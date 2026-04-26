"""Generator 基类 + GeneratorRegistry"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from pathlib import Path
from ..config.models import UbunturouterConfig


class ConfigGenerator(ABC):
    """配置生成器基类"""

    @abstractmethod
    def generate(self, config: UbunturouterConfig) -> Dict[str, str]:
        """
        从统一配置生成子系统配置文件。
        返回 {目标路径: 文件内容} 的字典。
        """

    def validate_generated(self, content: str) -> Optional[str]:
        """验证生成的内容是否合法。返回 None=通过，str=错误信息"""
        return None

    def reload_command(self) -> List[str]:
        """重启/重载服务的命令列表"""
        return []

    def reload_delay(self) -> int:
        """reload 后的等待时间（毫秒）"""
        return 0


class GeneratorRegistry:
    """生成器注册中心"""

    def __init__(self):
        self._generators: Dict[str, ConfigGenerator] = {}

    def register(self, name: str, generator: ConfigGenerator) -> None:
        self._generators[name] = generator

    def get(self, name: str) -> Optional[ConfigGenerator]:
        return self._generators.get(name)

    def all(self) -> Dict[str, ConfigGenerator]:
        return dict(self._generators)

    def generate_all(self, config: UbunturouterConfig) -> Dict[str, Dict[str, str]]:
        """调用所有注册的生成器，返回 {generator_name: {path: content}}"""
        result = {}
        for name, gen in self._generators.items():
            result[name] = gen.generate(config)
        return result
