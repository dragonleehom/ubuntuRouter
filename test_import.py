#!/usr/bin/env python3
"""Sprint 1 快速验证脚本"""
import sys, tempfile, os
from pathlib import Path
sys.path.insert(0, 'src')

print("=== 测试 1: 模型导入 ===")
from ubunturouter.config.models import (
    UbunturouterConfig, InterfaceConfig, InterfaceRole,
    IPConfig, IPMethod, DHCPPoolConfig, DNSConfig,
    FirewallConfig, RoutingConfig, SystemConfig,
)
print("  All models imported")

print("\n=== 测试 2: 创建配置 ===")
config = UbunturouterConfig(
    interfaces=[
        InterfaceConfig(name="eth0", device="eth0", role=InterfaceRole.WAN,
                        ipv4=IPConfig(method=IPMethod.DHCP)),
        InterfaceConfig(name="eth1", device="eth1", role=InterfaceRole.LAN,
                        ipv4=IPConfig(method=IPMethod.STATIC, address="192.168.21.1/24")),
    ],
    dhcp=DHCPPoolConfig(interface="eth1", range_start="192.168.21.50", range_end="192.168.21.200"),
)
print("  Config created")

print("\n=== 测试 3: 序列化 ===")
from ubunturouter.config.serializer import ConfigSerializer
yaml_str = ConfigSerializer.to_yaml(config)
print(f"  YAML ({len(yaml_str)} chars):")
print(yaml_str[:300])

print("\n=== 测试 4: 配置引擎 ===")
from ubunturouter.engine.engine import ConfigEngine
with tempfile.TemporaryDirectory() as tmpdir:
    cfg_path = Path(tmpdir) / "config.yaml"
    engine = ConfigEngine(config_path=cfg_path)
    engine.save(config)
    print(f"  Config saved to {cfg_path}")
    loaded = engine.load()
    assert loaded.interfaces[0].role == InterfaceRole.WAN
    print(f"  Config loaded and verified: {len(loaded.interfaces)} interfaces")

print("\n=== 测试 5: 配置差异 ===")
diff = engine.diff(config)
print(f"  Diff computed: changed={diff.has_changes}, sections={diff.changed_sections}")

print("\n=== 全部通过! ===")
