"""编排 API 路由 — 设备管理、应用识别、规则配置、流量统计、模板"""
import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..deps import require_auth
from ...orchestrator import (
    DeviceDetector,
    AppDB,
    AppDetector,
    RuleCompiler,
    Rule,
    RuleMatch,
    RuleAction,
    RuleSchedule,
    TrafficStats,
    FailoverEngine,
)
from ...multiwan.health import HealthChecker

router = APIRouter()

# ─── 全局实例 ──────────────────────────────────────────────
device_detector = DeviceDetector()
app_db = AppDB()
app_detector = AppDetector(app_db)
rule_compiler = RuleCompiler()
traffic_stats = TrafficStats()
health_checker = HealthChecker()
failover_engine = FailoverEngine(health_checker)

# ─── 请求/响应模型 ─────────────────────────────────────────

class RuleMatchRequest(BaseModel):
    devices: List[str] = Field(default_factory=list, description="MAC 地址列表")
    apps: List[str] = Field(default_factory=list, description="应用名称列表")
    ports: List[str] = Field(default_factory=list, description="端口列表")
    protocols: List[str] = Field(default_factory=list, description="协议列表")
    src_ips: List[str] = Field(default_factory=list, description="源 IP 列表")
    dst_ips: List[str] = Field(default_factory=list, description="目标 IP 列表")

class RuleActionRequest(BaseModel):
    action: str = Field("route", description="动作: route/bypass/drop")
    target: str = Field("", description="目标: wan1/wan2/vpn/direct")
    table: int = Field(100, description="路由表 ID")
    mark: int = Field(0, description="fwmark 值")

class RuleScheduleRequest(BaseModel):
    enabled: bool = False
    start_time: str = ""
    end_time: str = ""
    days: List[str] = Field(default_factory=list, description="星期: mon/tue/wed/thu/fri/sat/sun")

class RuleCreateRequest(BaseModel):
    name: str = Field(..., description="规则名称")
    description: str = ""
    enabled: bool = True
    priority: int = Field(1000, ge=1, le=99999, description="优先级 (越小越优先)")
    match: RuleMatchRequest = Field(default_factory=RuleMatchRequest)
    action: RuleActionRequest = Field(default_factory=RuleActionRequest)
    schedule: RuleScheduleRequest = Field(default_factory=RuleScheduleRequest)

class RuleUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    match: Optional[RuleMatchRequest] = None
    action: Optional[RuleActionRequest] = None
    schedule: Optional[RuleScheduleRequest] = None

class RenameRequest(BaseModel):
    name: str = Field(..., description="新设备名称")

# ─── 模板定义 ──────────────────────────────────────────────

ORCHESTRATOR_TEMPLATES = [
    {
        "id": "gaming_wan1",
        "name": "游戏流量走 WAN1",
        "description": "将 Steam、Epic Games 等游戏流量路由到 WAN1",
        "category": "gaming",
        "rules": [
            {
                "name": "Steam -> WAN1",
                "priority": 1000,
                "match": {"apps": ["Steam", "Epic Games"]},
                "action": {"action": "route", "target": "wan1"},
            }
        ],
    },
    {
        "id": "video_wan2",
        "name": "视频流量走 WAN2",
        "description": "将视频/直播类流量路由到 WAN2",
        "category": "media",
        "rules": [
            {
                "name": "Video -> WAN2",
                "priority": 1000,
                "match": {
                    "apps": [
                        "Netflix", "YouTube", "Bilibili",
                        "Douyin", "TikTok",
                    ]
                },
                "action": {"action": "route", "target": "wan2"},
            }
        ],
    },
    {
        "id": "chat_vpn",
        "name": "通讯流量走 VPN",
        "description": "将 Telegram、WhatsApp 等通讯流量路由到 VPN",
        "category": "chat",
        "rules": [
            {
                "name": "Chat -> VPN",
                "priority": 1000,
                "match": {
                    "apps": ["Telegram", "WhatsApp", "WeChat", "QQ", "Discord"]
                },
                "action": {"action": "route", "target": "vpn"},
            }
        ],
    },
    {
        "id": "device_wan1",
        "name": "指定设备走 WAN1",
        "description": "将指定 MAC 设备的全部流量路由到 WAN1",
        "category": "device",
        "rules": [
            {
                "name": "Device -> WAN1",
                "priority": 1000,
                "match": {"devices": ["00:00:00:00:00:00"]},
                "action": {"action": "route", "target": "wan1"},
            }
        ],
    },
    {
        "id": "ai_bypass",
        "name": "AI 服务直连",
        "description": "AI 服务（ChatGPT 等）不经过 VPN 直接路由",
        "category": "ai",
        "rules": [
            {
                "name": "AI Direct",
                "priority": 900,
                "match": {"apps": ["ChatGPT"]},
                "action": {"action": "route", "target": "direct"},
            }
        ],
    },
]


