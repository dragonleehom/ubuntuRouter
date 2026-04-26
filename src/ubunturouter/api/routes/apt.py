"""APT Sources API routes — software source management"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import require_auth
from ...apt import APTManager

router = APIRouter()
apt_manager = APTManager()


class SourceAddRequest(BaseModel):
    line: str = Field(..., min_length=1, description="APT sources.list line (e.g. 'deb http://archive.ubuntu.com/ubuntu noble main')")


class SourceRemoveRequest(BaseModel):
    uri: str = Field(..., min_length=1, description="URI to remove from sources (e.g. 'archive.ubuntu.com')")


class MirrorSwitchRequest(BaseModel):
    mirror: str = Field(..., min_length=1, description="Mirror key (e.g. 'mirrors.tuna.tsinghua.edu.cn')")


@router.get("/sources")
async def list_sources(auth=Depends(require_auth)):
    """List all APT software sources."""
    sources = apt_manager.list_sources()
    return {"sources": sources, "count": len(sources)}


@router.post("/sources", status_code=201)
async def add_source(body: SourceAddRequest, auth=Depends(require_auth)):
    """Add a new APT source line."""
    result = apt_manager.add_source(body.line)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "add failed"))
    return result


@router.delete("/sources")
async def remove_source(body: SourceRemoveRequest, auth=Depends(require_auth)):
    """Remove all APT source lines matching a URI."""
    result = apt_manager.remove_source(body.uri)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result


@router.put("/sources/mirror")
async def switch_mirror(body: MirrorSwitchRequest, auth=Depends(require_auth)):
    """Switch Ubuntu primary mirror."""
    result = apt_manager.switch_mirror(body.mirror)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


@router.get("/mirrors")
async def list_mirrors(auth=Depends(require_auth)):
    """List all available mirror options."""
    mirrors = apt_manager.get_mirrors()
    return {"mirrors": mirrors, "count": len(mirrors)}


@router.post("/update")
async def run_apt_update(auth=Depends(require_auth)):
    """Run apt update."""
    return apt_manager.run_update()


@router.get("/status")
async def get_apt_status(auth=Depends(require_auth)):
    """Get APT source management status."""
    return apt_manager.get_status()
