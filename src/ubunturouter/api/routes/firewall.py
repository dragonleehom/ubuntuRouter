"""防火墙 API 路由 — Zones + 端口转发 + 规则 + 状态 + Sprint 1 增强

Sprint 1 增强: ICMP/ipset/rate limit/时间限制/conntrack state/MAC/NAT回环/Zone增强
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from src.ubunturouter.api.deps import require_auth
from src.ubunturouter.firewall import (
    FirewallManager, NftablesStats, ICMP_TYPES, ICMPV6_TYPES, NftablesRuleBuilder
)

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
    nat_loopback: bool = False


class FirewallRuleCreate(BaseModel):
    """增强的防火墙规则创建模型 — Sprint 1"""
    name: str = Field("", max_length=64)
    chain: str = "forward"  # input | forward | output | custom_zone
    direction: str = ""     # 兼容旧版（可选）
    action: str = Field(default="accept", pattern=r"^(accept|drop|reject)$")

    # 基础匹配
    src_ip: str = ""
    dst_ip: str = ""
    src_port: Optional[int] = Field(None, ge=1, le=65535)
    dst_port: Optional[int] = Field(None, ge=1, le=65535)
    protocol: str = "tcp"

    # Sprint 1 增强
    src_mac: str = ""               # MAC 地址匹配
    in_iface: str = ""              # 入接口
    out_iface: str = ""             # 出接口
    icmp_type: str = ""             # ICMP 类型名 (如 echo-request)
    ct_state: str = ""              # conntrack 状态 (new/est/related/invalid)
    rate: str = ""                  # 速率限制 (如 "10/minute")
    burst: str = ""                 # 突发 (如 "5 packets")
    time_begin: str = ""            # 开始时间 (HH:MM)
    time_end: str = ""              # 结束时间 (HH:MM)
    time_days: str = ""             # 星期 (Mon,Tue,Wed...)
    log: bool = False
    log_prefix: str = ""
    enabled: bool = True
    mark: str = ""                  # fwmark
    dscp: int = Field(0, ge=0, le=63)  # DSCP 标记
    jump_to: str = ""               # 跳转到 zone
    comment: str = ""


class SetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    type: str = "ipv4_addr"
    flags: str = "interval"


class SetElementAdd(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    element: str = ""


# ─── ICMP 类型列表 ────────────────────────────────────────

@router.get("/icmp-types")
async def list_icmp_types(auth=Depends(require_auth)):
    """获取支持的 ICMP/ICMPv6 类型列表"""
    return {
        "icmp": [{"value": v, "label": k} for k, v in ICMP_TYPES.items()],
        "icmpv6": [{"value": v, "label": k} for k, v in ICMPV6_TYPES.items()],
    }


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


# ─── Zone 管理 (增强) ─────────────────────────────────────

@router.get("/zones")
async def list_zones(auth=Depends(require_auth)):
    """获取 ubunturouter 中的所有 zone (chain)"""
    zones = fw.list_zones()
    return {"zones": zones}


@router.post("/zones")
async def create_zone(zone: ZoneCreate, auth=Depends(require_auth)):
    """创建 Zone (nftables chain)"""
    fw.ensure_base_chains()
    success = fw.create_zone(zone.name)
    return {
        "success": success,
        "message": f"Zone '{zone.name}' 已创建" if success else f"创建 zone 失败"
    }


@router.delete("/zones/{name}")
async def delete_zone(name: str, auth=Depends(require_auth)):
    """删除 Zone"""
    if name in ("input", "forward", "output"):
        raise HTTPException(status_code=400, detail="不能删除内置 chain")
    success = fw.delete_zone(name)
    return {
        "success": success,
        "message": f"Zone '{name}' 已删除" if success else f"删除 zone 失败"
    }


# ─── 端口转发 (含 NAT 回环) ───────────────────────────────

@router.get("/port-forwards")
async def list_port_forwards(auth=Depends(require_auth)):
    """列出所有端口转发规则"""
    forwards = fw.list_port_forwards()
    return {"port_forwards": forwards}


@router.post("/port-forwards")
async def add_port_forward(pf: PortForwardCreate, auth=Depends(require_auth)):
    """添加端口转发规则，支持 NAT 回环"""
    success = fw.add_port_forward(
        name=pf.name,
        from_zone=pf.from_zone,
        from_port=pf.from_port,
        to_ip=pf.to_ip,
        to_port=pf.to_port,
        protocol=pf.protocol,
        iface=pf.from_zone if pf.from_zone != "wan" else "",
        nat_loopback=pf.nat_loopback,
    )
    return {
        "success": success,
        "message": "端口转发已添加" if success else "添加失败",
        "nat_loopback": pf.nat_loopback,
    }


@router.delete("/port-forwards/{handle}")
async def delete_port_forward(handle: int, auth=Depends(require_auth)):
    """删除端口转发（按 handle）"""
    success = fw.delete_port_forward(handle)
    if not success:
        raise HTTPException(status_code=404, detail="未找到该端口转发规则")
    return {"success": success, "message": "端口转发已删除"}


# ─── 防火墙规则 (增强) ───────────────────────────────────

@router.get("/rules")
async def list_rules(table: str = "ubunturouter",
                      auth=Depends(require_auth)):
    """列出指定表中的所有规则"""
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
async def add_rule(rule: FirewallRuleCreate, auth=Depends(require_auth)):
    """添加增强的防火墙规则（支持 ICMP/ipset/conntrack state/MAC/rate limit 等）"""
    # 向后兼容：如果传了 direction 但没传 chain
    chain = rule.chain if rule.chain else rule.direction if rule.direction else "forward"
    rule_dict = rule.model_dump()
    rule_dict["chain"] = chain
    success = fw.add_rule(rule_dict)
    return {
        "success": success,
        "message": "规则已添加" if success else "添加失败",
        "chain": chain,
    }


@router.post("/rules/simple")
async def add_simple_rule(rule: dict, auth=Depends(require_auth)):
    """向后兼容：添加简单规则（旧版格式）"""
    chain = rule.get("direction", rule.get("chain", "forward"))
    success = fw.add_rule_advanced(chain, rule.get("rule_expr", ""))
    return {"success": success, "message": "规则已添加" if success else "添加失败"}


@router.delete("/rules/{handle}")
async def delete_rule(handle: int, chain: str = "",
                       auth=Depends(require_auth)):
    """删除指定 handle 的规则"""
    if chain:
        success = fw.delete_rule(handle, chain)
    else:
        # 自动查找
        stats = fw.get_stats()
        success = False
        for r in stats.rules:
            if r.handle == handle and r.table == "ubunturouter":
                success = fw.delete_rule(handle, r.chain)
                break
    if not success:
        raise HTTPException(status_code=404, detail="未找到该规则")
    return {"success": success, "message": "规则已删除"}


@router.post("/rules/flush")
async def flush_rules(chain: str = "forward",
                       auth=Depends(require_auth)):
    """清空指定链的所有规则"""
    success = fw.flush_chain(chain)
    return {"success": success, "message": f"{chain} 链已清空" if success else "清空失败"}


# ─── ipset 管理 ─────────────────────────────────────────────

@router.get("/sets")
async def list_sets(auth=Depends(require_auth)):
    """列出所有 nftables 集合 (ipset 替代)"""
    sets = fw.list_sets()
    return {"sets": sets}


@router.post("/sets")
async def create_set(s: SetCreate, auth=Depends(require_auth)):
    """创建 nftables 集合"""
    fw.ensure_table()
    success = fw.create_set(s.name, set_type=s.type, flags=s.flags)
    return {
        "success": success,
        "message": f"集合 '{s.name}' 已创建" if success else "创建失败",
    }


@router.delete("/sets/{name}")
async def delete_set(name: str, auth=Depends(require_auth)):
    """删除集合"""
    success = fw.delete_set(name)
    return {
        "success": success,
        "message": f"集合 '{name}' 已删除" if success else "删除失败"
    }


@router.post("/sets/elements")
async def add_set_element(e: SetElementAdd, auth=Depends(require_auth)):
    """向集合添加元素"""
    success = fw.add_to_set(e.name, e.element)
    return {
        "success": success,
        "message": f"元素 {e.element} 已添加到 {e.name}" if success else "添加失败"
    }


@router.delete("/sets/elements")
async def delete_set_element(name: str = Query(...),
                               element: str = Query(...),
                               auth=Depends(require_auth)):
    """从集合删除元素"""
    success = fw.delete_from_set(name, element)
    return {
        "success": success,
        "message": f"元素 {element} 已从 {name} 删除" if success else "删除失败"
    }
