"""Storage management API: disks, SMART, mounts, NFS, CIFS"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

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


class NfsMountRequest(BaseModel):
    """NFS mount request body."""
    server: str = Field(..., description="NFS server address")
    remote_path: str = Field(..., description="Remote export path (e.g. '/exports/data')")
    mount_point: str = Field(..., description="Local mount point (e.g. '/mnt/nfs_data')")
    options: str | None = Field(None, description="Mount options (e.g. 'vers=4.2,soft,timeo=100')")


class CifsMountRequest(BaseModel):
    """CIFS/SMB mount request body."""
    server: str = Field(..., description="SMB server address")
    share: str = Field(..., description="Share name (e.g. 'shared')")
    mount_point: str = Field(..., description="Local mount point (e.g. '/mnt/smb_share')")
    username: str | None = Field(None, description="SMB username")
    password: str | None = Field(None, description="SMB password")
    domain: str | None = Field(None, description="SMB domain/workgroup")
    options: str | None = Field(None, description="Additional mount options (e.g. 'vers=3.0,sec=ntlmssp')")


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


# ═══════════════════════════════════════════════════════════════════════════════
# NFS / CIFS 网络共享挂载
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/mount/nfs")
async def mount_nfs(req: NfsMountRequest, auth=Depends(require_auth)):
    """挂载 NFS 网络共享"""
    import subprocess
    from pathlib import Path
    try:
        # 创建挂载点
        Path(req.mount_point).mkdir(parents=True, exist_ok=True)
        # 构建 mount 命令
        source = f"{req.server}:{req.remote_path}"
        cmd = ["mount", "-t", "nfs"]
        if req.options:
            cmd.extend(["-o", req.options])
        cmd.extend([source, req.mount_point])
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            raise HTTPException(status_code=400, detail=f"NFS 挂载失败: {r.stderr.strip()}")
        # 尝试添加到 fstab
        _add_to_fstab(source, req.mount_point, "nfs", req.options or "defaults")
        return {"success": True, "message": f"NFS 共享 {source} 已挂载到 {req.mount_point}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"NFS 挂载失败: {e}")


@router.post("/mount/cifs")
async def mount_cifs(req: CifsMountRequest, auth=Depends(require_auth)):
    """挂载 CIFS/SMB 网络共享"""
    import subprocess
    from pathlib import Path
    try:
        # 创建挂载点
        Path(req.mount_point).mkdir(parents=True, exist_ok=True)
        # 构建 mount 命令
        source = f"//{req.server}/{req.share}"
        cmd = ["mount", "-t", "cifs"]
        opts = []
        if req.username:
            opts.append(f"username={req.username}")
        if req.password:
            opts.append(f"password={req.password}")
        if req.domain:
            opts.append(f"domain={req.domain}")
        if req.options:
            opts.append(req.options)
        if opts:
            cmd.extend(["-o", ",".join(opts)])
        cmd.extend([source, req.mount_point])
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            raise HTTPException(status_code=400, detail=f"CIFS 挂载失败: {r.stderr.strip()}")
        # 添加到 fstab（注意：不写入密码到 fstab）
        fstab_opts = f"username={req.username or 'guest'}"
        if req.domain:
            fstab_opts += f",domain={req.domain}"
        if req.options:
            fstab_opts += f",{req.options}"
        _add_to_fstab(source, req.mount_point, "cifs", fstab_opts)
        return {"success": True, "message": f"CIFS 共享 {source} 已挂载到 {req.mount_point}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CIFS 挂载失败: {e}")


def _add_to_fstab(source: str, mount_point: str, fs_type: str, options: str):
    """添加条目到 /etc/fstab（如果不存在）"""
    from pathlib import Path
    fstab = Path("/etc/fstab")
    entry = f"{source} {mount_point} {fs_type} {options} 0 0"
    if fstab.exists():
        content = fstab.read_text()
        if source in content and mount_point in content:
            return  # 已存在，不重复添加
    with open(fstab, "a") as f:
        f.write(f"\n{entry}\n")