# ═══════════════════════════════════════════════════════════════
# 设备 API
# ═══════════════════════════════════════════════════════════════

@router.get("/devices", summary="获取设备列表")
async def get_devices(auth=Depends(require_auth)):
    """获取所有已知设备列表（触发检测）"""
    devices = device_detector.detect_all()
    return {
        "devices": [d.to_dict() for d in devices],
        "total": len(devices),
    }


@router.get("/devices/{mac}", summary="获取设备详情")
async def get_device(mac: str, auth=Depends(require_auth)):
    """获取单个设备详情"""
    device = device_detector.get_device(mac)
    if not device:
        raise HTTPException(
            status_code=404, detail=f"设备 {mac} 未找到"
        )
    return device.to_dict()


@router.put("/devices/{mac}/rename", summary="重命名设备")
async def rename_device(mac: str, req: RenameRequest,
                         auth=Depends(require_auth)):
    """重命名设备"""
    success = device_detector.rename(mac, req.name)
    if not success:
        raise HTTPException(
            status_code=404, detail=f"设备 {mac} 未找到"
        )
    return {"success": True, "message": "设备已重命名"}


# ═══════════════════════════════════════════════════════════════
# 应用 API
# ═══════════════════════════════════════════════════════════════

@router.get("/apps", summary="获取应用列表")
async def get_apps(
    category: Optional[str] = Query(None, description="按分类过滤"),
    q: Optional[str] = Query(None, description="搜索关键词"),
    auth=Depends(require_auth),
):
    """获取应用特征库列表"""
    if q:
        apps = app_db.search(q)
    elif category:
        apps = app_db.get_by_category(category)
    else:
        apps = app_db.get_all()

    return {
        "apps": [a.to_dict() for a in apps],
        "total": len(apps),
        "categories": app_db.get_categories(),
    }


@router.get("/apps/{name}", summary="获取应用详情")
async def get_app(name: str, auth=Depends(require_auth)):
    """获取应用详情"""
    app = app_db.get_by_name(name)
    if not app:
        raise HTTPException(
            status_code=404, detail=f"应用 {name} 未找到"
        )
    return app.to_dict()


# ═══════════════════════════════════════════════════════════════
# 规则 API
# ═══════════════════════════════════════════════════════════════

@router.get("/rules", summary="获取规则列表")
async def get_rules(auth=Depends(require_auth)):
    """获取所有规则（持久化的 + 已应用的）"""
    persisted = rule_compiler.load_rules()
    applied = rule_compiler.get_applied_rules()
    applied_ids = {r.id for r in applied}

    # 合并状态：标记哪些规则已应用
    rules_data = []
    for rule in persisted:
        data = rule.to_dict()
        data["applied"] = rule.id in applied_ids
        rules_data.append(data)

    return {
        "rules": rules_data,
        "total": len(rules_data),
    }


