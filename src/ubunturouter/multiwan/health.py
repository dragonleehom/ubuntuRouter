"""Multi-WAN 健康检查引擎 — 后台检测 WAN 线路健康并自动故障切换"""

import subprocess
import threading
import time
import logging
import re
import statistics
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

import yaml

from ..routing import RoutingManager

logger = logging.getLogger("ubunturouter.multiwan")

CONFIG_PATH = Path("/opt/ubunturouter/config/multiwan.yaml")

DEFAULT_CONFIG: Dict[str, Any] = {
    "wans": [
        {"name": "wan1", "iface": "eth0", "gateway": "192.168.1.1", "weight": 1},
        {"name": "wan2", "iface": "eth1", "gateway": "10.0.0.1", "weight": 1},
    ],
    "check_interval": 5,
    "ping_targets": ["8.8.8.8", "114.114.114.114"],
    "ping_count": 3,
    "failure_threshold": 2,
    "recovery_threshold": 3,
    "auto_failover": True,
    "load_balance": False,
}


class WANStatus:
    """单个 WAN 线路的运行时状态"""

    def __init__(self, name: str, iface: str, gateway: str, weight: int = 1):
        self.name = name
        self.iface = iface
        self.gateway = gateway
        self.weight = weight

        self.online: bool = True
        self.latency_ms: float = 0.0
        self.packet_loss: float = 0.0
        self.is_active: bool = False
        self.failures: int = 0
        self.recoveries: int = 0
        self.last_check: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "iface": self.iface,
            "gateway": self.gateway,
            "online": self.online,
            "latency_ms": round(self.latency_ms, 2),
            "packet_loss": round(self.packet_loss, 1),
            "is_active": self.is_active,
            "failures": self.failures,
            "last_check": self.last_check.isoformat() if self.last_check else None,
        }

    def __repr__(self) -> str:
        return (
            f"<WANStatus {self.name} iface={self.iface} gateway={self.gateway} "
            f"online={self.online} active={self.is_active}>"
        )


