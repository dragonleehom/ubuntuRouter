"""NFS export management API: exports, status, service control"""

import subprocess
import os
import shutil
import tempfile
from typing import List, Optional
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import require_auth

router = APIRouter()

EXPORTS_FILE = Path("/etc/exports")


# ─── Pydantic models ──────────────────────────────────────────────────────


class ExportClient(BaseModel):
    client: str = Field(..., min_length=1, description="Client spec, e.g. '192.168.1.0/24' or '*'")
    options: List[str] = Field(default_factory=lambda: ["rw", "sync", "no_subtree_check"])


class ExportCreate(BaseModel):
    path: str = Field(..., min_length=1, description="Absolute path to export")
    clients: List[ExportClient] = Field(..., min_length=1, description="At least one client")


class ExportUpdate(BaseModel):
    clients: Optional[List[ExportClient]] = None


class ExportEntry(BaseModel):
    path: str
    clients: List[ExportClient]


class ExportDeleteRequest(BaseModel):
    path: str


# ─── Helpers ──────────────────────────────────────────────────────────────


def _parse_exports(content: str) -> List[ExportEntry]:
    """Parse /etc/exports content into structured entries."""
    entries: List[ExportEntry] = []
    for line in content.splitlines():
        line = line.strip()
        # skip comments and blank lines
        if not line or line.startswith("#"):
            continue
        # Split on first whitespace to get path and client specs
        parts = line.split()
        if len(parts) < 2:
            continue
        path = parts[0]
        # Remaining parts are client(options) pairs
        clients: List[ExportClient] = []
        for spec in parts[1:]:
            spec = spec.strip()
            if "(" in spec and spec.endswith(")"):
                idx = spec.index("(")
                client = spec[:idx]
                opts_str = spec[idx + 1 : -1]
                options = [o.strip() for o in opts_str.split(",") if o.strip()]
            else:
                client = spec
                options = []
            clients.append(ExportClient(client=client, options=options))
        if clients:
            entries.append(ExportEntry(path=path, clients=clients))
    return entries


def _serialize_exports(entries: List[ExportEntry]) -> str:
    """Serialize export entries back to /etc/exports format."""
    lines: List[str] = []
    for entry in entries:
        client_specs = []
        for c in entry.clients:
            if c.options:
                client_specs.append(f"{c.client}({','.join(c.options)})")
            else:
                client_specs.append(c.client)
        lines.append(f"{entry.path}\t{' '.join(client_specs)}")
    return "\n".join(lines) + "\n"


def _read_exports() -> str:
    """Read the current /etc/exports file."""
    if not EXPORTS_FILE.exists():
        return ""
    return EXPORTS_FILE.read_text(encoding="utf-8")


def _write_exports_safe(content: str) -> None:
    """Atomically write /etc/exports using a temp file."""
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(dir=str(EXPORTS_FILE.parent), prefix=".exports-")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(tmp, 0o644)
        shutil.copy2(tmp, str(EXPORTS_FILE))
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def _exportfs_reload() -> None:
    """Reload NFS exports via exportfs -ra."""
    r = subprocess.run(
        ["exportfs", "-ra"],
        capture_output=True, text=True, timeout=15,
    )
    if r.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"exportfs failed: {r.stderr.strip() or r.stdout.strip()}",
        )


def _is_nfs_active() -> bool:
    """Check if nfs-kernel-server is active."""
    r = subprocess.run(
        ["systemctl", "is-active", "nfs-kernel-server"],
        capture_output=True, text=True, timeout=5,
    )
    return r.stdout.strip() == "active"


def _restart_nfs() -> None:
    """Restart nfs-kernel-server service."""
    r = subprocess.run(
        ["systemctl", "restart", "nfs-kernel-server"],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to restart nfs-kernel-server: {r.stderr.strip()}",
        )


def _start_nfs() -> None:
    """Start nfs-kernel-server service."""
    r = subprocess.run(
        ["systemctl", "start", "nfs-kernel-server"],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start nfs-kernel-server: {r.stderr.strip()}",
        )


