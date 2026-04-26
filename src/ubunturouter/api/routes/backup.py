"""System Backup API routes — config backup and restore"""

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from typing import Optional

from ..deps import require_auth
from ...backup import BackupManager

router = APIRouter()
backup_manager = BackupManager()


class BackupCreateRequest(BaseModel):
    description: Optional[str] = Field("", description="Optional backup description")


class BackupDeleteRequest(BaseModel):
    backup_id: str = Field(..., min_length=1, description="Backup ID to delete")


@router.get("/list")
async def list_backups(auth=Depends(require_auth)):
    """List all available configuration backups."""
    return backup_manager.list_backups()


@router.post("/create")
async def create_backup(body: BackupCreateRequest, auth=Depends(require_auth)):
    """Create a new configuration backup."""
    result = backup_manager.create_backup(body.description)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message"))
    return result


@router.delete("/{backup_id}")
async def delete_backup(backup_id: str, auth=Depends(require_auth)):
    """Delete a backup by ID."""
    result = backup_manager.delete_backup(backup_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result


@router.get("/{backup_id}/download")
async def download_backup(backup_id: str, auth=Depends(require_auth)):
    """Download a backup archive file."""
    content = backup_manager.get_backup_content(backup_id)
    if content is None:
        raise HTTPException(status_code=404, detail=f"Backup {backup_id} not found")
    return Response(
        content=content,
        media_type="application/gzip",
        headers={"Content-Disposition": f'attachment; filename="{backup_id}.tar.gz"'},
    )


@router.get("/{backup_id}/preview")
async def preview_backup(backup_id: str, auth=Depends(require_auth)):
    """Preview files contained in a backup."""
    result = backup_manager.preview_restore(backup_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result


@router.post("/{backup_id}/restore")
async def restore_backup(backup_id: str, auth=Depends(require_auth)):
    """Restore configuration from a backup."""
    result = backup_manager.restore_backup(backup_id)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message"))
    return result
