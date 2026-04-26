"""配置 API: apply / rollback / view / validate"""

from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from ..deps import require_auth
from ...engine.engine import ConfigEngine
from ...engine.applier import ConfigApplier
from ...engine.rollback import RollbackManager
from ...config.serializer import ConfigSerializer
from ...generators.base import GeneratorRegistry
from ...generators.netplan import NetplanGenerator
from ...generators.nftables import NftablesGenerator
from ...generators.dnsmasq import DnsmasqGenerator


router = APIRouter()


class ApplyRequest(BaseModel):
    config_yaml: str
    auto_rollback: bool = True


class RollbackRequest(BaseModel):
    snapshot_id: str


def get_registry():
    registry = GeneratorRegistry()
    registry.register("netplan", NetplanGenerator())
    registry.register("nftables", NftablesGenerator())
    registry.register("dnsmasq", DnsmasqGenerator())
    return registry


@router.get("/view")
async def view_config(auth=Depends(require_auth)):
    """查看当前配置"""
    engine = ConfigEngine()
    if not engine.exists():
        raise HTTPException(status_code=404, detail="系统未初始化")

    config = engine.load()
    yaml_str = ConfigSerializer.to_yaml(config)
    return {"config_yaml": yaml_str}


@router.post("/apply")
async def apply_config(req: ApplyRequest, auth=Depends(require_auth)):
    """Apply 新配置"""
    engine = ConfigEngine()

    try:
        new_config = ConfigSerializer.from_yaml(req.config_yaml)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"配置解析失败: {str(e)}")

    # 校验
    validation = engine.validate(new_config)
    if validation.errors:
        raise HTTPException(status_code=400, detail={
            "error": "配置校验失败",
            "errors": validation.errors,
        })

    registry = get_registry()
    applier = ConfigApplier(engine, registry)
    result = applier.apply_atomic(new_config, auto_rollback=req.auto_rollback)

    return {
        "success": result.success,
        "snapshot_id": result.snapshot_id,
        "rollback_to": result.rollback_to,
        "error": result.error,
        "changed_sections": result.changed_sections,
        "service_results": [
            {"name": s.name, "success": s.success, "duration_ms": s.duration_ms}
            for s in result.service_results
        ],
    }


@router.post("/rollback")
async def rollback_config(req: RollbackRequest, auth=Depends(require_auth)):
    """回滚到指定快照"""
    engine = ConfigEngine()
    rollback = RollbackManager(snapshot_dir=engine.snapshot_dir)
    success = rollback.auto_rollback(req.snapshot_id)
    return {"success": success, "snapshot_id": req.snapshot_id}


@router.get("/validate")
async def validate_config(yaml: str, auth=Depends(require_auth)):
    """校验配置（不 Apply）"""
    engine = ConfigEngine()
    try:
        config = ConfigSerializer.from_yaml(yaml)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"配置解析失败: {str(e)}")

    validation = engine.validate(config)
    return {
        "valid": len(validation.errors) == 0,
        "errors": validation.errors,
        "warnings": validation.warnings,
    }
