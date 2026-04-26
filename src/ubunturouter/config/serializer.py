"""配置序列化：YAML 读写 + 原子写入"""

import os
import tempfile
import yaml
from pathlib import Path
from typing import Optional
from enum import Enum

from .models import UbunturouterConfig


class ConfigSerializer:
    """配置序列化器"""

    @staticmethod
    def to_yaml(config: UbunturouterConfig) -> str:
        """将配置对象序列化为 YAML 字符串"""
        return yaml.dump(
            config.model_dump(mode='json', exclude_none=True),
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            indent=2
        )

    @staticmethod
    def from_yaml(content: str) -> UbunturouterConfig:
        """从 YAML 字符串反序列化为配置对象"""
        data = yaml.safe_load(content)
        if data is None:
            raise ValueError("配置为空")
        return UbunturouterConfig(**data)

    @staticmethod
    def from_yaml_file(path: Path) -> UbunturouterConfig:
        """从 YAML 文件加载配置"""
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {path}")
        content = path.read_text(encoding='utf-8')
        return ConfigSerializer.from_yaml(content)

    @staticmethod
    def atomic_write(path: Path, content: str) -> None:
        """
        原子写入（write-then-rename）
        
        先写入临时文件，然后 rename 到目标路径。
        确保不会出现半写状态。
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(path.parent),
            prefix=f'.{path.name}.',
            suffix='.tmp'
        )
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(content)
                f.flush()
                os.fsync(fd)  # 确保数据刷到磁盘
            os.replace(tmp_path, str(path))
        except:
            # 写入失败，清理临时文件
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    @staticmethod
    def atomic_write_config(path: Path, config: UbunturouterConfig) -> None:
        """原子写入配置对象到 YAML 文件"""
        yaml_str = ConfigSerializer.to_yaml(config)
        ConfigSerializer.atomic_write(path, yaml_str)