@router.post("/rules", summary="创建规则")
async def create_rule(req: RuleCreateRequest, auth=Depends(require_auth)):
    """创建新规则"""
    now = datetime.now().isoformat()
    rule_id = str(uuid.uuid4())[:8]

    rule = Rule(
        id=rule_id,
        name=req.name,
        description=req.description,
        enabled=req.enabled,
        priority=req.priority,
        match=RuleMatch(
            devices=req.match.devices,
            apps=req.match.apps,
            ports=req.match.ports,
            protocols=req.match.protocols,
            src_ips=req.match.src_ips,
            dst_ips=req.match.dst_ips,
        ),
        action=RuleAction(
            action=req.action.action,
            target=req.action.target,
            table=req.action.table,
            mark=req.action.mark,
        ),
        schedule=RuleSchedule(
            enabled=req.schedule.enabled,
            start_time=req.schedule.start_time,
            end_time=req.schedule.end_time,
            days=req.schedule.days,
        ),
        created_at=now,
        updated_at=now,
    )

    # 校验
    errors = rule_compiler.validate_rule(rule)
    if errors:
        raise HTTPException(
            status_code=400,
            detail={"message": "规则校验失败", "errors": errors},
        )

    # 持久化
    existing = rule_compiler.load_rules()
    existing.append(rule)
    # 保存到文件
    import yaml
    rules_path = Path("/opt/ubunturouter/data/orchestrator_rules.yaml")
    rules_path.parent.mkdir(parents=True, exist_ok=True)
    with open(rules_path, "w", encoding="utf-8") as f:
        yaml.dump([r.to_dict() for r in existing], f,
                  default_flow_style=False, allow_unicode=True)

    return {"success": True, "rule": rule.to_dict()}


@router.put("/rules/{rule_id}", summary="更新规则")
async def update_rule(rule_id: str, req: RuleUpdateRequest,
                       auth=Depends(require_auth)):
    """更新规则"""
    rules = rule_compiler.load_rules()
    target = None
    for r in rules:
        if r.id == rule_id:
            target = r
            break

    if not target:
        raise HTTPException(
            status_code=404, detail=f"规则 {rule_id} 未找到"
        )

    now = datetime.now().isoformat()

    if req.name is not None:
        target.name = req.name
    if req.description is not None:
        target.description = req.description
    if req.enabled is not None:
        target.enabled = req.enabled
    if req.priority is not None:
        target.priority = req.priority
    if req.match is not None:
        target.match = RuleMatch(
            devices=req.match.devices,
            apps=req.match.apps,
            ports=req.match.ports,
            protocols=req.match.protocols,
            src_ips=req.match.src_ips,
            dst_ips=req.match.dst_ips,
        )
    if req.action is not None:
        target.action = RuleAction(
            action=req.action.action,
            target=req.action.target,
            table=req.action.table,
            mark=req.action.mark,
        )
    if req.schedule is not None:
        target.schedule = RuleSchedule(
            enabled=req.schedule.enabled,
            start_time=req.schedule.start_time,
            end_time=req.schedule.end_time,
            days=req.schedule.days,
        )
    target.updated_at = now

    # 校验
    errors = rule_compiler.validate_rule(target)
    if errors:
        raise HTTPException(
            status_code=400,
            detail={"message": "规则校验失败", "errors": errors},
        )

    # 持久化
    import yaml
    rules_path = Path("/opt/ubunturouter/data/orchestrator_rules.yaml")
    with open(rules_path, "w", encoding="utf-8") as f:
        yaml.dump([r.to_dict() for r in rules], f,
                  default_flow_style=False, allow_unicode=True)

    return {"success": True, "rule": target.to_dict()}


@router.delete("/rules/{rule_id}", summary="删除规则")
async def delete_rule(rule_id: str, auth=Depends(require_auth)):
    """删除规则"""
    rules = rule_compiler.load_rules()
    original_len = len(rules)
    rules = [r for r in rules if r.id != rule_id]

    if len(rules) == original_len:
        raise HTTPException(
            status_code=404, detail=f"规则 {rule_id} 未找到"
        )

    # 如果已应用，先移除
    rule_compiler.remove_rule(rule_id)

    # 持久化
    import yaml
    rules_path = Path("/opt/ubunturouter/data/orchestrator_rules.yaml")
    with open(rules_path, "w", encoding="utf-8") as f:
        yaml.dump([r.to_dict() for r in rules], f,
                  default_flow_style=False, allow_unicode=True)

    return {"success": True, "message": f"规则 {rule_id} 已删除"}


@router.post("/rules/{rule_id}/toggle", summary="启用/禁用规则")
async def toggle_rule(rule_id: str, auth=Depends(require_auth)):
    """切换规则的启用/禁用状态"""
    rules = rule_compiler.load_rules()
    target = None
    for r in rules:
        if r.id == rule_id:
            target = r
            break

    if not target:
        raise HTTPException(
            status_code=404, detail=f"规则 {rule_id} 未找到"
        )

    target.enabled = not target.enabled
    target.updated_at = datetime.now().isoformat()

    # 持久化
    import yaml
    rules_path = Path("/opt/ubunturouter/data/orchestrator_rules.yaml")
    with open(rules_path, "w", encoding="utf-8") as f:
        yaml.dump([r.to_dict() for r in rules], f,
                  default_flow_style=False, allow_unicode=True)

    return {
        "success": True,
        "enabled": target.enabled,
        "message": f"规则已{'启用' if target.enabled else '禁用'}",
    }


