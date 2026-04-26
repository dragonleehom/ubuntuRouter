"""故障转移引擎 — 监听 Multi-WAN 健康状态，切换流量编排出口"""
import logging
from typing import Optional, Dict, Any
from threading import Lock

from ..multiwan.health import HealthChecker

logger = logging.getLogger("ubunturouter.orchestrator.failover")


class FailoverEngine:
    """故障转移引擎

    监听 Multi-WAN 健康检查状态变化。当 active WAN 掉线时，
    自动切换流量编排规则中的出口通道（WAN1/WAN2/VPN）。

    与 HealthChecker 集成，回调 on_wan_status_change。
    """

    def __init__(self, health_checker: Optional[HealthChecker] = None):
        self._lock = Lock()
        self._health_checker = health_checker or HealthChecker()
        self._current_active: Optional[str] = None
        self._failover_callbacks: list = []

        # 初始化当前 active WAN
        status = self._health_checker.get_status()
        for wan in status:
            if wan.get("is_active"):
                self._current_active = wan.get("name")
                break

    # ─── 公共方法 ──────────────────────────────────────────────

    def start(self) -> None:
        """启动故障转移引擎（启动 HealthChecker 并注册回调）"""
        # 注册健康检查回调
        # 实际通过轮询 HealthChecker 状态实现
        logger.info(
            "Failover engine started, active WAN: %s", self._current_active
        )

    def on_wan_status_change(self, old_active: Optional[str],
                              new_active: Optional[str]) -> None:
        """WAN 状态变化回调

        Args:
            old_active: 之前的 active WAN 名称
            new_active: 新的 active WAN 名称
        """
        if old_active == new_active:
            return

        with self._lock:
            self._current_active = new_active

        logger.info(
            "WAN failover: %s -> %s",
            old_active or "(none)",
            new_active or "(none)",
        )

        # 通知所有回调
        for cb in self._failover_callbacks:
            try:
                cb(old_active, new_active)
            except Exception as e:
                logger.error("Failover callback error: %s", e)

    def register_callback(self, callback) -> None:
        """注册故障转移回调

        callback(old_active, new_active) 在 WAN 切换时被调用
        """
        with self._lock:
            self._failover_callbacks.append(callback)

    def get_active_wan(self) -> Optional[str]:
        """获取当前 active WAN 名称"""
        with self._lock:
            return self._current_active

    def check_and_failover(self) -> Optional[str]:
        """检查当前 WAN 状态，必要时执行故障切换

        Returns:
            切换后的 active WAN 名称，无变化返回 None
        """
        status = self._health_checker.get_status()
        if not status:
            return None

        old_active = self.get_active_wan()

        # 查找当前 active WAN 的在线状态
        active = next((w for w in status if w.get("is_active")), None)
        if active is None:
            return None

        # 如果 active WAN 不在线且自动故障转移开启
        if not active.get("online"):
            logger.warning(
                "Active WAN '%s' is offline, triggering failover",
                active.get("name"),
            )
            # 找第一个在线的 WAN
            online = [w for w in status if w.get("online") and not w.get("is_active")]
            if online:
                target = online[0]
                success = self._health_checker.switch_active(target["name"])
                if success:
                    new_active = target["name"]
                    self.on_wan_status_change(old_active, new_active)
                    return new_active

        return None

    def get_status(self) -> Dict[str, Any]:
        """获取故障转移引擎状态"""
        with self._lock:
            return {
                "active_wan": self._current_active,
                "callbacks_count": len(self._failover_callbacks),
            }
