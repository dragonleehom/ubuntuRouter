"""TTYD Terminal API routes — web terminal service management"""

from fastapi import APIRouter, Depends, HTTPException

from ..deps import require_auth
from ...ttyd import TTYDManager

router = APIRouter()
ttyd_manager = TTYDManager()


@router.get("/info")
async def get_ttyd_info(auth=Depends(require_auth)):
    """Get ttyd terminal service information."""
    return ttyd_manager.get_info()


@router.post("/start")
async def start_ttyd(auth=Depends(require_auth)):
    """Start ttyd web terminal."""
    result = ttyd_manager.start()
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "start failed"))
    return result


@router.post("/stop")
async def stop_ttyd(auth=Depends(require_auth)):
    """Stop ttyd web terminal."""
    result = ttyd_manager.stop()
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "stop failed"))
    return result


@router.post("/restart")
async def restart_ttyd(auth=Depends(require_auth)):
    """Restart ttyd web terminal."""
    result = ttyd_manager.restart()
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "restart failed"))
    return result