@router.post("/rules/apply", summary="应用所有规则")
async def apply_rules(auth=Depends(require_auth)):
    """应用所有启用的规则到系统"""
    rules = rule_compiler.load_rules()
    enabled_rules = [r for r in rules if r.enabled]

    if not enabled_rules:
        raise HTTPException(
            status_code=400, detail="没有启用的规则需要应用"
        )

    success = rule_compiler.apply_rules(enabled_rules)
    if not success:
        raise HTTPException(
            status_code=500, detail="规则应用失败"
        )

    return {
        "success": True,
        "message": f"已应用 {len(enabled_rules)} 条规则",
        "applied_count": len(enabled_rules),
    }


# ═══════════════════════════════════════════════════════════════
# 统计 API
# ═══════════════════════════════════════════════════════════════

@router.get("/stats/devices", summary="设备流量统计")
async def get_device_stats(auth=Depends(require_auth)):
    """获取各设备的流量统计"""
    stats = traffic_stats.get_device_stats()
    return {"stats": stats}


@router.get("/stats/apps", summary="应用流量统计")
async def get_app_stats(auth=Depends(require_auth)):
    """获取按应用分类的流量统计"""
    stats = traffic_stats.get_app_stats()
    return {"stats": stats}


@router.get("/stats/channels", summary="通道流量统计")
async def get_channel_stats(auth=Depends(require_auth)):
    """获取各通道的流量统计"""
    stats = traffic_stats.get_channel_stats()
    return {"stats": stats}


# ═══════════════════════════════════════════════════════════════
# 模板 API
# ═══════════════════════════════════════════════════════════════

@router.get("/templates", summary="预置编排模板列表")
async def get_templates(auth=Depends(require_auth)):
    """获取所有预置编排模板"""
    return {
        "templates": ORCHESTRATOR_TEMPLATES,
        "total": len(ORCHESTRATOR_TEMPLATES),
    }


@router.post("/templates/{template_id}/apply", summary="应用模板")
async def apply_template(template_id: str, auth=Depends(require_auth)):
    """应用预置编排模板"""
    # 查找模板
    template = None
    for t in ORCHESTRATOR_TEMPLATES:
        if t["id"] == template_id:
            template = t
            break

    if not template:
        raise HTTPException(
            status_code=404, detail=f"模板 {template_id} 未找到"
        )

    # 将模板规则转换为 Rule 对象
    now = datetime.now().isoformat()
    new_rules = []
    for t_rule in template["rules"]:
        rule = Rule(
            id=str(uuid.uuid4())[:8],
            name=t_rule["name"],
            enabled=True,
            priority=t_rule.get("priority", 1000),
            match=RuleMatch(
                apps=t_rule.get("match", {}).get("apps", []),
                devices=t_rule.get("match", {}).get("devices", []),
                ports=t_rule.get("match", {}).get("ports", []),
                protocols=t_rule.get("match", {}).get("protocols", []),
            ),
            action=RuleAction(
                action=t_rule.get("action", {}).get("action", "route"),
                target=t_rule.get("action", {}).get("target", ""),
            ),
            created_at=now,
            updated_at=now,
        )
        new_rules.append(rule)

    # 合并到现有规则
    existing = rule_compiler.load_rules()
    existing.extend(new_rules)

    # 持久化
    import yaml
    rules_path = Path("/opt/ubunturouter/data/orchestrator_rules.yaml")
    rules_path.parent.mkdir(parents=True, exist_ok=True)
    with open(rules_path, "w", encoding="utf-8") as f:
        yaml.dump([r.to_dict() for r in existing], f,
                  default_flow_style=False, allow_unicode=True)

    return {
        "success": True,
        "message": f"已应用模板 '{template['name']}'，创建了 {len(new_rules)} 条规则",
        "rules": [r.to_dict() for r in new_rules],
    }
