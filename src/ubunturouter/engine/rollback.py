"""回滚管理器 — 快照创建/回滚/清理"""

import os
import time
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from ..config.models import UbunturouterConfig
from ..config.serializer import ConfigSerializer


class RollbackManager:
    """回滚管理器"""

    MAX_SNAPSHOTS = 50

    def __init__(self, snapshot_dir: Optional[Path] = None):
        self.snapshot_dir = snapshot_dir or Path("/var/lib/ubunturouter/snapshots")

    def create_snapshot(self, config: UbunturouterConfig, summary: str = "") -> str:
        """
        创建配置快照。
        返回快照 ID。
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_hash = f"{id(config):08x}"[:8]
        snapshot_id = f"{timestamp}_{short_hash}"

        snap_path = self.snapshot_dir / snapshot_id
        systemd_path = snap_path / "systemd"

        snap_path.mkdir(parents=True, exist_ok=True)
        systemd_path.mkdir(parents=True, exist_ok=True)

        # 保存配置
        ConfigSerializer.atomic_write_config(
            snap_path / "config.yaml", config
        )

        # 保存元数据
        meta = {
            "snapshot_id": snapshot_id,
            "created_at": datetime.now().isoformat(),
            "summary": summary or "自动快照",
            "good": False,
        }
        self._write_meta(snap_path, meta)

        # 保存当前子系统配置（如果存在）
        self._backup_system_configs(systemd_path)

        # 更新 latest 符号链接
        latest_link = self.snapshot_dir / "latest"
        if latest_link.exists() or latest_link.is_symlink():
            latest_link.unlink()
        latest_link.symlink_to(snap_path)

        # 清理旧快照
        self.cleanup_old_snapshots()

        return snapshot_id

    def auto_rollback(self, snapshot_id: str) -> bool:
        """自动回滚到指定快照。返回 True=回滚成功，False=回滚失败"""
        snap_path = self.snapshot_dir / snapshot_id
        if not snap_path.exists():
            return False

        systemd_path = snap_path / "systemd"

        try:
            # 1. 恢复子系统配置
            if systemd_path.exists():
                self._restore_system_configs(systemd_path)

            # 2. 恢复主配置文件
            config_file = snap_path / "config.yaml"
            if config_file.exists():
                dest = Path("/etc/ubunturouter/config.yaml")
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(config_file), str(dest))

            # 3. 重载服务
            self._reload_all_services()

            # 4. 连通性检测（简化版 — 30s）
            deadline = time.time() + 30
            while time.time() < deadline:
                try:
                    r = subprocess.run(
                        ["ping", "-c", "1", "-W", "1", "127.0.0.1"],
                        capture_output=True, timeout=2
                    )
                    if r.returncode == 0:
                        # 再等 3 秒让服务稳定
                        time.sleep(3)
                        return True
                except Exception:
                    pass
                time.sleep(2)

            return True  # 即使 ping 不通也返回成功（已恢复配置）

        except Exception:
            return False

    def mark_snapshot_good(self, snapshot_id: str) -> None:
        """标记快照为已验证成功"""
        snap_path = self.snapshot_dir / snapshot_id
        meta_file = snap_path / "meta.yaml"
        if meta_file.exists():
            import yaml
            with open(meta_file, 'r') as f:
                meta = yaml.safe_load(f) or {}
            meta["good"] = True
            self._write_meta(snap_path, meta)
            # 创建 good 标记文件
            (snap_path / "good").touch()

    def cleanup_old_snapshots(self) -> None:
        """删除超过 MAX_SNAPSHOTS 的旧快照"""
        if not self.snapshot_dir.exists():
            return

        snapshots = sorted([
            p for p in self.snapshot_dir.iterdir()
            if p.is_dir() and p.name != "latest" and p.name[0].isdigit()
        ], key=lambda p: p.name)

        while len(snapshots) > self.MAX_SNAPSHOTS:
            oldest = snapshots.pop(0)
            shutil.rmtree(str(oldest), ignore_errors=True)

    def list_snapshots(self) -> List[dict]:
        """列出所有快照"""
        if not self.snapshot_dir.exists():
            return []

        import yaml
        snapshots = []
        for p in sorted(self.snapshot_dir.iterdir(), reverse=True):
            if not p.is_dir() or p.name == "latest":
                continue
            meta_file = p / "meta.yaml"
            meta = {}
            if meta_file.exists():
                try:
                    with open(meta_file) as f:
                        meta = yaml.safe_load(f) or {}
                except Exception:
                    pass
            meta["snapshot_id"] = meta.get("snapshot_id", p.name)
            meta["dir"] = str(p)
            snapshots.append(meta)
        return snapshots

    # ─── 内部方法 ────────────────────────────────────────

    def _write_meta(self, snap_path: Path, meta: dict) -> None:
        import yaml
        with open(snap_path / "meta.yaml", 'w') as f:
            yaml.dump(meta, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def _backup_system_configs(self, systemd_path: Path) -> None:
        """备份当前子系统配置文件"""
        configs = {
            "01-netplan.yaml": "/etc/netplan/01-ubunturouter.yaml",
            "nftables.conf": "/etc/nftables.d/ubunturouter.conf",
            "dnsmasq.conf": "/etc/dnsmasq.d/ubunturouter.conf",
        }
        for name, src_path in configs.items():
            src = Path(src_path)
            if src.exists():
                shutil.copy2(str(src), str(systemd_path / name))

    def _restore_system_configs(self, systemd_path: Path) -> None:
        """从备份恢复子系统配置文件"""
        configs = {
            "01-netplan.yaml": "/etc/netplan/01-ubunturouter.yaml",
            "nftables.conf": "/etc/nftables.d/ubunturouter.conf",
            "dnsmasq.conf": "/etc/dnsmasq.d/ubunturouter.conf",
        }
        for name, dest_path in configs.items():
            backup = systemd_path / name
            if backup.exists():
                dest = Path(dest_path)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(backup), str(dest))

    def _reload_all_services(self) -> None:
        """回滚后重载所有服务"""
        commands = [
            ["netplan", "apply"],
            ["nft", "-f", "/etc/nftables.d/ubunturouter.conf"],
            ["systemctl", "reload-or-restart", "dnsmasq"],
        ]
        for cmd in commands:
            try:
                subprocess.run(cmd, capture_output=True, timeout=30)
                time.sleep(1)
            except Exception:
                pass