def _stop_nfs() -> None:
    """Stop nfs-kernel-server service."""
    r = subprocess.run(
        ["systemctl", "stop", "nfs-kernel-server"],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop nfs-kernel-server: {r.stderr.strip()}",
        )


# ─── API Routes ───────────────────────────────────────────────────────────


@router.get("/exports")
async def get_exports(auth=Depends(require_auth)):
    """获取 NFS 导出列表"""
    content = _read_exports()
    entries = _parse_exports(content)
    return {"entries": [e.model_dump() for e in entries]}


@router.post("/exports")
async def create_export(req: ExportCreate, auth=Depends(require_auth)):
    """添加 NFS 导出"""
    # Validate path exists
    path_obj = Path(req.path)
    if not path_obj.exists():
        raise HTTPException(status_code=400, detail=f"路径不存在: {req.path}")
    if not path_obj.is_dir():
        raise HTTPException(status_code=400, detail=f"路径不是目录: {req.path}")

    # Read current exports
    content = _read_exports()
    entries = _parse_exports(content)

    # Check for duplicate path
    if any(e.path == req.path for e in entries):
        raise HTTPException(status_code=409, detail=f"导出路径已存在: {req.path}")

    # Append new export
    new_entry = ExportEntry(path=req.path, clients=req.clients)
    entries.append(new_entry)
    new_content = _serialize_exports(entries)

    # Back up original content in case exportfs fails
    original = content
    try:
        _write_exports_safe(new_content)
        _exportfs_reload()
    except HTTPException:
        # Rollback file change
        _write_exports_safe(original)
        raise

    return {"entry": new_entry.model_dump(), "message": "导出已添加"}


@router.put("/exports/{path:path}")
async def update_export(path: str, req: ExportUpdate, auth=Depends(require_auth)):
    """更新 NFS 导出"""
    content = _read_exports()
    entries = _parse_exports(content)

    # Find the export to update
    found = False
    for entry in entries:
        if entry.path == path:
            if req.clients is not None:
                entry.clients = req.clients
            found = True
            break

    if not found:
        raise HTTPException(status_code=404, detail=f"导出路径不存在: {path}")

    new_content = _serialize_exports(entries)
    original = content

    try:
        _write_exports_safe(new_content)
        _exportfs_reload()
    except HTTPException:
        _write_exports_safe(original)
        raise

    return {"message": "导出已更新"}


@router.delete("/exports/{path:path}")
async def delete_export(path: str, auth=Depends(require_auth)):
    """删除 NFS 导出"""
    content = _read_exports()
    entries = _parse_exports(content)

    # Filter out the export to delete
    new_entries = [e for e in entries if e.path != path]

    if len(new_entries) == len(entries):
        raise HTTPException(status_code=404, detail=f"导出路径不存在: {path}")

    new_content = _serialize_exports(new_entries)
    original = content

    try:
        _write_exports_safe(new_content)
        _exportfs_reload()
    except HTTPException:
        _write_exports_safe(original)
        raise

    return {"message": "导出已删除"}


@router.get("/status")
async def get_status(auth=Depends(require_auth)):
    """获取 NFS 服务状态"""
    active = _is_nfs_active()
    return {
        "active": active,
        "service": "nfs-kernel-server",
    }


@router.post("/start")
async def start_service(auth=Depends(require_auth)):
    """启动 NFS 服务"""
    _start_nfs()
    return {"message": "NFS 服务已启动", "active": True}


@router.post("/stop")
async def stop_service(auth=Depends(require_auth)):
    """停止 NFS 服务"""
    _stop_nfs()
    return {"message": "NFS 服务已停止", "active": False}


@router.post("/restart")
async def restart_service(auth=Depends(require_auth)):
    """重启 NFS 服务"""
    _restart_nfs()
    return {"message": "NFS 服务已重启", "active": True}