class HealthChecker:
    """Multi-WAN 健康检查引擎

    在后台线程中定期对所有 WAN 线路执行 ping 检测，根据配置的阈值自动切换默认路由。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # 加载配置（优先从 yaml 加载，然后合并传入的配置覆盖）
        self._config: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self.load_config()
        if config is not None:
            self._update_config_internal(config)

        # 构建 WAN 状态列表
        self._wans: List[WANStatus] = []
        self._active_wan_index: int = 0
        self._rebuild_wans()

        # 路由管理器
        self._routing = RoutingManager()

    # ─── 公共方法 ──────────────────────────────────────────────

    def start(self) -> None:
        """启动后台健康检查线程"""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                logger.warning("HealthChecker is already running")
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop, daemon=True, name="multiwan-health"
            )
            self._thread.start()
            logger.info("Multi-WAN health checker started")

    def stop(self) -> None:
        """停止后台健康检查线程"""
        self._stop_event.set()
        with self._lock:
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=10)
                if self._thread.is_alive():
                    logger.warning("Health checker thread did not stop gracefully")
                else:
                    logger.info("Multi-WAN health checker stopped")
            self._thread = None

    def get_status(self) -> List[Dict[str, Any]]:
        """返回所有 WAN 线路的当前状态列表"""
        with self._lock:
            return [w.to_dict() for w in self._wans]

    def get_config(self) -> Dict[str, Any]:
        """返回当前配置（深拷贝避免外部修改）"""
        with self._lock:
            import copy
            return copy.deepcopy(self._config)

    def update_config(self, new_config: Dict[str, Any]) -> None:
        """更新配置并持久化"""
        with self._lock:
            self._update_config_internal(new_config)
            self._rebuild_wans()
        self.persist_config()
        logger.info("Multi-WAN configuration updated and persisted")

    def switch_active(self, wan_name: str) -> bool:
        """手动切换到指定 WAN 线路

        Returns:
            True 切换成功, False 找不到该 WAN 或切换失败
        """
        with self._lock:
            for idx, wan in enumerate(self._wans):
                if wan.name == wan_name:
                    logger.info(
                        "Manual switch to WAN %s (iface=%s, gateway=%s)",
                        wan_name, wan.iface, wan.gateway,
                    )
                    return self._perform_switch(idx)
            logger.warning("Manual switch failed: WAN '%s' not found", wan_name)
            return False

    def persist_config(self) -> None:
        """将当前配置写入持久化文件"""
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                config_copy = dict(self._config)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                yaml.dump(config_copy, f, default_flow_style=False, allow_unicode=True)
            logger.debug("Configuration persisted to %s", CONFIG_PATH)
        except OSError as e:
            logger.error("Failed to persist configuration: %s", e)

    def load_config(self) -> None:
        """从持久化文件读取配置"""
        try:
            if CONFIG_PATH.exists():
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    # 合并，不丢失默认字段
                    merged = dict(DEFAULT_CONFIG)
                    merged.update(loaded)
                    with self._lock:
                        self._config = merged
                    logger.info("Configuration loaded from %s", CONFIG_PATH)
        except (yaml.YAMLError, OSError) as e:
            logger.warning("Failed to load configuration from %s: %s", CONFIG_PATH, e)

    # ─── 内部方法 ──────────────────────────────────────────────

    def _update_config_internal(self, new_config: Dict[str, Any]) -> None:
        """无锁版配置合并（调用方需持有 _lock）"""
        merged = dict(self._config)
        merged.update(new_config)
        self._config = merged

    def _rebuild_wans(self) -> None:
        """根据配置重建 WANStatus 列表（调用方需持有 _lock）"""
        wans_config = self._config.get("wans", [])
        old_active_name: Optional[str] = None
        if self._wans and self._active_wan_index < len(self._wans):
            old_active_name = self._wans[self._active_wan_index].name

        new_wans: List[WANStatus] = []
        for wc in wans_config:
            wan = WANStatus(
                name=wc.get("name", "unknown"),
                iface=wc.get("iface", ""),
                gateway=wc.get("gateway", ""),
                weight=wc.get("weight", 1),
            )
            new_wans.append(wan)

        self._wans = new_wans

        # 尝试保持旧的 active WAN
        if old_active_name:
            for idx, wan in enumerate(self._wans):
                if wan.name == old_active_name:
                    wan.is_active = True
                    self._active_wan_index = idx
                    break
            else:
                # 旧的 active WAN 不存在了，选第一个
                if self._wans:
                    self._wans[0].is_active = True
                    self._active_wan_index = 0
        else:
            if self._wans:
                self._wans[0].is_active = True
                self._active_wan_index = 0

    def _run_loop(self) -> None:
        """后台线程主循环"""
        logger.debug("Health check loop started")
        while not self._stop_event.is_set():
            interval = self._get_check_interval()
            self._check_all_wans()
            time.sleep(interval)

    def _get_check_interval(self) -> float:
        with self._lock:
            return float(self._config.get("check_interval", 5))

    def _check_all_wans(self) -> None:
        """对每个 WAN 执行一次健康检查并触发自动切换逻辑"""
        with self._lock:
            wans = list(self._wans)
            config = dict(self._config)

        ping_targets = config.get("ping_targets", [])
        ping_count = config.get("ping_count", 3)
        failure_threshold = config.get("failure_threshold", 2)
        recovery_threshold = config.get("recovery_threshold", 3)
        auto_failover = config.get("auto_failover", True)

        now = datetime.now()
        failover_needed = False

        for wan in wans:
            latencies: List[float] = []
            total_loss = 0.0
            target_count = len(ping_targets)

            for target in ping_targets:
                lat, loss = self._ping_wan(wan.iface, target, ping_count)
                if loss < 100:
                    latencies.append(lat)
                total_loss += loss

            avg_loss = total_loss / target_count if target_count > 0 else 100.0
            avg_latency = statistics.mean(latencies) if latencies else 0.0

            # 更新状态（需要锁保护 _wans）
            with self._lock:
                current_wan = self._find_wan_internal(wan.name)
                if current_wan is None:
                    continue

                current_wan.last_check = now

                if avg_loss >= 100:
                    # 检测失败：所有 target 都 ping 不通
                    current_wan.failures += 1
                    current_wan.recoveries = 0
                    current_wan.latency_ms = 0.0
                    current_wan.packet_loss = avg_loss

                    if (
                        current_wan.online
                        and current_wan.failures >= failure_threshold
                    ):
                        current_wan.online = False
                        logger.warning(
                            "WAN '%s' (iface=%s) marked OFFLINE after %d failures",
                            current_wan.name,
                            current_wan.iface,
                            current_wan.failures,
                        )
                        if auto_failover and current_wan.is_active:
                            failover_needed = True
                else:
                    # 检测成功
                    current_wan.recoveries += 1
                    current_wan.failures = 0
                    current_wan.latency_ms = avg_latency
                    current_wan.packet_loss = avg_loss

                    if (
                        not current_wan.online
                        and current_wan.recoveries >= recovery_threshold
                    ):
                        current_wan.online = True
                        logger.info(
                            "WAN '%s' (iface=%s) RECOVERED after %d successes",
                            current_wan.name,
                            current_wan.iface,
                            current_wan.recoveries,
                        )
                        # 如果原来 active 的 WAN 恢复了，自动回切
                        if auto_failover and self._should_fallback(current_wan):
                            logger.info(
                                "Falling back to original WAN '%s' after recovery",
                                current_wan.name,
                            )
                            idx = self._find_wan_index_internal(current_wan.name)
                            if idx is not None:
                                self._perform_switch_internal(idx)

        # 在遍历完所有 WAN 后统一处理自动故障切换
        if failover_needed:
            with self._lock:
                self._auto_failover_internal()

        # 日志输出调试信息
        if not failover_needed:
            with self._lock:
                active = self._get_active_wan_internal()
                if active:
                    logger.debug(
                        "Health check complete | active=%s online=%s "
                        "latency=%.1fms loss=%.1f%%",
                        active.name,
                        active.online,
                        active.latency_ms,
                        active.packet_loss,
                    )

    def _ping_wan(self, iface: str, target: str, count: int) -> tuple:
        """通过指定接口 ping 目标，返回 (avg_latency, packet_loss_percent)"""
        try:
            r = subprocess.run(
                ["ping", "-I", iface, "-c", str(count), "-W", "2", target],
                capture_output=True,
                text=True,
                timeout=10,
            )
            output = r.stdout

            avg_latency = 0.0
            match = re.search(r"rtt min/avg/max/mdev = [\d.]+/([\d.]+)/", output)
            if match:
                avg_latency = float(match.group(1))

            loss = 100.0
            match = re.search(r"(\d+)% packet loss", output)
            if match:
                loss = float(match.group(1))

            return avg_latency, loss
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.debug("Ping failed for iface=%s target=%s: %s", iface, target, e)
            return 0.0, 100.0

    def _find_wan_internal(self, name: str) -> Optional[WANStatus]:
        """在 _wans 列表中按名称查找（调用方需持有 _lock）"""
        for wan in self._wans:
            if wan.name == name:
                return wan
        return None

    def _find_wan_index_internal(self, name: str) -> Optional[int]:
        """按名称查找索引（调用方需持有 _lock）"""
        for idx, wan in enumerate(self._wans):
            if wan.name == name:
                return idx
        return None

    def _get_active_wan_internal(self) -> Optional[WANStatus]:
        """获取当前 active WAN（调用方需持有 _lock）"""
        if 0 <= self._active_wan_index < len(self._wans):
            return self._wans[self._active_wan_index]
        return None

    def _should_fallback(self, recovered_wan: WANStatus) -> bool:
        """判断是否应该自动回切到刚恢复的 WAN

        仅当该 WAN 之前是 active 的且当前 active 不是它时才回切。
        """
        active = self._get_active_wan_internal()
        return active is not None and recovered_wan.name != active.name

    def _auto_failover_internal(self) -> None:
        """自动故障切换：从在线 WAN 中选择下一个（调用方需持有 _lock）"""
        active = self._get_active_wan_internal()
        if active is not None and active.online:
            return  # 当前 active WAN 仍在线，不需要切换

        # 按 weight 降序选在线 WAN
        online_wans = [
            (i, w) for i, w in enumerate(self._wans) if w.online and not w.is_active
        ]

        if not online_wans:
            logger.warning("No online WAN available for failover")
            return

        # 按 weight 降序，weight 相同保持原有顺序
        online_wans.sort(key=lambda x: x[1].weight, reverse=True)
        target_idx, target_wan = online_wans[0]

        logger.info(
            "Auto-failover: switching from '%s' to '%s' (iface=%s, gateway=%s)",
            active.name if active else "(none)",
            target_wan.name,
            target_wan.iface,
            target_wan.gateway,
        )
        self._perform_switch_internal(target_idx)

    def _perform_switch(self, target_idx: int) -> bool:
        """执行切换到指定索引的 WAN（外部调用，需持有 _lock）"""
        return self._perform_switch_internal(target_idx)

    def _perform_switch_internal(self, target_idx: int) -> bool:
        """内部切换实现（调用方需持有 _lock）

        1. 清除旧的 active 标记
        2. 设置新的 active
        3. 调用 RoutingManager.switch_default_gateway
        """
        if target_idx < 0 or target_idx >= len(self._wans):
            logger.error("Switch failed: index %d out of range", target_idx)
            return False

        # 清除旧 active
        old_active = self._get_active_wan_internal()
        if old_active is not None:
            old_active.is_active = False

        # 设置新 active
        new_active = self._wans[target_idx]
        new_active.is_active = True
        self._active_wan_index = target_idx

        # 执行路由切换
        success = self._routing.switch_default_gateway(
            new_active.iface, new_active.gateway
        )

        if success:
            logger.info(
                "Default gateway switched to %s (iface=%s, gateway=%s)",
                new_active.name,
                new_active.iface,
                new_active.gateway,
            )
        else:
            logger.error(
                "Failed to switch default gateway to %s (iface=%s, gateway=%s)",
                new_active.name,
                new_active.iface,
                new_active.gateway,
            )

        return success
