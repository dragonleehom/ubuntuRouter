"""规则编译器 — 流量编排规则编译与策略路由实现"""
import json
import logging
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Set

import yaml

from .app_db import AppDB

logger = logging.getLogger("ubunturouter.orchestrator.compiler")

RULES_PATH = Path("/opt/ubunturouter/data/orchestrator_rules.yaml")
NFTABLES_SET_BASE = "ubunturouter_app"
MARK_BASE = 1000  # 规则 mark 起始值

# 预定义路由表
ROUTING_TABLES = {
    "main": 254,
    "wan1": 100,
    "wan2": 200,
    "vpn": 300,
    "direct": 400,
    "bypass": 500,
}


@dataclass
class RuleMatch:
    """规则的匹配条件"""
    devices: List[str] = field(default_factory=list)      # MAC 地址列表
    apps: List[str] = field(default_factory=list)          # 应用名称列表
    ports: List[str] = field(default_factory=list)         # 端口列表 (如 "443", "80-443")
    protocols: List[str] = field(default_factory=list)     # 协议列表 (tcp/udp)
    src_ips: List[str] = field(default_factory=list)       # 源 IP 列表
    dst_ips: List[str] = field(default_factory=list)       # 目标 IP 列表

    def to_dict(self) -> Dict[str, Any]:
        return {
            "devices": self.devices,
            "apps": self.apps,
            "ports": self.ports,
            "protocols": self.protocols,
            "src_ips": self.src_ips,
            "dst_ips": self.dst_ips,
        }


@dataclass
class RuleAction:
    """规则的动作"""
    action: str = "route"         # route / bypass / drop
    target: str = ""              # wan1 / wan2 / vpn / direct
    table: int = 100              # 路由表 ID
    mark: int = 0                 # fwmark 值

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "target": self.target,
            "table": self.table,
            "mark": self.mark,
        }


@dataclass
class RuleSchedule:
    """规则的时间调度"""
    enabled: bool = False
    start_time: str = ""          # HH:MM
    end_time: str = ""            # HH:MM
    days: List[str] = field(default_factory=list)  # mon,tue,wed,thu,fri,sat,sun

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "days": self.days,
        }


