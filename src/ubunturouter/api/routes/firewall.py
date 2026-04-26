"""防火墙 API 路由 — Zones + 端口转发 + 规则 + 状态"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from ..deps import require_auth
from ...firewall import FirewallManager, NftablesStats

router = APIRouter()
fw = FirewallManager()


# ─── 请求/响应模型 ──────────────────────────────────────────

class ZoneCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=32)
    input: str = "accept"
    forward: str = "accept"
    output: str = "accept"
    masquerade: bool = False
    isolated: bool = False
    forward_to: List[str] = []


class PortForwardCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    from_zone: str = "wan"
    from_port: int = Field(..., ge=1, le=65535)
    protocol: str = "tcp"
    to_ip: str = Field(..., pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    to_port: int = Field(..., ge=1, le=65535)
    description: str = ""
    enabled: bool = True


class RuleCreate(BaseModel):
    name: str = Field("", max_length=64)
    direction: str = "input"  # input | forward | output
    action: str = "accept"    # accept | drop | reject
    src_ip: str = ""
    dst_ip: str = ""
    src_port: Optional[int] = None
    dst_port: Optional[int] = None
    protocol: str = "tcp"
    log: bool = False
    enabled: bool = True


# ─── 状态 ──────────────────────────────────────────────────

@router.get("/stats")
async def get_nftables_stats(auth=Depends(require_auth)):
    """获取 nftables 完整运行时状态"""
    stats = fw.get_stats()
    return {
        "tables": stats.tables,
        "chains": stats.chains,
        "rules_count": len(stats.rules),
        "rules": [
            {
                "handle": r.handle,
                "table": r.table,
                "chain": r.chain,
                "rule": r.rule,
                "packets": r.counter_packets,
                "bytes": r.counter_bytes,
            }
            for r in stats.rules
        ],
    }


@router.get("/stats/ubunturouter")
async def get_ubunturouter_rules(auth=Depends(require_auth)):
    """仅获取 ubunturouter 表中的规则"""
    stats = fw.get_stats()
    rules = [r for r in stats.rules if r.table == "ubunturouter"]
    return {
        "rules_count": len(rules),
        "rules": [
            {
                "handle": r.handle,
                "chain": r.chain,
                "rule": r.rule,
                "packets": r.counter_packets,
                "bytes": r.counter_bytes,
            }
            for r in rules
        ],
    }


# ─── Conntrack ─────────────────────────────────────────────

@router.get("/conntrack")
async def get_conntrack(limit: int = Query(100, le=500),
                         auth=Depends(require_auth)):
    """获取 conntrack 连接跟踪"""
    entries = fw.get_conntrack(limit)
    return {
        "total": len(entries),
        "entries": [
            {
                "protocol": e.protocol,
                "src": f"{e.src_ip}:{e.src_port}",
                "dst": f"{e.dst_ip}:{e.dst_port}",
                "state": e.state,
                "bytes": e.bytes_in + e.bytes_out,
            }
            for e in entries
        ],
    }


@router.post("/conntrack/flush")
async def flush_conntrack(auth=Depends(require_auth)):
    """清空 conntrack 表"""
    success = fw.flush_conntrack()
    return {"success": success, "message": "conntrack 表已清空" if success else "清空失败"}


# ─── Zone 管理 ─────────────────────────────────────────────

@router.get("/zones")
async def list_zones(auth=Depends(require_auth)):
    """获取 ubunturouter 中的所有 zone (chain)"""
    stats = fw.get_stats()
    zones = []
    for chain_name, rules_list in stats.chains.items():
        if chain_name != "ubunturouter":
            continue
        for c in rules_list:
            zone_type = "builtin" if c in ("input", "forward", "output") else "custom"
            zones.append({
                "name": c,
                "type": zone_type,
                "policy": "accept",
                "rules_count": len([r for r in stats.rules if r.chain == c and r.table == "ubunturouter"]),
            })
    return {"zones": zones}


@router.post("/zones")
async def create_zone(zone: ZoneCreate, auth=Depends(require_auth)):
    """创建 Zone (nftables chain)"""
    import subprocess
    nft = "/usr/sbin/nft"
    try:
        # 确保表和基础 chains 存在
        fw.ensure_table("ubunturouter", "inet")
        for base_chain in ["input", "forward", "output", "prerouting", "postrouting"]:
            try:
                subprocess.run(
                    [nft, "add", "chain", "inet", "ubunturouter", base_chain],
                    capture_output=True, text=True, timeout=5
                )
            except Exception:
                pass

        # 创建自定义 zone chain（无 hook，作为 jump 目标）
        r = subprocess.run(
            [nft, "add", "chain", "inet", "ubunturouter", zone.name],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode != 0:
            return {"success": False, "message": f"创建 zone 失败: {r.stderr.strip()}"}
        return {"success": True, "message": f"Zone '{zone.name}' 已创建"}
    except Exception as e:
        return {"success": False, "message": f"创建 zone 失败: {str(e)}"}


@router.delete("/zones/{name}")
async def delete_zone(name: str, auth=Depends(require_auth)):
    """删除 Zone (nftables chain)"""
    import subprocess
    nft = "/usr/sbin/nft"
    try:
        r = subprocess.run(
            [nft, "delete", "chain", "inet", "ubunturouter", name],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode != 0:
            return {"success": False, "message": f"删除 zone 失败: {r.stderr.strip()}"}
        return {"success": True, "message": f"Zone '{name}' 已删除"}
    except Exception as e:
        return {"success": False, "message": f"删除 zone 失败: {str(e)}"}


# ─── 端口转发 ─────────────────────────────────────────────

@router.get("/port-forwards")
async def list_port_forwards(auth=Depends(require_auth)):
    """列出所有端口转发规则"""
    stats = fw.get_stats()
    forwards = []
    for r in stats.rules:
        if "dnat" in r.rule.lower() or ("dport" in r.rule.lower() and r.chain == "prerouting"):
            forwards.append({
                "handle": r.handle,
                "chain": r.chain,
                "rule": r.rule,
                "packets": r.counter_packets,
                "bytes": r.counter_bytes,
                "enabled": True,
            })
    return {"port_forwards": forwards}


@router.post("/port-forwards")
async def add_port_forward(pf: PortForwardCreate, auth=Depends(require_auth)):
    """添加端口转发规则"""
    success = fw.add_port_forward(
        name=pf.name,
        from_zone=pf.from_zone,
        from_port=pf.from_port,
        to_ip=pf.to_ip,
        to_port=pf.to_port,
        protocol=pf.protocol,
        iface=pf.from_zone if pf.from_zone != "wan" else "",
    )
    return {"success": success, "message": "端口转发已添加" if success else "添加失败"}


@router.delete("/port-forwards/{handle}")
async def delete_port_forward(handle: int, auth=Depends(require_auth)):
    """删除端口转发（按 handle）"""
    stats = fw.get_stats()
    for r in stats.rules:
        if r.handle == handle:
            success = fw.delete_rule(handle, r.chain)
            return {"success": success, "message": "端口转发已删除" if success else "删除失败"}
    raise HTTPException(status_code=404, detail="未找到该端口转发规则")


# ─── 防火墙规则 ───────────────────────────────────────────

@router.get("/rules")
async def list_rules(table: str = "ubunturouter",
                      auth=Depends(require_auth)):
    """列出 ubunturouter 表中的所有规则"""
    stats = fw.get_stats()
    rules = [
        {
            "handle": r.handle,
            "chain": r.chain,
            "rule": r.rule,
            "packets": r.counter_packets,
            "bytes": r.counter_bytes,
        }
        for r in stats.rules if r.table == table
    ]
    return {"rules": rules}


@router.post("/rules")
async def add_rule(rule: RuleCreate, auth=Depends(require_auth)):
    """添加防火墙规则"""
    rule_parts = []
    if rule.src_ip:
        rule_parts.append(f"ip saddr {rule.src_ip}")
    if rule.dst_ip:
        rule_parts.append(f"ip daddr {rule.dst_ip}")
    if rule.src_port:
        rule_parts.append(f"tcp sport {rule.src_port}")
    if rule.dst_port:
        rule_parts.append(f"tcp dport {rule.dst_port}")
    if rule.log:
        rule_parts.append("log")
    rule_parts.append("counter")
    rule_parts.append(rule.action)

    success = fw.add_rule(rule.direction, " ".join(rule_parts))
    return {"success": success, "message": "规则已添加" if success else "添加失败"}


@router.delete("/rules/{handle}")
async def delete_rule(handle: int, chain: str = "input",
                       auth=Depends(require_auth)):
    """删除指定 handle 的规则"""
    success = fw.delete_rule(handle, chain)
    if not success:
        # 尝试在其他链中查找
        stats = fw.get_stats()
        for r in stats.rules:
            if r.handle == handle and r.table == "ubunturouter":
                success = fw.delete_rule(handle, r.chain)
                break
    return {"success": success, "message": "规则已删除" if success else "删除失败"}


@router.post("/rules/flush")
async def flush_rules(chain: str = "forward",
                       auth=Depends(require_auth)):
    """清空指定链的所有规则"""
    success = fw.flush_chain(chain)
    return {"success": success, "message": f"{chain} 链已清空" if success else "清空失败"}
