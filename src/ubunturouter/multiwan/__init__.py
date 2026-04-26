"""Multi-WAN 模块 — 健康检查与故障切换"""
from .health import HealthChecker, WANStatus

__all__ = ["HealthChecker", "WANStatus"]
