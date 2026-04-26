"""Storage management API: disks, SMART, mounts"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import require_auth
from ...storage import StorageManager

router = APIRouter()
storage_manager = StorageManager()


class MountRequest(BaseModel):
    """Mount request body."""
    device: str = Field(..., description="Device name (e.g. 'sda1')", min_length=1,
                        pattern=r"^[a-zA-Z0-9_\-]+$")
    target: str = Field(..., description="Mount target path (e.g. '/mnt/usb')", min_length=1)
    fs_type: str | None = Field(None, description="Optional filesystem type (e.g. 'ext4', 'vfat')")


class UnmountRequest(BaseModel):
    """Unmount request body."""
    target: str = Field(..., description="Mount target path to unmount", min_length=1)


@router.get("/overview")
async def overview(auth=Depends(require_auth)):
    """Combined view: disks + mounts + SMART summary."""
    return storage_manager.get_overview()


@router.get("/disks")
async def list_disks(auth=Depends(require_auth)):
    """List physical block devices."""
    disks = storage_manager.list_disks()
    # Check if result has an error at the top level
    if disks and len(disks) == 1 and "error" in disks[0]:
        return {"disks": [], "warning": disks[0]["error"]}
    return {"disks": disks}


@router.get("/disks/{dev}")
async def disk_detail(dev: str, auth=Depends(require_auth)):
    """Single disk detail with SMART data."""
    result = storage_manager.get_disk_detail(dev)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/mounts")
async def list_mounts(auth=Depends(require_auth)):
    """List mounts with usage information."""
    mounts = storage_manager.list_mounts()
    if mounts and len(mounts) == 1 and "error" in mounts[0]:
        return {"mounts": [], "warning": mounts[0]["error"]}
    return {"mounts": mounts}


@router.post("/mount")
async def mount_filesystem(req: MountRequest, auth=Depends(require_auth)):
    """Mount a filesystem."""
    result = storage_manager.mount(req.device, req.target, req.fs_type)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "mount failed"))
    return result


@router.post("/unmount")
async def unmount_filesystem(req: UnmountRequest, auth=Depends(require_auth)):
    """Unmount a filesystem."""
    result = storage_manager.unmount(req.target)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "unmount failed"))
    return result


@router.get("/smart/{dev}")
async def smart_info(dev: str, auth=Depends(require_auth)):
    """Raw SMART info for a device."""
    result = storage_manager.get_smart_info(dev)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result
