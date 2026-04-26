"""配置引擎核心：加载、校验、Diff、Apply、回滚"""

import os
import fcntl
import time
import shutil
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import yaml

from ..config.models import UbunturouterConfig
from ..config.serializer import ConfigSerializer


CONFIG_PATH = Path("/etc/ubunturouter/config.yaml")
SNAPSHOT_DIR = Path("/var/lib/ubunturouter/snapshots")
LOCK_PATH = Path("/var/run/ubunturouter/engine.lock")
INIT_FLAG = Path("/etc/ubunturouter/.initialized")
FRESH_FLAG = Path("/etc/ubunturouter/.fresh-install")


@dataclass
class ValidationResult:
    """校验结果"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ConfigDiff:
    """配置变更差异摘要"""
    has_changes: bool
    summary: str = ""
    changed_sections: List[str] = field(default_factory=list)


@dataclass
class ApplyResult:
    """Apply 结果"""
    success: bool
    message: str = ""
    snapshot_id: Optional[str] = None
    execution_time_ms: int = 0


@dataclass
class SnapshotInfo:
    """快照信息"""
    id: str
    timestamp: str
    summary: str
    file_size: int


# ═══════════════════════════════════════════════════════
# 文件锁
# ═══════════════════════════════════════════════════════

class EngineLock:
    """文件锁，确保同一时刻只有一个 Apply 操作"""

    def __enter__(self):
        LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.lock = open(LOCK_PATH, 'w')
        fcntl.flock(self.lock, fcntl.LOCK_EX)
        return self

    def __exit__(self, *args):
        fcntl.flock(self.lock, fcntl.LOCK_UN)
        self.lock.close()


# ═══════════════════════════════════════════════════════
# 配置引擎
# ═══════════════════════════════════════════════════════

class ConfigEngine:
    """配置引擎核心"""

    def __init__(self, config_path: Path = CONFIG_PATH,
                 snapshot_dir: Path = SNAPSHOT_DIR):
        self.config_path = config_path
        self.snapshot_dir = snapshot_dir

    # ─── 配置加载 ─────────────────────────────────────

    def load(self) -> UbunturouterConfig:
        """加载当前配置"""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"配置文件不存在: {self.config_path}\n"
                "请先运行 urctl init 初始化系统"
            )
        return ConfigSerializer.from_yaml_file(self.config_path)

    def save(self, config: UbunturouterConfig) -> None:
        """保存配置（原子写入）"""
        ConfigSerializer.atomic_write_config(self.config_path, config)

    def exists(self) -> bool:
        """配置是否已存在"""
        return self.config_path.exists()

    # ─── 配置校验 ─────────────────────────────────────

    def validate(self, config: UbunturouterConfig) -> ValidationResult:
        """
        校验配置合法性
        
        1. Pydantic Schema 校验（模型自带）
        2. 语义校验（额外的业务规则）
        """
        errors = []
        warnings = []

        # 检查接口名唯一性
        iface_names = [i.name for i in config.interfaces]
        if len(iface_names) != len(set(iface_names)):
            duplicates = [n for n in iface_names if iface_names.count(n) > 1]
            errors.append(f'接口名重复: {", ".join(set(duplicates))}')

        # 检查 bridge 端口引用的接口是否存在
        for iface in config.interfaces:
            if iface.type == "bridge" and iface.ports:
                for port in iface.ports:
                    # port 可以是 device 名，也可以是其他接口的 name
                    found = any(
                        (i.device == port or i.name == port)
                        for i in config.interfaces
                    )
                    if not found:
                        warnings.append(
                            f'Bridge {iface.name} 的端口 {port} 未在其他接口定义中'
                        )

        # 检查端口转发的端口冲突
        used_ports = {}
        for pf in config.firewall.port_forwards:
            key = (pf.from_zone, pf.from_port, pf.protocol)
            if key in used_ports:
                errors.append(
                    f'端口转发端口冲突: {pf.from_zone}:{pf.from_port}/{pf.protocol}'
                )
            used_ports[key] = pf.name

        # 检查 DHCP 地址池范围
        if config.dhcp:
            try:
                start_parts = config.dhcp.range_start.split('.')
                end_parts = config.dhcp.range_end.split('.')
                if start_parts[:3] != end_parts[:3]:
                    warnings.append(
                        'DHCP 地址池的起始和结束地址不在同一网段'
                    )
            except:
                pass

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    # ─── 配置 Diff ───────────────────────────────────

    def diff(self, new_config: UbunturouterConfig) -> ConfigDiff:
        """计算新旧配置的差异"""
        if not self.config_path.exists():
            return ConfigDiff(
                has_changes=True,
                summary="首次创建配置",
                changed_sections=["interfaces", "firewall", "routing", "dhcp", "dns"]
            )

        old_config = self.load()
        old_dict = old_config.model_dump(exclude_none=True)
        new_dict = new_config.model_dump(exclude_none=True)

        changed = []
        for section in ['interfaces', 'firewall', 'routing', 'dhcp', 'dns', 'system']:
            old_val = old_dict.get(section)
            new_val = new_dict.get(section)
            if old_val != new_val:
                changed.append(section)

        return ConfigDiff(
            has_changes=len(changed) > 0,
            summary=f'变更的配置节: {", ".join(changed)}' if changed else '无变更',
            changed_sections=changed
        )

    # ─── 快照管理 ─────────────────────────────────────

    def create_snapshot(self, config: UbunturouterConfig,
                        summary: str = "") -> str:
        """创建配置快照"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_id = f"{timestamp}_{os.urandom(3).hex()}"

        snap_path = self.snapshot_dir / snapshot_id
        snap_path.mkdir(parents=True, exist_ok=True)

        # 保存配置
        serialized = ConfigSerializer.to_yaml(config)
        (snap_path / "config.yaml").write_text(serialized, encoding='utf-8')

        # 保存元数据
        meta = {
            "id": snapshot_id,
            "timestamp": timestamp,
            "summary": summary or f"快照 {snapshot_id}",
        }
        (snap_path / "meta.yaml").write_text(
            yaml.dump(meta, default_flow_style=False),
            encoding='utf-8'
        )

        # 更新 latest 符号链接
        latest_link = self.snapshot_dir / "latest"
        if latest_link.exists() or latest_link.is_symlink():
            latest_link.unlink()
        latest_link.symlink_to(snapshot_id)

        # 清理旧快照
        self._cleanup_old_snapshots()

        return snapshot_id

    def list_snapshots(self) -> List[SnapshotInfo]:
        """列出所有快照"""
        if not self.snapshot_dir.exists():
            return []

        snapshots = []
        for entry in sorted(self.snapshot_dir.iterdir(), reverse=True):
            if entry.is_dir() and entry.name != "latest":
                meta_file = entry / "meta.yaml"
                config_file = entry / "config.yaml"
                if config_file.exists():
                    meta = {"summary": "", "timestamp": entry.name[:15]}
                    if meta_file.exists():
                        try:
                            meta = yaml.safe_load(meta_file.read_text()) or meta
                        except:
                            pass
                    snapshots.append(SnapshotInfo(
                        id=entry.name,
                        timestamp=meta.get("timestamp", ""),
                        summary=meta.get("summary", ""),
                        file_size=config_file.stat().st_size
                    ))
        return snapshots

    def get_snapshot(self, snapshot_id: str) -> Optional[UbunturouterConfig]:
        """读取指定快照的配置"""
        if snapshot_id == "latest":
            latest_link = self.snapshot_dir / "latest"
            if latest_link.exists() or latest_link.is_symlink():
                snapshot_id = latest_link.resolve().name
            else:
                return None

        snap_path = self.snapshot_dir / snapshot_id / "config.yaml"
        if not snap_path.exists():
            return None
        try:
            return ConfigSerializer.from_yaml_file(snap_path)
        except Exception:
            return None

    def _cleanup_old_snapshots(self, max_snapshots: int = 50):
        """清理旧快照，保留最近 N 个"""
        if not self.snapshot_dir.exists():
            return

        snapshots = sorted([
            d for d in self.snapshot_dir.iterdir()
            if d.is_dir() and d.name != "latest"
        ], key=lambda d: d.name, reverse=True)

        for old in snapshots[max_snapshots:]:
            shutil.rmtree(old)

    # ─── Apply 与回滚 ─────────────────────────────────

    def apply(self, new_config: UbunturouterConfig,
              auto_rollback: bool = True) -> ApplyResult:
        """
        应用配置变更
        
        流程:
        1. 校验
        2. 创建快照
        3. 保存配置
        4. 通知各 Manager Apply
        """
        start_time = time.time()

        with EngineLock():
            # 1. 校验
            validation = self.validate(new_config)
            if not validation.is_valid:
                return ApplyResult(
                    success=False,
                    message=f'配置校验失败:\n' + '\n'.join(validation.errors),
                    execution_time_ms=int((time.time() - start_time) * 1000)
                )

            # 2. 创建快照
            snapshot_id = None
            if self.exists():
                current = self.load()
                diff_result = self.diff(new_config)
                if not diff_result.has_changes:
                    return ApplyResult(
                        success=True,
                        message='配置无变更，跳过 Apply',
                        execution_time_ms=int((time.time() - start_time) * 1000)
                    )
                snapshot_id = self.create_snapshot(
                    current, summary=diff_result.summary
                )
            else:
                snapshot_id = self.create_snapshot(
                    new_config, summary="初始配置"
                )

            # 3. 保存新配置
            try:
                self.save(new_config)
            except Exception as e:
                return ApplyResult(
                    success=False,
                    message=f'写入配置文件失败: {e}',
                    execution_time_ms=int((time.time() - start_time) * 1000)
                )

            # 4. 通知各 Generator（此处为桩，后续由 Manager 实现）
            # TODO: 调用 NetworkManager.apply()
            # TODO: 调用 FirewallManager.apply()
            # TODO: 调用 DnsmasqManager.apply()

            return ApplyResult(
                success=True,
                message='配置已保存（子系统 Apply 待实现）',
                snapshot_id=snapshot_id,
                execution_time_ms=int((time.time() - start_time) * 1000)
            )

    def rollback(self, snapshot_id: str = "latest") -> ApplyResult:
        """回滚到指定快照"""
        start_time = time.time()

        with EngineLock():
            snapshot = self.get_snapshot(snapshot_id)
            if snapshot is None:
                return ApplyResult(
                    success=False,
                    message=f'快照不存在: {snapshot_id}',
                    execution_time_ms=int((time.time() - start_time) * 1000)
                )

            # 备份当前配置作为快照（以防回滚后需要再次回滚）
            if self.exists():
                current = self.load()
                self.create_snapshot(current, summary="回滚前自动备份")

            # 保存快照配置
            self.save(snapshot)

            # TODO: 通知各 Manager 重新 Apply

            return ApplyResult(
                success=True,
                message=f'已回滚到快照: {snapshot_id}',
                snapshot_id=snapshot_id,
                execution_time_ms=int((time.time() - start_time) * 1000)
            )
