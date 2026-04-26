"""配置应用器 — 原子 Apply + 服务 Reload 顺序"""

import subprocess
import time
import shlex
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from ..config.models import UbunturouterConfig
from .engine import ConfigEngine
from .lock import EngineLock
from .rollback import RollbackManager
from ..generators.base import GeneratorRegistry


@dataclass
class ServiceResult:
    name: str
    success: bool
    output: str = ""
    duration_ms: int = 0


@dataclass
class ApplyResult:
    success: bool
    snapshot_id: Optional[str] = None
    rollback_to: Optional[str] = None
    error: Optional[str] = None
    service_results: List[ServiceResult] = field(default_factory=list)
    changed_sections: List[str] = field(default_factory=list)


# 服务依赖顺序
SERVICE_ORDER = [
    ("netplan", "networking", 0),       # 网络先就绪
    ("nftables", "nftables", 500),       # 防火墙
    ("dnsmasq", "dnsmasq", 200),         # DHCP+DNS
]

TIMEOUT_HEALTH_CHECK = 60  # 秒
TIMEOUT_SERVICE = 30       # 秒


class ConfigApplier:
    """配置应用器 — 按正确顺序执行配置变更"""

    def __init__(self, engine: ConfigEngine, registry: GeneratorRegistry):
        self.engine = engine
        self.registry = registry
        self.rollback = RollbackManager(snapshot_dir=engine.snapshot_dir)

    def apply_atomic(self, config: UbunturouterConfig,
                     auto_rollback: bool = True) -> ApplyResult:
        """原子 Apply — 完整流程"""
        result = ApplyResult(success=False)

        with EngineLock():
            try:
                # 1. 校验配置
                validation = self.engine.validate(config)
                if validation.errors:
                    result.error = "配置校验失败:\n" + "\n".join(validation.errors)
                    return result

                # 2. 计算 diff（仅处理有变更的 section）
                diff = self.engine.diff(config)
                result.changed_sections = diff.changed_sections
                if not diff.has_changes:
                    result.success = True
                    return result

                # 3. 创建快照
                current_config = None
                try:
                    current_config = self.engine.load()
                except FileNotFoundError:
                    pass  # 首次初始化，无当前配置

                snapshot_id = self.rollback.create_snapshot(
                    current_config or config,
                    summary=f"Apply: {', '.join(diff.changed_sections)}"
                )
                result.snapshot_id = snapshot_id

                # 4. 生成子系统配置
                all_generated = self.registry.generate_all(config)

                # 5. 校验生成的配置文件
                for name, files in all_generated.items():
                    generator = self.registry.get(name)
                    if generator:
                        for path_str, content in files.items():
                            err = generator.validate_generated(content)
                            if err:
                                result.error = f"{name} 配置校验失败: {err}"
                                if auto_rollback:
                                    self._rollback(snapshot_id, result)
                                return result

                # 6. 原子写入文件
                write_errors = self._write_all_files(all_generated)
                if write_errors:
                    result.error = f"写入配置文件失败: {', '.join(write_errors)}"
                    if auto_rollback:
                        self._rollback(snapshot_id, result)
                    return result

                # 7. 保存新配置到引擎
                self.engine.save(config)

                # 8. 按序 reload 服务
                for name, service, delay_ms in SERVICE_ORDER:
                    if name not in all_generated:
                        continue
                    gen = self.registry.get(name)
                    if not gen:
                        continue

                    cmd = gen.reload_command()
                    if not cmd:
                        continue

                    sr = self._reload_service(name, service, cmd)
                    result.service_results.append(sr)

                    if not sr.success and auto_rollback:
                        self._rollback(snapshot_id, result)
                        return result

                    if delay_ms > 0:
                        time.sleep(delay_ms / 1000.0)

                # 9. 连通性检测
                if auto_rollback:
                    health_ok = self._check_health(config)
                    if not health_ok:
                        result.error = "连通性检测失败，触发自动回滚"
                        self._rollback(snapshot_id, result)
                        return result

                # 10. 成功 — 标记快照为 good
                self.rollback.mark_snapshot_good(snapshot_id)
                result.success = True

            except Exception as e:
                result.error = f"Apply 异常: {str(e)}"
                if auto_rollback and result.snapshot_id:
                    self._rollback(result.snapshot_id, result)

        return result

    def _write_all_files(self, all_generated: Dict[str, Dict[str, str]]) -> List[str]:
        """原子写入所有生成的配置文件"""
        errors = []
        for name, files in all_generated.items():
            for path_str, content in files.items():
                p = Path(path_str)
                try:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    # 使用原子写入
                    import tempfile
                    fd, tmp_path = tempfile.mkstemp(
                        dir=str(p.parent),
                        prefix=f'.{p.name}.',
                        suffix='.tmp'
                    )
                    import os
                    try:
                        with os.fdopen(fd, 'w', encoding='utf-8') as f:
                            f.write(content)
                            f.flush()
                            os.fsync(fd)
                        os.replace(tmp_path, str(p))
                    except:
                        try:
                            os.unlink(tmp_path)
                        except OSError:
                            pass
                        raise
                except Exception as e:
                    errors.append(f"{path_str}: {e}")
        return errors

    def _reload_service(self, name: str, service: str, cmd: List[str]) -> ServiceResult:
        """重新加载单个服务"""
        start = time.time()
        sr = ServiceResult(name=name)

        try:
            cmd_str = " ".join(shlex.quote(c) for c in cmd)
            r = subprocess.run(
                cmd_str, shell=True, capture_output=True, text=True,
                timeout=TIMEOUT_SERVICE
            )
            sr.output = (r.stdout + r.stderr)[:200]
            sr.success = r.returncode == 0
        except subprocess.TimeoutExpired:
            sr.output = f"命令超时 ({TIMEOUT_SERVICE}s)"
            sr.success = False
        except Exception as e:
            sr.output = str(e)
            sr.success = False

        sr.duration_ms = int((time.time() - start) * 1000)
        return sr

    def _check_health(self, config: UbunturouterConfig) -> bool:
        """连通性检测 — 60s 内轮询"""
        deadline = time.time() + TIMEOUT_HEALTH_CHECK
        checks = []

        # 构建检查项
        lan_ifaces = [i for i in config.interfaces
                      if i.role.value in ("lan", "wanlan")]
        for i in lan_ifaces:
            if i.ipv4 and i.ipv4.address:
                ip = i.ipv4.address.split("/")[0]
                checks.append(("ping_lan", ip))

        # DNS 检查
        if config.dhcp and config.dhcp.gateway:
            checks.append(("dns", config.dhcp.gateway))

        while time.time() < deadline:
            passed = 0
            for check_type, target in checks:
                try:
                    if check_type == "ping_lan":
                        r = subprocess.run(
                            ["ping", "-c", "1", "-W", "1", target],
                            capture_output=True, timeout=2
                        )
                        if r.returncode == 0:
                            passed += 1
                    elif check_type == "dns":
                        r = subprocess.run(
                            ["dig", f"@target", "ubunturouter.local", "+short", "+time=1"],
                            capture_output=True, timeout=2
                        )
                        # DNS 不强制通过
                        if r.returncode == 0:
                            passed += 1
                except Exception:
                    pass

            # 至少 ping 通一个 LAN IP
            if passed >= 1:
                return True

            time.sleep(2)

        return False

    def _rollback(self, snapshot_id: str, result: ApplyResult) -> None:
        """执行回滚"""
        rb_result = self.rollback.auto_rollback(snapshot_id)
        result.rollback_to = snapshot_id
        if rb_result:
            result.error = (result.error or "") + f" (已回滚到快照 {snapshot_id})"
        else:
            result.error = (result.error or "") + f" (回滚失败! 严重错误, 快照: {snapshot_id})"
