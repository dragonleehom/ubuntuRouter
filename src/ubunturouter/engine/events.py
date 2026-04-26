"""配置变更事件 — 统一配置变更通知机制

所有模块通过订阅配置事件来响应配置变更。
实现发布-订阅模式，支持同步和异步监听器。
"""

import logging
import threading
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class ConfigChangeEvent:
    """配置变更事件载荷"""
    snapshot_id: str
    changed_sections: List[str]
    old_config: Optional[Dict[str, Any]] = None
    new_config: Optional[Dict[str, Any]] = None
    # 生成器执行结果记录
    generator_results: Dict[str, 'GeneratorResult'] = field(default_factory=dict)


@dataclass
class GeneratorResult:
    """生成器执行结果"""
    generator_name: str
    success: bool
    message: str = ""
    files_modified: List[str] = field(default_factory=list)


# 监听器类型：接受 ConfigChangeEvent 参数
Listener = Callable[[ConfigChangeEvent], GeneratorResult]


class ConfigEventBus:
    """配置变更事件总线 — 单例

    模块通过 subscribe() 注册自己的监听器，
    配置变更时通过 publish() 发布事件。
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._listeners = {}
                    cls._instance._order = []
        return cls._instance

    def subscribe(self, section: str, listener: Listener,
                  priority: int = 100) -> None:
        """订阅指定配置节的变更

        Args:
            section: 配置节名（如 'dns', 'firewall', 'pppoe'）
            listener: 回调函数，接收 ConfigChangeEvent，返回 GeneratorResult
            priority: 优先级（越小越先执行）
        """
        if section not in self._listeners:
            self._listeners[section] = []
        self._listeners[section].append((priority, listener))
        # 按优先级排序
        self._listeners[section].sort(key=lambda x: x[0])
        if section not in self._order:
            self._order.append(section)
        logger.info("Config listener registered for section '%s' (priority=%d)",
                     section, priority)

    def unsubscribe(self, section: str, listener: Listener) -> None:
        """取消订阅"""
        if section in self._listeners:
            self._listeners[section] = [
                (p, l) for p, l in self._listeners[section]
                if l is not listener
            ]

    def publish(self, event: ConfigChangeEvent) -> List[GeneratorResult]:
        """发布配置变更事件

        遍历所有受影响的配置节，依次调用它的监听器。
        如果某个监听器失败，继续执行其他监听器（不阻断）。

        Returns:
            所有生成器的执行结果列表
        """
        results = []
        changed = event.changed_sections

        for section in self._order:
            if section not in changed:
                continue
            listeners = self._listeners.get(section, [])
            for _, listener in listeners:
                try:
                    result = listener(event)
                    results.append(result)
                    event.generator_results[result.generator_name] = result
                    if result.success:
                        logger.info("Generator '%s' succeeded: %s",
                                     result.generator_name, result.message)
                    else:
                        logger.error("Generator '%s' failed: %s",
                                      result.generator_name, result.message)
                except Exception as e:
                    logger.exception("Generator for section '%s' crashed: %s",
                                     section, e)
                    results.append(GeneratorResult(
                        generator_name=f"unknown({section})",
                        success=False,
                        message=str(e),
                    ))

        return results

    def list_subscribers(self) -> Dict[str, List[str]]:
        """列出所有订阅者（调试用）"""
        result = {}
        for section, listeners in self._listeners.items():
            result[section] = [
                getattr(l, '__name__', str(l)) for _, l in listeners
            ]
        return result


# 便捷函数
def get_event_bus() -> ConfigEventBus:
    """获取全局事件总线实例"""
    return ConfigEventBus()
