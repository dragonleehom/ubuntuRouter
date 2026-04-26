"""配置 API: apply / rollback / view / validate

使用新的 EventBus + Generator 体系。
"""

from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..deps import require_auth
from ...config.serializer import ConfigSerializer
from ...config.models import UbunturouterConfig


router = APIRouter()


class ApplyRequest(BaseModel):
    """Apply 请求"""
    config_yaml: str
    auto_rollback: bool = True


class RollbackRequest(BaseModel):
    """回滚请求"""
    snapshot_id: str


@router.get("/view")
async def view_config(auth=Depends(require_auth)):
    """查看当前配置"""
    from ...engine.engine import ConfigEngine
    engine = ConfigEngine()
    if not engine.exists():
        raise HTTPException(status_code=404, detail="系统未初始化")

    config = engine.load()
    yaml_str = ConfigSerializer.to_yaml(config)
    return {"config_yaml": yaml_str}


@router.post("/apply")
async def apply_config(req: ApplyRequest, auth=Depends(require_auth)):
    """Apply 新配置 — 通过 EventBus 触发所有 Generator"""
    from ...engine.engine import ConfigEngine
    engine = ConfigEngine()

    try:
        new_config = ConfigSerializer.from_yaml(req.config_yaml)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"配置解析失败: {str(e)}")

    if not isinstance(new_config, UbunturouterConfig):
        raise HTTPException(status_code=400, detail="无效的配置格式")

    result = engine.apply(new_config, auto_rollback=req.auto_rollback)

    return {
        "success": result.success,
        "message": result.message,
        "snapshot_id": result.snapshot_id,
        "execution_time_ms": result.execution_time_ms,
    }


@router.post("/rollback")
async def rollback_config(req: RollbackRequest, auth=Depends(require_auth)):
    """回滚到指定快照"""
    from ...engine.engine import ConfigEngine
    engine = ConfigEngine()
    result = engine.rollback(req.snapshot_id)
    return {
        "success": result.success,
        "message": result.message,
        "snapshot_id": req.snapshot_id,
    }


@router.post("/validate")
async def validate_config(data: dict, auth=Depends(require_auth)):
    """校验配置（不 Apply）接收 JSON 或 YAML"""
    from ...engine.engine import ConfigEngine
    engine = ConfigEngine()

    raw = data.get("config_yaml", data.get("yaml", ""))
    try:
        config = ConfigSerializer.from_yaml(raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"配置解析失败: {str(e)}")

    validation = engine.validate(config)
    return {
        "valid": validation.is_valid,
        "errors": validation.errors,
        "warnings": validation.warnings,
    }
