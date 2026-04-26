"""配置生成器基类 — 将统一配置模型转写为各子系统配置文件

所有模块的 Generator 放在 engine/generators/ 目录下。
每个 Generator 继承 BaseGenerator，实现 generate() 方法。
"""

import logging
import os
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

from ubunturouter.config.models import UbunturouterConfig
from ubunturouter.engine.events import GeneratorResult


logger = logging.getLogger(__name__)


class BaseGenerator(ABC):
    """配置生成器基类

    每个子系统（DNS、PPPoE、Firewall 等）实现一个 Generator，
    负责将 UbunturouterConfig 模型中的相关配置节转写为实际的
    系统配置文件，并 reload 对应的 daemon。
    """

    # 该 Generator 负责的配置节名
    SECTION: str = ""

    def __init__(self):
        if not self.SECTION:
            raise ValueError("SECTION must be set in subclass")
        self._name = self.__class__.__name__

    @abstractmethod
    def generate(self, config: UbunturouterConfig) -> GeneratorResult:
        """根据统一配置模型生成子系统配置文件

        Args:
            config: 完整的 UbunturouterConfig 模型

        Returns:
            GeneratorResult 包含成功/失败状态、消息和修改的文件列表
        """
        ...

    @property
    def name(self) -> str:
        return self._name

    # ─── 工具方法 ────────────────────────────────────────

    @staticmethod
    def write_file(path: Path, content: str) -> bool:
        """原子写入文件"""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(f"{path.suffix}.tmp")
            tmp.write_text(content, encoding="utf-8")
            tmp.replace(path)
            return True
        except Exception as e:
            logger.error("Failed to write %s: %s", path, e)
            return False

    @staticmethod
    def run_cmd(cmd: List[str], timeout: int = 30) -> dict:
        """运行系统命令"""
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return {
                "success": r.returncode == 0,
                "stdout": r.stdout.strip(),
                "stderr": r.stderr.strip(),
            }
        except FileNotFoundError:
            return {"success": False, "stdout": "", "stderr": f"Command not found: {cmd[0]}"}
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": "Timeout"}
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e)}

    @staticmethod
    def reload_service(service: str) -> bool:
        """重启或重载系统服务"""
        r = BaseGenerator.run_cmd(["systemctl", "reload-or-restart", service])
        return r["success"]

    @staticmethod
    def file_exists(path: Path) -> bool:
        return path.exists()

    def ok(self, message: str = "",
           files_modified: Optional[List[str]] = None) -> GeneratorResult:
        return GeneratorResult(
            generator_name=self._name,
            success=True,
            message=message or f"{self._name} completed",
            files_modified=files_modified or [],
        )

    def fail(self, message: str = "") -> GeneratorResult:
        return GeneratorResult(
            generator_name=self._name,
            success=False,
            message=message or f"{self._name} failed",
        )


# ─── Generator 注册 ──────────────────────────────────────────

_generator_registry: Dict[str, 'BaseGenerator'] = {}


def register_generator(generator_class: type) -> type:
    """注册 Generator 类（延迟实例化，首次访问时创建实例）"""
    # 创建一个工厂函数来实例化
    section = generator_class.SECTION

    def get_instance() -> 'BaseGenerator':
        if section not in _generator_registry:
            _generator_registry[section] = generator_class()
            logger.info("Generator instantiated: %s -> section '%s'",
                         generator_class.__name__, section)
        return _generator_registry[section]

    generator_class._get_instance = staticmethod(get_instance)
    logger.info("Generator class registered: %s -> section '%s'",
                 generator_class.__name__, section)
    return generator_class


def get_generator(section: str) -> Optional['BaseGenerator']:
    """按配置节名获取 Generator 实例"""
    if section not in _generator_registry:
        # 尝试触发注册
        return None
    return _generator_registry[section]


def list_generators() -> Dict[str, str]:
    """列出所有已注册的 Generator"""
    return {s: g.name for s, g in _generator_registry.items()}


def get_all_generators() -> List['BaseGenerator']:
    """获取所有已注册的 Generator 实例列表"""
    return list(_generator_registry.values())
