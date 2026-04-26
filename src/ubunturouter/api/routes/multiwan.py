"""Multi-WAN API 路由 — 健康检查配置 + 线路状态 + 手动切换"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from ..deps import require_auth
from ...multiwan.health import HealthChecker

router = APIRouter()

# 全局健康检查引擎实例
health_checker = HealthChecker()


# ─── 请求/响应模型 ──────────────────────────────────────────

class WANConfig(BaseModel):
    name: str = Field(..., description="WAN 名称")
    iface: str = Field(..., description="物理接口")
    gateway: str = Field(..., pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    weight: int = Field(1, ge=1, le=100, description="权重，越高优先")

class MultiWANConfig(BaseModel):
    wans: List[WANConfig] = Field(..., description="WAN 线路列表")
    check_interval: int = Field(5, ge=1, le=300, description="检测间隔(秒)")
    ping_targets: List[str] = Field(default=["8.8.8.8", "114.114.114.114"])
    ping_count: int = Field(3, ge=1, le=10, description="每次 ping 次数")
    failure_threshold: int = Field(2, ge=1, le=10, description="连续失败触发切换")
    recovery_threshold: int = Field(3, ge=1, le=10, description="连续成功触发恢复")
    auto_failover: bool = Field(True, description="自动故障切换")
    load_balance: bool = Field(False, description="负载均衡")


# ─── Manager API ────────────────────────────────────────────

@router.get("/health")
async def get_health_status(auth=Depends(require_auth)):
    """获取健康检查引擎运行状态"""
    return {
        "running": health_checker._thread is not None and health_checker._thread.is_alive(),
        "wans_count": len(health_checker._config.get("wans", [])),
    }


@router.post("/start")
async def start_health_check(auth=Depends(require_auth)):
    """启动后台健康检查"""
    health_checker.start()
    return {"success": True, "message": "健康检查已启动"}


@router.post("/stop")
async def stop_health_check(auth=Depends(require_auth)):
    """停止后台健康检查"""
    health_checker.stop()
    return {"success": True, "message": "健康检查已停止"}


# ─── Status API ─────────────────────────────────────────────

@router.get("/status")
async def get_multiwan_status(auth=Depends(require_auth)):
    """获取所有 WAN 线路的实时状态"""
    status = health_checker.get_status()
    return {
        "wans": status,
        "active_wan": next((w for w in status if w["is_active"]), None),
    }


@router.post("/switch")
async def switch_active_wan(wan_name: str, auth=Depends(require_auth)):
    """手动切换到指定 WAN 线路"""
    success = health_checker.switch_active(wan_name)
    if success:
        return {"success": True, "message": f"已切换到 {wan_name}"}
    raise HTTPException(status_code=400, detail=f"切换失败: WAN '{wan_name}' 不存在或不可用")


# ─── Config API ─────────────────────────────────────────────

@router.get("/config")
async def get_multiwan_config(auth=Depends(require_auth)):
    """获取 Multi-WAN 配置"""
    config = health_checker.get_config()
    return config


@router.put("/config")
async def update_multiwan_config(config: MultiWANConfig, auth=Depends(require_auth)):
    """更新 Multi-WAN 配置"""
    health_checker.update_config(config.model_dump())
    return {"success": True, "message": "Multi-WAN 配置已更新"}
