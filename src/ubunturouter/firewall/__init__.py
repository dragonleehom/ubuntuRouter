"""UbuntuRouter 防火墙管理器 — 直接操作 nftables 运行时状态"""
import subprocess
import json
import re
from pathlib import Path
from typing import List, Optional, Dict
from dataclasses import dataclass, field


NFT_TABLE = "ubunturouter"
NFT_BINARY = "/usr/sbin/nft"


@dataclass
class ConntrackEntry:
    protocol: str
    src_ip: str
    src_port: int
    dst_ip: str
    dst_port: int
    state: str
    bytes_in: int = 0
    bytes_out: int = 0


@dataclass
class FirewallRuleEntry:
    handle: int
    family: str
    table: str
    chain: str
    rule: str  # nftables 规则字符串
    counter_packets: int = 0
    counter_bytes: int = 0


@dataclass
class NftablesStats:
    rules: List[FirewallRuleEntry] = field(default_factory=list)
    tables: List[str] = field(default_factory=list)
    chains: Dict[str, List[str]] = field(default_factory=dict)


class FirewallManager:
    """运行时防火墙状态管理器 — 读取 nftables 当前状态"""

    def __init__(self):
        self._nft = NFT_BINARY

    # ─── nftables 运行时状态 ────────────────────────────────

    def get_stats(self) -> NftablesStats:
        """获取当前 nftables 完整状态"""
        stats = NftablesStats()

        try:
            r = subprocess.run(
                [self._nft, "-j", "list", "ruleset"],
                capture_output=True, text=True, timeout=10
            )
            if r.returncode != 0:
                return stats
            data = json.loads(r.stdout)
        except Exception:
            return stats

        for table in data.get("nftables", []):
            if "metainfo" in table:
                continue
            if "table" in table:
                t = table["table"]
                name = f"{t.get('family', 'inet')} {t.get('name', '')}"
                stats.tables.append(name)
            if "chain" in table:
                c = table["chain"]
                chain_name = f"{c.get('family', 'inet')} {c.get('table', '')} {c.get('name', '')}"
                if c.get('table') not in stats.chains:
                    stats.chains[c['table']] = []
                stats.chains[c['table']].append(c.get('name', ''))
            if "rule" in table:
                r = table["rule"]
                handle = r.get("handle", 0)
                # 提取计数器
                pkts = 0
                bytes_ = 0
                expr_list = r.get("expr", [])
                for expr in expr_list:
                    if "counter" in expr:
                        pkts = expr["counter"].get("packets", 0)
                        bytes_ = expr["counter"].get("bytes", 0)
                stats.rules.append(FirewallRuleEntry(
                    handle=handle,
                    family=r.get("family", "inet"),
                    table=r.get("table", ""),
                    chain=r.get("chain", ""),
                    rule=self._rule_to_text(r.get("expr", [])),
                    counter_packets=pkts,
                    counter_bytes=bytes_,
                ))

        return stats

    def get_rule_by_handle(self, handle: int, table: str = NFT_TABLE,
                           family: str = "inet") -> Optional[FirewallRuleEntry]:
        """按 handle 获取单条规则"""
        stats = self.get_stats()
        for rule in stats.rules:
            if rule.handle == handle and rule.table == table and rule.family == family:
                return rule
        return None

    def add_rule(self, chain: str, rule_expr: str, position: Optional[str] = None,
                 table: str = NFT_TABLE, family: str = "inet") -> bool:
        """动态添加一条 nftables 规则"""
        cmd = [self._nft, "add", "rule", family, table, chain]
        if position:
            cmd += [position]
        cmd += rule_expr.split()
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return r.returncode == 0
        except Exception:
            return False

    def delete_rule(self, handle: int, chain: str,
                    table: str = NFT_TABLE, family: str = "inet") -> bool:
        """删除指定 handle 的规则"""
        try:
            r = subprocess.run(
                [self._nft, "delete", "rule", family, table, chain, f"handle {handle}"],
                capture_output=True, text=True, timeout=10
            )
            return r.returncode == 0
        except Exception:
            return False

    def flush_chain(self, chain: str, table: str = NFT_TABLE,
                    family: str = "inet") -> bool:
        """清空某条链"""
        try:
            r = subprocess.run(
                [self._nft, "flush", "chain", family, table, chain],
                capture_output=True, text=True, timeout=10
            )
            return r.returncode == 0
        except Exception:
            return False

    # ─── Conntrack 状态 ────────────────────────────────────

    def get_conntrack(self, limit: int = 100) -> List[ConntrackEntry]:
        """获取 conntrack 连接跟踪状态"""
        entries = []
        try:
            r = subprocess.run(
                ["conntrack", "-L", "-o", "extended", "--count"],
                capture_output=True, text=True, timeout=10
            )
            # conntrack 可能不存在
            if r.returncode != 0:
                return entries

            r = subprocess.run(
                ["conntrack", "-L", "-o", "json"],
                capture_output=True, text=True, timeout=10
            )
            if r.returncode != 0:
                return entries
            data = json.loads(r.stdout)
            for entry in data.get("entries", [])[:limit]:
                entries.append(ConntrackEntry(
                    protocol=entry.get("proto", ""),
                    src_ip=entry.get("src", ""),
                    src_port=entry.get("sport", 0),
                    dst_ip=entry.get("dst", ""),
                    dst_port=entry.get("dport", 0),
                    state=entry.get("state", ""),
                    bytes_in=entry.get("bytes", 0),
                    bytes_out=entry.get("bytes", 0),
                ))
        except Exception:
            pass
        return entries

    def flush_conntrack(self) -> bool:
        """清空 conntrack 表"""
        try:
            subprocess.run(
                ["conntrack", "-F"],
                capture_output=True, text=True, timeout=10
            )
            return True
        except Exception:
            return False

    # ─── 端口转发快捷操作 ──────────────────────────────────

    def add_port_forward(self, name: str, from_zone: str, from_port: int,
                         to_ip: str, to_port: int, protocol: str = "tcp",
                         iface: str = "") -> bool:
        """动态添加端口转发 DNAT 规则"""
        success = True
        nft = self._nft

        # 确保 nat 表存在
        try:
            subprocess.run([nft, "add", "table", "inet", "nat"],
                           capture_output=True, text=True, timeout=5)
            subprocess.run([nft, "add", "chain", "inet", "nat", "prerouting",
                           '{ type nat hook prerouting priority -100; }'],
                           capture_output=True, text=True, timeout=5)
        except Exception:
            pass

        # Forward chain (inet ubunturouter): 放行转发的流量
        fwd_rule = f"{protocol} dport {from_port} ct state new counter accept"
        if iface:
            fwd_rule = f"iif {iface} {fwd_rule}"
        if not self.add_rule("forward", fwd_rule):
            success = False

        # Prerouting DNAT (inet nat): 目标地址转换
        dnat_rule = f"{protocol} dport {from_port} dnat ip to {to_ip}:{to_port}"
        if iface:
            dnat_rule = f"iif {iface} {dnat_rule}"
        try:
            cmd = [nft, "add", "rule", "inet", "nat", "prerouting"] + dnat_rule.split()
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if r.returncode != 0:
                success = False
        except Exception:
            success = False

        return success

    # ─── 辅助 ──────────────────────────────────────────────

    def _rule_to_text(self, expr_list: List[Dict]) -> str:
        """将 JSON expr 转成可读文本"""
        parts = []
        for expr in expr_list:
            if "match" in expr:
                m = expr["match"]
                left = m.get("left", {})
                right = m.get("right", {})
                op = m.get("op", "")
                # 提取 payload / meta
                payload = left.get("payload", {})
                if payload:
                    field = f"{payload.get('protocol', '')} {payload.get('field', '')}"
                else:
                    field = left.get("meta", {}).get("key", "") or json.dumps(left)
                val = right.get("set", [right.get("value", "")])[0] if isinstance(right.get("set"), list) else right.get("value", "")
                parts.append(f"{field} {op} {val}")
            elif "counter" in expr:
                c = expr["counter"]
                parts.append(f"counter packets {c.get('packets', 0)} bytes {c.get('bytes', 0)}")
            elif "accept" in expr:
                parts.append("accept")
            elif "drop" in expr:
                parts.append("drop")
            elif "reject" in expr:
                parts.append("reject")
            elif "log" in expr:
                parts.append("log")
            elif "masquerade" in expr:
                parts.append("masquerade")
            elif "dnat" in expr:
                d = expr["dnat"]
                addr = d.get("addr", "")
                port = d.get("port", "")
                parts.append(f"dnat to {addr}:{port}")
            elif "snat" in expr:
                s = expr["snat"]
                addr = s.get("addr", "")
                parts.append(f"snat to {addr}")
        return " ".join(parts)

    def table_exists(self, table: str = NFT_TABLE, family: str = "inet") -> bool:
        try:
            r = subprocess.run(
                [self._nft, "list", "table", family, table],
                capture_output=True, text=True, timeout=5
            )
            return r.returncode == 0
        except Exception:
            return False

    def ensure_table(self, table: str = NFT_TABLE, family: str = "inet") -> bool:
        """确保 nftables 表存在"""
        if not self.table_exists(table, family):
            try:
                subprocess.run(
                    [self._nft, "add", "table", family, table],
                    capture_output=True, text=True, timeout=5
                )
                return True
            except Exception:
                return False
        return True
