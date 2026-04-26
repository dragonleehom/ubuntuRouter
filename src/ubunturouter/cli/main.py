"""urctl CLI — UbuntuRouter 命令行管理工具"""

import sys
import os
import argparse
import json
from pathlib import Path
from typing import Optional

# 确保能找到包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def get_engine() -> ...:
    """获取配置引擎实例"""
    from ubunturouter.engine.engine import ConfigEngine
    return ConfigEngine()


def get_registry():
    """获取注册了所有生成器的 registry"""
    from ubunturouter.generators.base import GeneratorRegistry
    from ubunturouter.generators.netplan import NetplanGenerator
    from ubunturouter.generators.nftables import NftablesGenerator
    from ubunturouter.generators.dnsmasq import DnsmasqGenerator

    registry = GeneratorRegistry()
    registry.register("netplan", NetplanGenerator())
    registry.register("nftables", NftablesGenerator())
    registry.register("dnsmasq", DnsmasqGenerator())
    return registry


# ─── 命令实现 ────────────────────────────────────────────


def cmd_init(args):
    """初始化系统"""
    from ubunturouter.engine.initializer import Initializer

    engine = get_engine()
    init = Initializer(engine)

    if not init.should_init():
        print("系统已经初始化，跳过。如需重新初始化请删除 /etc/ubunturouter/config.yaml")
        return 0

    print("🔍 检测物理网口...")
    nics = init.detect_physical_nics()
    print(f"   发现 {len(nics)} 个物理网口: {[n.name for n in nics]}")

    print("  📋 分配 WAN/LAN 角色...")
    assignment = init.auto_assign_roles(nics)
    if assignment.wanlan:
        print(f"   单网口模式: {assignment.wanlan.name} (WAN+LAN)")
    else:
        print(f"   WAN: {assignment.wan.name if assignment.wan else '无'}")
        print(f"   LAN: {[l.name for l in assignment.lans]}")

    print("  📝 生成初始配置...")
    config = init.generate_initial_config(assignment)

    print("  🚀 Apply 配置...")
    try:
        init.apply_and_start_wizard()
        print("  ✅ 初始化完成!")
        print(f"  🌐 LAN 网关: {assignment.gateway}")
        print(f"  📡 DHCP: {config.dhcp.range_start} - {config.dhcp.range_end}")
        return 0
    except Exception as e:
        print(f"  ❌ 初始化失败: {e}")
        return 1


def cmd_status(args):
    """显示系统状态"""
    engine = get_engine()

    if not engine.exists():
        print("系统未初始化。运行 'urctl init' 初始化。")
        return 1

    config = engine.load()

    print("=== UbuntuRouter 状态 ===")
    print(f"  系统版本: v1.0")
    print(f"  主机名:    {config.system.hostname}")
    print()

    # 接口状态
    print(f"  接口 ({len(config.interfaces)}):")
    for iface in config.interfaces:
        role_str = iface.role.value.upper()
        ip_str = iface.ipv4.address if iface.ipv4 and iface.ipv4.address else (
            "DHCP" if iface.ipv4 and iface.ipv4.method == IPMethod.DHCP else "未配置"
        )
        print(f"    {iface.name:12} {role_str:8} {iface.type.value:10} {ip_str}")

    print()
    if config.dhcp:
        print(f"  DHCP: {config.dhcp.range_start} - {config.dhcp.range_end} ({config.dhcp.lease_time}s)")
    if config.dns:
        print(f"  DNS: {', '.join(config.dns.upstream)}")

    # 防火墙
    print()
    print(f"  防火墙 Zones ({len(config.firewall.zones)}):")
    for zone in config.firewall.zones:
        masq = "MASQ" if zone.masquerade else ""
        print(f"    {zone.name:12} in={zone.input.value:8} fwd={zone.forward_to} {masq}")

    return 0


