"""配置引擎 — 配置加载/校验/Diff/Apply/回滚"""
import logging
from .engine import ConfigEngine, ValidationResult, ConfigDiff, ApplyResult
from .lock import EngineLock
from .applier import ConfigApplier
from .rollback import RollbackManager
from .initializer import Initializer

logger = logging.getLogger(__name__)


def _init_subsystem():
    """懒加载 Generator 子系统（避免循环导入）"""
    from .events import ConfigChangeEvent, ConfigEventBus, get_event_bus
    from .generators.base import (
        BaseGenerator, register_generator, get_generator,
        get_all_generators, list_generators,
    )
    # 主动触发所有 Generator 注册（import 触发 @register_generator 装饰器）
    from .generators import (
        netplan_generator,
        dnsmasq_generator,
        pppoe_generator,
        samba_generator,
        system_generator,
        firewall_generator,
    )
    # 主动实例化所有已注册的 Generator
    for gen_cls in [
        netplan_generator.NetplanGenerator,
        dnsmasq_generator.DnsmasqGenerator,
        pppoe_generator.PPPoEGenerator,
        samba_generator.SambaGenerator,
        system_generator.SystemGenerator,
        firewall_generator.FirewallGenerator,
    ]:
        gen_cls._get_instance()

    registered = list_generators()
    logger.info("Generators registered: %s", registered)
    return locals()


# 延迟初始化一次
_init_subsystem()

__all__ = [
    "ConfigEngine",
    "ValidationResult",
    "ConfigDiff",
    "ApplyResult",
    "EngineLock",
    "ConfigApplier",
    "RollbackManager",
    "Initializer",
]