@dataclass
class Rule:
    """流量编排规则"""
    id: str = ""
    name: str = ""
    description: str = ""
    enabled: bool = True
    priority: int = 1000
    match: RuleMatch = field(default_factory=RuleMatch)
    action: RuleAction = field(default_factory=RuleAction)
    schedule: RuleSchedule = field(default_factory=RuleSchedule)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "priority": self.priority,
            "match": self.match.to_dict(),
            "action": self.action.to_dict(),
            "schedule": self.schedule.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class RuleCompiler:
    """规则编译器

    将流量编排规则编译为 nftables 规则集 + ip rule + ip route 命令，
    执行策略路由实现。
    """

    def __init__(self):
        self._app_db = AppDB()
        self._app_sets: Set[str] = set()  # 已创建的应用 set
        self._next_mark = MARK_BASE
        self._applied_rules: Dict[str, Rule] = {}

    # ─── 规则编译 ──────────────────────────────────────────────

    def compile_rule(self, rule: Rule) -> List[str]:
        """将一条规则编译为系统命令列表

        Returns:
            需要执行的 shell 命令列表
        """
        commands: List[str] = []
        mark = rule.action.mark or self._get_next_mark()
        rule.action.mark = mark

        if rule.action.action == "bypass":
            # 跳过/直通 — 不标记，不路由
            return commands

        table_id = self._resolve_table(rule.action.target)

        # 1. nftables 规则: 匹配条件并设置 mark
        nft_cmds = self._build_nftables_rules(rule, mark)
        commands.extend(nft_cmds)

        # 2. ip rule: 根据 mark 选择路由表
        commands.append(
            f"ip rule add from all fwmark {mark} lookup {table_id} "
            f"priority {rule.priority}"
        )

        # 3. ip route: 确保路由表有默认路由（如果目标是指定 WAN）
        if rule.action.target in ("wan1", "wan2"):
            # 获取 WAN 接口的默认路由
            gateway = self._get_wan_gateway(rule.action.target)
            iface = self._get_wan_iface(rule.action.target)
            if gateway and iface:
                commands.append(
                    f"ip route add default via {gateway} dev {iface} "
                    f"table {table_id} 2>/dev/null || "
                    f"ip route replace default via {gateway} dev {iface} "
                    f"table {table_id}"
                )

        return commands

    def apply_rules(self, rules: List[Rule]) -> bool:
        """应用一组规则到系统

        1. 清理已有规则
        2. 按优先级排序
        3. 逐条编译并执行
        """
        try:
            # 先清理
            self._cleanup_all()

            # 排序（优先级数字越小越优先）
            sorted_rules = sorted(rules, key=lambda r: r.priority)

            for rule in sorted_rules:
                if not rule.enabled:
                    continue
                commands = self.compile_rule(rule)
                for cmd in commands:
                    self._execute(cmd)

                self._applied_rules[rule.id] = rule

            # 持久化
            self._persist_rules(rules)
            logger.info("Applied %d traffic steering rules", len(sorted_rules))
            return True
        except Exception as e:
            logger.error("Failed to apply rules: %s", e)
            return False

    def remove_rule(self, rule_id: str) -> bool:
        """删除已应用的规则"""
        if rule_id not in self._applied_rules:
            logger.warning("Rule %s not found in applied rules", rule_id)
            return False

        rule = self._applied_rules[rule_id]
        mark = rule.action.mark

        try:
            # 删除 ip rule
            self._execute(
                f"ip rule del from all fwmark {mark} 2>/dev/null || true"
            )

            # 删除 nftables 规则
            table_name = f"{NFTABLES_SET_BASE}_{rule_id}"
            self._execute(
                f"nft delete table inet {table_name} 2>/dev/null || true"
            )

            del self._applied_rules[rule_id]
            logger.info("Removed rule %s (%s)", rule_id, rule.name)
            return True
        except Exception as e:
            logger.error("Failed to remove rule %s: %s", rule_id, e)
            return False

    def validate_rule(self, rule: Rule) -> List[str]:
        """校验规则的合法性，返回错误信息列表"""
        errors: List[str] = []

        if not rule.id:
            errors.append("规则 ID 不能为空")
        if not rule.name:
            errors.append("规则名称不能为空")

        # 校验动作
        valid_actions = {"route", "bypass", "drop"}
        if rule.action.action not in valid_actions:
            errors.append(
                f"动作 '{rule.action.action}' 无效，"
                f"有效值: {', '.join(valid_actions)}"
            )

        # 校验目标
        if rule.action.action == "route":
            valid_targets = {"wan1", "wan2", "vpn", "direct"}
            if rule.action.target not in valid_targets:
                errors.append(
                    f"目标 '{rule.action.target}' 无效，"
                    f"有效值: {', '.join(valid_targets)}"
                )

        # 校验调度时间格式
        if rule.schedule.enabled:
            time_pattern = re.compile(r"^\d{2}:\d{2}$")
            if not time_pattern.match(rule.schedule.start_time):
                errors.append("开始时间格式无效 (需要 HH:MM)")
            if not time_pattern.match(rule.schedule.end_time):
                errors.append("结束时间格式无效 (需要 HH:MM)")

            valid_days = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
            for day in rule.schedule.days:
                if day not in valid_days:
                    errors.append(f"日期 '{day}' 无效")

        return errors

    # ─── 查询 ──────────────────────────────────────────────────

    def get_applied_rules(self) -> List[Rule]:
        """获取当前已应用的规则"""
        return list(self._applied_rules.values())

    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """获取指定规则"""
        return self._applied_rules.get(rule_id)

    # ─── 内部方法 ──────────────────────────────────────────────

    def _build_nftables_rules(self, rule: Rule, mark: int) -> List[str]:
        """构建 nftables 规则集"""
        cmds: List[str] = []
        table_name = f"{NFTABLES_SET_BASE}_{rule.id}"
        set_name = f"app_set_{rule.id}"

        # 创建表
        cmds.append(f"nft add table inet {table_name} 2>/dev/null || true")

        # 为应用匹配创建 set
        if rule.match.apps:
            ips: List[str] = []
            for app_name in rule.match.apps:
                app = self._app_db.get_by_name(app_name)
                if app and app.ips:
                    ips.extend(app.ips)

            if ips:
                cmds.append(
                    f"nft add set inet {table_name} {set_name} "
                    f"{{ type ipv4_addr\\; flags interval\\; }} "
                    f"2>/dev/null || true"
                )
                # 清空并添加元素
                cmds.append(f"nft flush set inet {table_name} {set_name}")
                for cidr in ips:
                    cmds.append(
                        f"nft add element inet {table_name} {set_name} "
                        f"{{ {cidr} }}"
                    )

        # 构建匹配表达式
        match_expr = self._build_match_expression(rule, set_name)

        # 添加规则: 匹配后设置 mark
        cmds.append(
            f"nft add rule inet {table_name} forward {match_expr} "
            f"meta mark set {mark} accept"
        )

        return cmds

    def _build_match_expression(self, rule: Rule, set_name: str) -> str:
        """构建 nftables 匹配表达式"""
        parts: List[str] = []

        # 设备匹配 (MAC)
        if rule.match.devices:
            mac_match = " || ".join(
                f"ether saddr {mac}" for mac in rule.match.devices
            )
            parts.append(f"({mac_match})")

        # 应用匹配 (目标 IP)
        if rule.match.apps:
            parts.append(f"ip daddr @{set_name}")

        # 端口匹配
        if rule.match.ports:
            port_match = " || ".join(
                f"th dport {{{p}}}" for p in rule.match.ports
            )
            parts.append(f"({port_match})")

        # 协议匹配
        if rule.match.protocols:
            proto_match = " || ".join(
                f"meta l4proto {p}" for p in rule.match.protocols
            )
            parts.append(f"({proto_match})")

        # 源 IP
        if rule.match.src_ips:
            src_match = " || ".join(
                f"ip saddr {ip}" for ip in rule.match.src_ips
            )
            parts.append(f"({src_match})")

        # 目标 IP
        if rule.match.dst_ips:
            dst_match = " || ".join(
                f"ip daddr {ip}" for ip in rule.match.dst_ips
            )
            parts.append(f"({dst_match})")

        return " && ".join(parts) if parts else ""

    def _resolve_table(self, target: str) -> int:
        """根据目标名称获取路由表 ID"""
        return ROUTING_TABLES.get(target, 254)

    def _get_next_mark(self) -> int:
        """获取下一个可用的 mark 值"""
        mark = self._next_mark
        self._next_mark += 1
        return mark

    def _get_wan_gateway(self, wan_name: str) -> str:
        """获取 WAN 接口的网关 IP"""
        try:
            routes = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True, text=True, timeout=5,
            )
            for line in routes.stdout.strip().split("\n"):
                parts = line.split()
                if "dev" in parts:
                    idx = parts.index("dev")
                    if idx + 1 < len(parts) and parts[idx + 1] == wan_name:
                        if "via" in parts:
                            via_idx = parts.index("via")
                            return parts[via_idx + 1]
        except Exception:
            pass
        return ""

    def _get_wan_iface(self, wan_name: str) -> str:
        """获取 WAN 接口名称"""
        # 默认 wan1=eth0, wan2=eth1
        mapping = {"wan1": "eth0", "wan2": "eth1"}
        return mapping.get(wan_name, wan_name)

    def _cleanup_all(self) -> None:
        """清理所有已应用的规则"""
        # 清理 nftables 表
        try:
            r = subprocess.run(
                ["nft", "list", "tables", "inet"],
                capture_output=True, text=True, timeout=5,
            )
            for line in r.stdout.strip().split("\n"):
                table = line.strip()
                if table.startswith(NFTABLES_SET_BASE):
                    self._execute(f"nft delete table inet {table}")
        except Exception:
            pass

        # 清理 ip rule (只清理我们添加的)
        self._applied_rules.clear()
        logger.info("Cleaned up all applied rules")

    def _execute(self, cmd: str) -> bool:
        """执行 shell 命令"""
        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=10
            )
            if r.returncode != 0 and r.stderr.strip():
                # 忽略某些已知的警告
                stderr = r.stderr.strip()
                if "File exists" not in stderr and "No such file" not in stderr:
                    logger.warning("Command '%s' stderr: %s", cmd, stderr)
            return r.returncode == 0
        except subprocess.TimeoutExpired:
            logger.error("Command timed out: %s", cmd)
            return False
        except Exception as e:
            logger.error("Command failed '%s': %s", cmd, e)
            return False

    def _persist_rules(self, rules: List[Rule]) -> None:
        """持久化规则到 YAML"""
        try:
            RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = [r.to_dict() for r in rules]
            with open(RULES_PATH, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False,
                          allow_unicode=True, sort_keys=False)
        except OSError as e:
            logger.error("Failed to persist rules: %s", e)

    def load_rules(self) -> List[Rule]:
        """从持久化文件加载规则"""
        rules: List[Rule] = []
        try:
            if RULES_PATH.exists():
                with open(RULES_PATH, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if isinstance(data, list):
                    for item in data:
                        match_data = item.get("match", {})
                        action_data = item.get("action", {})
                        schedule_data = item.get("schedule", {})

                        rule = Rule(
                            id=item.get("id", ""),
                            name=item.get("name", ""),
                            description=item.get("description", ""),
                            enabled=item.get("enabled", True),
                            priority=item.get("priority", 1000),
                            match=RuleMatch(
                                devices=match_data.get("devices", []),
                                apps=match_data.get("apps", []),
                                ports=match_data.get("ports", []),
                                protocols=match_data.get("protocols", []),
                                src_ips=match_data.get("src_ips", []),
                                dst_ips=match_data.get("dst_ips", []),
                            ),
                            action=RuleAction(
                                action=action_data.get("action", "route"),
                                target=action_data.get("target", ""),
                                table=action_data.get("table", 100),
                                mark=action_data.get("mark", 0),
                            ),
                            schedule=RuleSchedule(
                                enabled=schedule_data.get("enabled", False),
                                start_time=schedule_data.get("start_time", ""),
                                end_time=schedule_data.get("end_time", ""),
                                days=schedule_data.get("days", []),
                            ),
                            created_at=item.get("created_at", ""),
                            updated_at=item.get("updated_at", ""),
                        )
                        rules.append(rule)
        except Exception as e:
            logger.error("Failed to load rules: %s", e)
        return rules