def cmd_doctor(args):
    """诊断系统"""
    engine = get_engine()
    issues = []

    print("=== UbuntuRouter 诊断 ===")
    print()

    # 1. 配置文件
    from ubunturouter.engine.engine import CONFIG_PATH as config_path
    if config_path.exists():
        print(f"  ✅ config.yaml 存在: {config_path}")
    else:
        issues.append("配置文件不存在")
        print(f"  ❌ config.yaml 不存在")

    # 2. 系统服务
    services = ["dnsmasq", "nftables"]
    for svc in services:
        try:
            import subprocess
            r = subprocess.run(["systemctl", "is-active", svc],
                               capture_output=True, text=True, timeout=5)
            status = r.stdout.strip()
            if status == "active":
                print(f"  ✅ {svc}: {status}")
            else:
                print(f"  ⚠ {svc}: {status}")
                issues.append(f"{svc} 服务未运行")
        except Exception as e:
            print(f"  ❌ {svc}: 检查失败 ({e})")
            issues.append(f"无法检查 {svc}")

    # 3. 网口状态
    try:
        r = subprocess.run(["ip", "link", "show"],
                           capture_output=True, text=True, timeout=5)
        for line in r.stdout.split("\n"):
            if "state UP" in line or "state DOWN" in line:
                iface = line.split(":")[1].strip() if ":" in line else "?"
                state = "UP" if "UP" in line else "DOWN"
                print(f"  {'✅' if state == 'UP' else '❌'} {iface:12} {state}")
                if state == "DOWN":
                    issues.append(f"网口 {iface} 未激活")
    except Exception as e:
        print(f"  ❌ 网口检查失败: {e}")

    print()
    if issues:
        print(f"⚠ 发现 {len(issues)} 个问题:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        return 1
    else:
        print("✅ 一切正常!")
        return 0


def cmd_view(args):
    """查看当前配置"""
    engine = get_engine()
    if not engine.exists():
        print("系统未初始化")
        return 1

    from ubunturouter.config.serializer import ConfigSerializer
    config = engine.load()
    yaml_str = ConfigSerializer.to_yaml(config)
    print(yaml_str)
    return 0


def cmd_apply(args):
    """Apply 配置变更"""
    from ubunturouter.engine.applier import ConfigApplier

    engine = get_engine()
    if not engine.exists():
        print("系统未初始化。运行 'urctl init' 初始化。")
        return 1

    # 从文件加载新配置
    config_file = args.file
    if config_file:
        from ubunturouter.config.serializer import ConfigSerializer
        config = ConfigSerializer.from_yaml_file(Path(config_file))
    else:
        # 从 stdin 读取
        import sys
        yaml_input = sys.stdin.read()
        from ubunturouter.config.serializer import ConfigSerializer
        config = ConfigSerializer.from_yaml(yaml_input)

    print(f"  📋 校验配置...")
    validation = engine.validate(config)
    if validation.errors:
        print("  ❌ 校验失败:")
        for err in validation.errors:
            print(f"     - {err}")
        return 1

    registry = get_registry()
    applier = ConfigApplier(engine, registry)
    print(f"  🚀 Apply 中...")
    result = applier.apply_atomic(config, auto_rollback=not args.no_rollback)

    if result.success:
        print(f"  ✅ Apply 成功!")
        for sr in result.service_results:
            status = "✅" if sr.success else "⚠"
            print(f"    {status} {sr.name}: {sr.duration_ms}ms")
        if result.changed_sections:
            print(f"  变更: {', '.join(result.changed_sections)}")
        if result.snapshot_id:
            print(f"  快照: {result.snapshot_id}")
        return 0
    else:
        print(f"  ❌ Apply 失败: {result.error}")
        if result.rollback_to:
            print(f"  已回滚到快照: {result.rollback_to}")
        return 1


def cmd_snapshots(args):
    """管理快照"""
    from ubunturouter.engine.rollback import RollbackManager

    rollback = RollbackManager()
    snapshots = rollback.list_snapshots()

    if not snapshots:
        print("没有快照")
        return 0

    for snap in snapshots:
        good = "✅" if snap.get("good") else " "
        created = snap.get("created_at", "?")[:19]
        summary = snap.get("summary", "?")
        sid = snap.get("snapshot_id", "?")
        print(f"  {good} {created} {sid[:20]:20} {summary}")

    return 0


def cmd_rollback(args):
    """回滚到指定快照"""
    from ubunturouter.engine.rollback import RollbackManager

    rollback = RollbackManager()
    if args.snapshot_id:
        success = rollback.auto_rollback(args.snapshot_id)
        if success:
            print(f"  ✅ 已回滚到快照: {args.snapshot_id}")
            return 0
        else:
            print(f"  ❌ 回滚失败")
            return 1
    else:
        # 回滚到 latest
        snapshots = rollback.list_snapshots()
        if not snapshots:
            print("没有可回滚的快照")
            return 1
        latest = snapshots[0]
        sid = latest.get("snapshot_id", "")
        if rollback.auto_rollback(sid):
            print(f"  ✅ 已回滚到最近快照: {sid}")
            return 0
        print("  ❌ 回滚失败")
        return 1


# ─── CLI 主入口 ──────────────────────────────────────────


def main():
    from ubunturouter.config.models import IPMethod

    parser = argparse.ArgumentParser(
        description="UbuntuRouter — 配置管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.set_defaults(func=lambda _: parser.print_help())

    subparsers = parser.add_subparsers(title="命令", dest="command")

    # init
    p_init = subparsers.add_parser("init", help="初始化系统")
    p_init.set_defaults(func=cmd_init)

    # status
    p_status = subparsers.add_parser("status", help="显示系统状态")
    p_status.set_defaults(func=cmd_status)

    # doctor
    p_doctor = subparsers.add_parser("doctor", help="诊断系统")
    p_doctor.set_defaults(func=cmd_doctor)

    # view
    p_view = subparsers.add_parser("view", help="查看当前配置 (YAML)")
    p_view.set_defaults(func=cmd_view)

    # apply
    p_apply = subparsers.add_parser("apply", help="Apply 新配置 (从文件或 stdin)")
    p_apply.add_argument("-f", "--file", help="从 YAML 文件读取配置")
    p_apply.add_argument("--no-rollback", action="store_true", help="禁用自动回滚")
    p_apply.set_defaults(func=cmd_apply)

    # snapshots
    p_snap = subparsers.add_parser("snapshots", help="列出快照")
    p_snap.set_defaults(func=cmd_snapshots)

    # rollback
    p_rb = subparsers.add_parser("rollback", help="回滚到快照")
    p_rb.add_argument("snapshot_id", nargs="?", help="快照 ID（缺省=最近）")
    p_rb.set_defaults(func=cmd_rollback)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
