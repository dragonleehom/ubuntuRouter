"""路由 API 路由 — 路由表 + 静态路由 + Multi-WAN"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from ..deps import require_auth
from ...routing import RoutingManager

router = APIRouter()
rm = RoutingManager()


# ─── 请求/响应模型 ──────────────────────────────────────────

class StaticRouteCreate(BaseModel):
    destination: str = Field(..., description="目标网络，如 10.0.0.0/24")
    gateway: str = Field(..., pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    iface: str = ""
    metric: int = 0
    table: str = "main"


class GatewaySwitch(BaseModel):
    iface: str
    gateway: str = Field(..., pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")


# ─── 路由表 ──────────────────────────────────────────────

@router.get("/table")
async def get_routing_table(table: str = Query("main"),
                             auth=Depends(require_auth)):
    """获取指定路由表的路由"""
    routes = rm.get_routes(table)
    return {
        "table": table,
        "routes_count": len(routes),
        "routes": [
            {
                "destination": r.destination,
                "gateway": r.gateway,
                "iface": r.iface,
                "metric": r.metric,
                "proto": r.proto,
                "is_default": r.is_default,
            }
            for r in routes
        ],
    }


@router.get("/tables")
async def get_all_tables(auth=Depends(require_auth)):
    """获取所有路由表"""
    tables = rm.get_all_routing_tables()
    return {
        "tables_count": len(tables),
        "tables": [
            {
                "table_id": t.table_id,
                "table_name": t.table_name,
                "routes_count": len(t.routes),
            }
            for t in tables
        ],
    }


@router.get("/default")
async def get_default_route(auth=Depends(require_auth)):
    """获取默认路由"""
    route = rm.get_default_route()
    if not route:
        return {"exists": False}
    return {
        "exists": True,
        "gateway": route.gateway,
        "iface": route.iface,
        "metric": route.metric,
    }


# ─── 规则 ──────────────────────────────────────────────────

@router.get("/rules")
async def get_routing_rules(auth=Depends(require_auth)):
    """获取策略路由规则"""
    rules = rm.get_routing_rules()
    return {"rules": rules}


# ─── 静态路由 CRUD ──────────────────────────────────────

@router.post("/static")
async def add_static_route(route: StaticRouteCreate,
                            auth=Depends(require_auth)):
    """添加静态路由"""
    success = rm.add_static_route(
        route.destination, route.gateway,
        route.iface, route.metric, route.table
    )
    return {"success": success, "message": "静态路由已添加" if success else "添加失败"}


@router.delete("/static")
async def delete_static_route(destination: str, gateway: str = "",
                               iface: str = "", table: str = "main",
                               auth=Depends(require_auth)):
    """删除静态路由"""
    success = rm.delete_static_route(destination, gateway, iface, table)
    return {"success": success, "message": "静态路由已删除" if success else "删除失败"}


# ─── Multi-WAN ─────────────────────────────────────────────

@router.get("/multiwan")
async def get_multiwan_status(auth=Depends(require_auth)):
    """获取 Multi-WAN 状态"""
    wans = rm.get_multiwan_status()
    return {
        "wans": [
            {
                "name": w.wan_name,
                "iface": w.iface,
                "gateway": w.gateway,
                "online": w.online,
                "latency_ms": round(w.latency_ms, 1),
                "packet_loss": round(w.packet_loss, 1),
                "is_active": w.is_active,
            }
            for w in wans
        ],
    }


@router.post("/multiwan/switch")
async def switch_gateway(switch: GatewaySwitch,
                          auth=Depends(require_auth)):
    """手动切换默认网关"""
    success = rm.switch_default_gateway(switch.iface, switch.gateway)
    if success:
        return {"success": True, "message": f"默认网关已切换到 {switch.iface} ({switch.gateway})"}
    return {"success": False, "message": "切换失败"}
