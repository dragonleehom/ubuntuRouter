#!/usr/bin/env python3
"""Sprint 1 集成测试 — 完整链路验证（在 VM 上运行）"""
import sys
sys.path.insert(0, 'src')

import os
import tempfile
from pathlib import Path

print("=" * 60)
print("Sprint 1 集成测试 — 完整链路")
print("=" * 60)

# ─── 1. 模型导入 ────────────────────────────────────────
print("\n=== 1. 模型导入 ===")
from ubunturouter.config.models import (
    UbunturouterConfig, InterfaceConfig, InterfaceRole, InterfaceType,
    IPConfig, IPMethod, DHCPPoolConfig, DNSConfig,
    FirewallConfig, FirewallZoneConfig, FirewallPolicy,
    RoutingConfig, SystemConfig,
)
print("  ✅ 模型导入成功")

# ─── 2. 构建完整配置 ─────────────────────────────────────
print("\n=== 2. 构建配置 ===")
config = UbunturouterConfig(
    system=SystemConfig(hostname="ubunturouter-test"),
    interfaces=[
        InterfaceConfig(
            name="eth0", device="eth0",
            type=InterfaceType.ETHERNET,
            role=InterfaceRole.WAN,
            ipv4=IPConfig(method=IPMethod.DHCP),
            firewall_zone="wan",
        ),
        InterfaceConfig(
            name="eth1", device="eth1",
            type=InterfaceType.ETHERNET,
            role=InterfaceRole.LAN,
            ipv4=IPConfig(method=IPMethod.STATIC, address="192.168.21.1/24"),
            firewall_zone="lan",
        ),
    ],
    firewall=FirewallConfig(zones={
        "wan": FirewallZoneConfig(name="wan", masquerade=True, input=FirewallPolicy.DROP, forward_to=["lan"]),
        "lan": FirewallZoneConfig(name="lan", masquerade=False, input=FirewallPolicy.ACCEPT, forward_to=["wan"]),
    }),
    dhcp=DHCPPoolConfig(interface="eth1", range_start="192.168.21.50", range_end="192.168.21.200"),
    dns=DNSConfig(),
)
print("  ✅ 配置构建成功")

# ─── 3. 序列化与反序列化 ─────────────────────────────────
print("\n=== 3. 序列化 ===")
from ubunturouter.config.serializer import ConfigSerializer
yaml_str = ConfigSerializer.to_yaml(config)
loaded = ConfigSerializer.from_yaml(yaml_str)
assert loaded.interfaces[0].role == InterfaceRole.WAN
print(f"  ✅ 序列化/反序列化成功 ({len(yaml_str)} chars)")

# ─── 4. 配置引擎 ─────────────────────────────────────────
print("\n=== 4. 配置引擎 ===")
from ubunturouter.engine.engine import ConfigEngine
with tempfile.TemporaryDirectory() as tmpdir:
    cfg_path = Path(tmpdir) / "config.yaml"
    engine = ConfigEngine(config_path=cfg_path)
    engine.save(config)
    loaded = engine.load()
    assert len(loaded.interfaces) == 2
    print(f"  ✅ 引擎保存/加载成功")
    
    diff = engine.diff(config)
    print(f"  ✅ Diff: changed={diff.has_changes}, sections={diff.changed_sections}")

# ─── 5. 生成器 ───────────────────────────────────────────
print("\n=== 5. 生成器 ===")
from ubunturouter.generators.netplan import NetplanGenerator
from ubunturouter.generators.nftables import NftablesGenerator
from ubunturouter.generators.dnsmasq import DnsmasqGenerator

netplan = NetplanGenerator()
gen_netplan = netplan.generate(config)
for path, content in gen_netplan.items():
    print(f"  ✅ Netplan -> {path}")
    # 验证是合法 YAML
    import yaml
    yaml.safe_load(content)

nftables = NftablesGenerator()
gen_nft = nftables.generate(config)
for path, content in gen_nft.items():
    print(f"  ✅ Nftables -> {path}")

dnsmasq = DnsmasqGenerator()
gen_dns = dnsmasq.generate(config)
for path, content in gen_dns.items():
    print(f"  ✅ Dnsmasq -> {path}")

# ─── 6. Registry ─────────────────────────────────────────
print("\n=== 6. Generator Registry ===")
from ubunturouter.generators.base import GeneratorRegistry
registry = GeneratorRegistry()
registry.register("netplan", netplan)
registry.register("nftables", nftables)
registry.register("dnsmasq", dnsmasq)
all_gen = registry.generate_all(config)
assert len(all_gen) == 3
print(f"  ✅ Registry: {len(all_gen)} generators")

# ─── 7. 文件锁 ───────────────────────────────────────────
print("\n=== 7. 文件锁 ===")
from ubunturouter.engine.lock import EngineLock
with tempfile.TemporaryDirectory() as tmpdir:
    lock_path = Path(tmpdir) / "test.lock"
    with EngineLock(lock_path=lock_path):
        pass
    print(f"  ✅ 文件锁工作正常")

# ─── 8. 回滚管理器 ───────────────────────────────────────
print("\n=== 8. 回滚管理器 ===")
from ubunturouter.engine.rollback import RollbackManager
with tempfile.TemporaryDirectory() as tmpdir:
    rollback = RollbackManager(snapshot_dir=Path(tmpdir))
    sid = rollback.create_snapshot(config, summary="Test snapshot")
    assert sid is not None
    print(f"  ✅ 快照创建成功: {sid}")
    
    snapshots = rollback.list_snapshots()
    assert len(snapshots) >= 1
    print(f"  ✅ 快照列表: {len(snapshots)}")

# ─── 9. 初始化器 ─────────────────────────────────────────
print("\n=== 9. 初始化器 ===")
from ubunturouter.engine.initializer import Initializer
print(f"  ✅ 初始化器模块导入成功")

# ─── 10. CLI 导入 ────────────────────────────────────────
print("\n=== 10. CLI 入口 ===")
from ubunturouter.cli.main import main, cmd_status, cmd_init, cmd_doctor, cmd_view, cmd_apply, cmd_snapshots, cmd_rollback
print(f"  ✅ CLI 所有命令导入成功")

# ─── 总结果 ──────────────────────────────────────────────
print("\n" + "=" * 60)
print("所有测试通过! ✅")
print("=" * 60)
