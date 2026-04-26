"""Samba share management API: status, shares, users"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from ..deps import require_auth
from ...storage.samba import SambaManager

router = APIRouter()
sm = SambaManager()


# ─── Pydantic models ──────────────────────────────────────────────────────

_SHARE_NAME_PATTERN = r"^[a-z0-9\-]+$"


class ShareCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=_SHARE_NAME_PATTERN,
        description="Share name: lowercase letters, numbers, hyphens only",
    )
    path: str = Field(..., min_length=1, description="Absolute path to the shared directory")
    writable: bool = True
    guest_ok: bool = False
    valid_users: str = ""


class ShareUpdate(BaseModel):
    path: Optional[str] = Field(None, min_length=1)
    writable: Optional[bool] = None
    guest_ok: Optional[bool] = None
    valid_users: Optional[str] = None


class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=64, description="System username to add as Samba user")
    password: str = Field(..., min_length=1, description="Samba password for the user")


# ─── Status & Service Control ─────────────────────────────────────────────


@router.get("/status")
async def get_status(auth=Depends(require_auth)):
    """Get Samba service status, smbstatus output, and config summary."""
    return sm.get_status()


@router.post("/start")
async def start_samba(auth=Depends(require_auth)):
    """Start smbd and nmbd services."""
    return sm.start()


@router.post("/stop")
async def stop_samba(auth=Depends(require_auth)):
    """Stop smbd and nmbd services."""
    return sm.stop()


@router.post("/restart")
async def restart_samba(auth=Depends(require_auth)):
    """Restart smbd and nmbd services."""
    return sm.restart()


# ─── Shares ────────────────────────────────────────────────────────────────


@router.get("/shares")
async def list_shares(auth=Depends(require_auth)):
    """List all Samba shares."""
    shares = sm.list_shares()
    return {"shares": shares, "count": len(shares)}


@router.post("/shares")
async def add_share(body: ShareCreate, auth=Depends(require_auth)):
    """Add a new Samba share."""
    result = sm.add_share(
        name=body.name,
        path=body.path,
        writable=body.writable,
        guest_ok=body.guest_ok,
        valid_users=body.valid_users,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "failed to add share"))
    return result


@router.put("/shares/{name}")
async def update_share(name: str, body: ShareUpdate, auth=Depends(require_auth)):
    """Update an existing Samba share."""
    result = sm.update_share(
        name=name,
        path=body.path,
        writable=body.writable,
        guest_ok=body.guest_ok,
        valid_users=body.valid_users,
    )
    if not result.get("success"):
        raise HTTPException(status_code=404 if "not found" in result.get("message", "").lower() else 400,
                            detail=result.get("message", "failed to update share"))
    return result


@router.delete("/shares/{name}")
async def delete_share(name: str, auth=Depends(require_auth)):
    """Delete a Samba share."""
    result = sm.delete_share(name)
    if not result.get("success"):
        raise HTTPException(status_code=404 if "not found" in result.get("message", "").lower() else 400,
                            detail=result.get("message", "failed to delete share"))
    return result


# ─── Users ─────────────────────────────────────────────────────────────────


@router.get("/users")
async def list_users(auth=Depends(require_auth)):
    """List Samba users."""
    users = sm.list_users()
    return {"users": users, "count": len(users)}


@router.post("/users")
async def add_user(body: UserCreate, auth=Depends(require_auth)):
    """Add a Samba user."""
    result = sm.add_user(username=body.username, password=body.password)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "failed to add user"))
    return result


@router.delete("/users/{username}")
async def delete_user(username: str, auth=Depends(require_auth)):
    """Delete a Samba user."""
    result = sm.delete_user(username)
    if not result.get("success"):
        raise HTTPException(status_code=404 if "not found" in result.get("message", "").lower() else 400,
                            detail=result.get("message", "failed to delete user"))
    return result
