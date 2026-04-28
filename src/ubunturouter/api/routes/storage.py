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


# ═══════════════════════════════════════════════════════════════════════════════
# HDD APM / 休眠管理
# ═══════════════════════════════════════════════════════════════════════════════

import subprocess
import re
from pathlib import Path


class ApmSetRequest(BaseModel):
    """APM/休眠设置请求体"""
    apm_level: int | None = Field(None, ge=1, le=255, description="APM 级别 (1-255)")
    spindown_timeout: int | None = Field(None, ge=0, le=255, description="休眠超时 (hdparm -S 值, 0=禁用, 1=5秒, 12=1分钟, 240=20分钟)")


APM_LEVEL_NAMES = {
    (1, 63): "高性能（极低延迟）",
    (64, 127): "性能优先",
    (128, 254): "中间值（允许旋转降速）",
    (255, 255): "禁用 APM",
}

SPINDOWN_TIMEOUT_NAMES = {
    0: "永不超时",
    1: "5 秒",
    2: "10 秒",
    3: "15 秒",
    4: "20 秒",
    5: "25 秒",
    6: "30 秒",
    7: "35 秒",
    8: "40 秒",
    9: "45 秒",
    10: "50 秒",
    11: "55 秒",
    12: "1 分钟",
    13: "1.5 分钟",
    14: "2 分钟",
    15: "2.5 分钟",
    16: "3 分钟",
    17: "3.5 分钟",
    18: "4 分钟",
    19: "4.5 分钟",
    20: "5 分钟",
    21: "5.5 分钟",
    22: "6 分钟",
    23: "6.5 分钟",
    24: "7 分钟",
    25: "7.5 分钟",
    26: "8 分钟",
    27: "8.5 分钟",
    28: "9 分钟",
    29: "9.5 分钟",
    30: "10 分钟",
    31: "10.5 分钟",
    32: "11 分钟",
    33: "11.5 分钟",
    34: "12 分钟",
    35: "12.5 分钟",
    36: "13 分钟",
    37: "13.5 分钟",
    38: "14 分钟",
    39: "14.5 分钟",
    40: "15 分钟",
    41: "15.5 分钟",
    42: "16 分钟",
    43: "16.5 分钟",
    44: "17 分钟",
    45: "17.5 分钟",
    46: "18 分钟",
    47: "18.5 分钟",
    48: "19 分钟",
    49: "19.5 分钟",
    50: "20 分钟",
    55: "27.5 分钟",
    60: "30 分钟",
    65: "32.5 分钟",
    70: "35 分钟",
    75: "37.5 分钟",
    80: "40 分钟",
    85: "42.5 分钟",
    90: "45 分钟",
    95: "47.5 分钟",
    100: "50 分钟",
    105: "52.5 分钟",
    110: "55 分钟",
    115: "57.5 分钟",
    120: "1 小时",
    121: "1 小时 5 秒",
    125: "1 小时 2.5 分钟",
    130: "1 小时 5 分钟",
    135: "1 小时 7.5 分钟",
    140: "1 小时 10 分钟",
    145: "1 小时 12.5 分钟",
    150: "1 小时 15 分钟",
    155: "1 小时 17.5 分钟",
    160: "1 小时 20 分钟",
    165: "1 小时 22.5 分钟",
    170: "1 小时 25 分钟",
    175: "1 小时 27.5 分钟",
    180: "1 小时 30 分钟",
    185: "1 小时 32.5 分钟",
    190: "1 小时 35 分钟",
    195: "1 小时 37.5 分钟",
    200: "1 小时 40 分钟",
    205: "1 小时 42.5 分钟",
    210: "1 小时 45 分钟",
    215: "1 小时 47.5 分钟",
    220: "1 小时 50 分钟",
    225: "1 小时 52.5 分钟",
    230: "1 小时 55 分钟",
    235: "1 小时 57.5 分钟",
    240: "2 小时",
    241: "2 小时 5 秒",
    245: "2 小时 2.5 分钟",
    250: "2 小时 5 分钟",
    251: "2 小时 5 分 5 秒",
    252: "2 小时 10 分钟",
    253: "2 小时 12.5 分钟",
    254: "2 小时 15 分钟",
    255: "2 小时 17.5 分钟",
}


def _check_hdparm() -> bool:
    """检查 hdparm 是否已安装"""
    r = subprocess.run(["which", "hdparm"], capture_output=True, text=True, timeout=5)
    return r.returncode == 0


def _get_apm_level_name(level: int) -> str:
    """根据 APM 级别返回人类可读的名称"""
    for (lo, hi), name in sorted(APM_LEVEL_NAMES.items(), key=lambda x: x[0][0]):
        if lo <= level <= hi:
            return name
    return f"未知级别 ({level})"


def _get_spindown_timeout_name(seconds: int) -> str:
    """根据休眠超时秒数返回人类可读的名称"""
    if seconds == 0:
        return "永不超时"
    # hdparm -S 使用特殊值
    # 值 1-240 = 5秒 * value
    # 值 241-251 = 30分钟 * (value - 240)
    # 值 252-255 = hdparm 文档中的特殊值
    minutes = seconds / 60
    if minutes < 1:
        return f"{seconds} 秒"
    if minutes == 1:
        return "1 分钟"
    if minutes < 60:
        return f"{int(minutes)} 分钟"
    hours = minutes / 60
    if hours == int(hours):
        return f"{int(hours)} 小时"
    return f"{int(hours)} 小时 {int((minutes % 60))} 分钟"


def _parse_hdparm_B_output(stdout: str) -> dict:
    """解析 hdparm -B 的输出，返回 APM 信息"""
    apm_enabled = False
    apm_level = None

    # 匹配格式: "setting Advanced Power Management level to 0x80 (128)"
    # 或: " Advanced Power Management level: 0x80 (128)"
    m = re.search(r'level[:\s]+0x[0-9a-fA-F]+\s*\((\d+)\)', stdout)
    if m:
        apm_level = int(m.group(1))
        apm_enabled = True
    else:
        # 匹配 "APM_level = 128" 或其他格式
        m = re.search(r'APM_level[:\s]*=?[:\s]*(\d+)', stdout, re.IGNORECASE)
        if m:
            apm_level = int(m.group(1))
            apm_enabled = True
        elif re.search(r'APM[^:]*:\s+not\s+supported', stdout, re.IGNORECASE):
            apm_enabled = False
        elif re.search(r'APM[^:]*:\s+off/\s+not\s+supported', stdout, re.IGNORECASE):
            apm_enabled = False

    return {
        "apm_enabled": apm_enabled,
        "apm_level": apm_level,
    }


def _parse_hdparm_S_output(stdout: str) -> dict:
    """解析 hdparm -S 的输出，返回 spindown 信息"""
    # spindown 值: 0=禁用, 1-240=5秒*value, 241-251=30分*(value-240)
    # 标准超时: value 0 = 永不, value 1 = 5秒 ...
    # hdparm -S 显示 "setting standby to 30 (5 seconds)"
    value = 0

    m = re.search(r'standby\s+to\s+(\d+)', stdout, re.IGNORECASE)
    if m:
        value = int(m.group(1))

    return {
        "spindown_timeout": value,
        "spindown_timeout_seconds": _spindown_value_to_seconds(value),
    }


def _spindown_value_to_seconds(value: int) -> int:
    """将 hdparm -S 值转换为秒数"""
    if value == 0:
        return 0
    if 1 <= value <= 240:
        return value * 5
    if 241 <= value <= 251:
        return (value - 240) * 30 * 60
    if value == 252:
        return 21 * 60  # 21 分钟
    if value == 253:
        return (8 * 60 + 5 * 60)  # hdparm 指定值 ~8小时
    if value == 254:
        return (10 * 60 + 5 * 60)  # 预留
    if value == 255:
        return 21 * 60 + 15 * 60  # 超级长
    return 0


def _parse_hdparm_C_output(stdout: str) -> str:
    """解析 hdparm -C 的输出，返回磁盘状态"""
    m = re.search(r'drive state is:\s+(\S+)', stdout, re.IGNORECASE)
    if m:
        return m.group(1).lower()
    return "unknown"


def _get_device_info(dev: str) -> dict:
    """获取磁盘基本信息和型号"""
    try:
        r = subprocess.run(
            ["lsblk", "-J", "-o", "NAME,MODEL,ROTA", f"/dev/{dev}"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            import json
            data = json.loads(r.stdout)
            devices = data.get("blockdevices", [])
            if devices:
                return {
                    "model": devices[0].get("model", "").strip() or "Unknown",
                    "is_rotational": devices[0].get("rota") == "1",
                }
    except Exception:
        pass
    return {"model": "Unknown", "is_rotational": True}


def _is_system_disk(dev: str) -> bool:
    """检查是否是系统盘（root 设备）"""
    try:
        r = subprocess.run(
            ["findmnt", "-n", "-o", "SOURCE", "/"],
            capture_output=True, text=True, timeout=10,
        )
        root_src = r.stdout.strip()
        # root_src 可能是 /dev/sda2 或 /dev/mmcblk0p2 等
        # 提取基础设备名
        import re
        m = re.match(r'/dev/([a-zA-Z]+)', root_src)
        if m and m.group(1) == dev:
            return True
        m = re.match(r'/dev/(mmcblk\d+)', root_src)
        if m:
            base = m.group(1)
            if dev == base or dev.startswith(base):
                return True
    except Exception:
        pass
    return False


@router.get("/disks/{dev}/apm")
async def get_apm_status(dev: str, auth=Depends(require_auth)):
    """获取磁盘 APM/休眠状态"""
    # 检查设备是否存在
    dev_path = Path(f"/dev/{dev}")
    if not dev_path.is_block_device():
        raise HTTPException(status_code=404, detail=f"设备 /dev/{dev} 不存在或不是块设备")

    # 检查 hdparm
    if not _check_hdparm():
        raise HTTPException(status_code=400, detail="hdparm 未安装，请先安装: sudo apt install hdparm")

    result = {
        "device": dev,
        "model": "Unknown",
        "apm_enabled": False,
        "apm_level": None,
        "apm_level_name": None,
        "spindown_timeout": 0,
        "spindown_timeout_seconds": 0,
        "spindown_timeout_name": "永不超时",
        "status": "unknown",
    }

    # 获取设备信息
    dev_info = _get_device_info(dev)
    result["model"] = dev_info["model"]

    # 获取 APM 级别
    try:
        r = subprocess.run(
            ["sudo", "hdparm", "-B", f"/dev/{dev}"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            apm_info = _parse_hdparm_B_output(r.stdout)
            result["apm_enabled"] = apm_info["apm_enabled"]
            result["apm_level"] = apm_info["apm_level"]
            if apm_info["apm_level"] is not None:
                result["apm_level_name"] = _get_apm_level_name(apm_info["apm_level"])
    except Exception as e:
        # APM 可能不被支持
        result["apm_enabled"] = False

    # 获取休眠超时
    try:
        r = subprocess.run(
            ["sudo", "hdparm", "-S", f"/dev/{dev}"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            spindown_info = _parse_hdparm_S_output(r.stdout)
            result["spindown_timeout"] = spindown_info["spindown_timeout"]
            result["spindown_timeout_seconds"] = spindown_info["spindown_timeout_seconds"]
            result["spindown_timeout_name"] = _get_spindown_timeout_name(spindown_info["spindown_timeout_seconds"])
    except Exception:
        pass

    # 获取磁盘状态
    try:
        r = subprocess.run(
            ["sudo", "hdparm", "-C", f"/dev/{dev}"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            result["status"] = _parse_hdparm_C_output(r.stdout)
    except Exception:
        pass

    return result


@router.post("/disks/{dev}/apm")
async def set_apm(dev: str, req: ApmSetRequest, auth=Depends(require_auth)):
    """设置磁盘 APM 级别和/或休眠超时"""
    # 检查设备
    dev_path = Path(f"/dev/{dev}")
    if not dev_path.is_block_device():
        raise HTTPException(status_code=404, detail=f"设备 /dev/{dev} 不存在或不是块设备")

    # 检查是否是系统盘
    if _is_system_disk(dev):
        raise HTTPException(status_code=400, detail=f"不允许修改系统盘 {dev} 的休眠设置")

    # 检查 hdparm
    if not _check_hdparm():
        raise HTTPException(status_code=400, detail="hdparm 未安装，请先安装: sudo apt install hdparm")

    # 至少提供一个参数
    if req.apm_level is None and req.spindown_timeout is None:
        raise HTTPException(status_code=400, detail="至少需要提供 apm_level 或 spindown_timeout 参数")

    results = {}
    errors = []

    # 设置 APM 级别
    if req.apm_level is not None:
        try:
            r = subprocess.run(
                ["sudo", "hdparm", "-B", str(req.apm_level), f"/dev/{dev}"],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode == 0:
                results["apm_level"] = req.apm_level
                results["apm_level_name"] = _get_apm_level_name(req.apm_level)
            else:
                errors.append(f"设置 APM 级别失败: {r.stderr.strip()}")
        except Exception as e:
            errors.append(f"设置 APM 级别异常: {e}")

    # 设置休眠超时
    if req.spindown_timeout is not None:
        try:
            r = subprocess.run(
                ["sudo", "hdparm", "-S", str(req.spindown_timeout), f"/dev/{dev}"],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode == 0:
                seconds = _spindown_value_to_seconds(req.spindown_timeout)
                results["spindown_timeout"] = req.spindown_timeout
                results["spindown_timeout_seconds"] = seconds
                results["spindown_timeout_name"] = _get_spindown_timeout_name(seconds)
            else:
                errors.append(f"设置休眠超时失败: {r.stderr.strip()}")
        except Exception as e:
            errors.append(f"设置休眠超时异常: {e}")

    # 重新获取完整状态
    final_result = None
    try:
        # 使用 get_apm_status 内部逻辑重新获取
        r_b = subprocess.run(
            ["sudo", "hdparm", "-B", f"/dev/{dev}"],
            capture_output=True, text=True, timeout=10,
        )
        if r_b.returncode == 0:
            apm_info = _parse_hdparm_B_output(r_b.stdout)
            results["apm_enabled"] = apm_info["apm_enabled"]
            if apm_info.get("apm_level") is not None and "apm_level" not in results:
                results["apm_level"] = apm_info["apm_level"]
                results["apm_level_name"] = _get_apm_level_name(apm_info["apm_level"])

        r_s = subprocess.run(
            ["sudo", "hdparm", "-S", f"/dev/{dev}"],
            capture_output=True, text=True, timeout=10,
        )
        if r_s.returncode == 0:
            spindown_info = _parse_hdparm_S_output(r_s.stdout)
            if "spindown_timeout" not in results:
                results["spindown_timeout"] = spindown_info["spindown_timeout"]
                results["spindown_timeout_seconds"] = spindown_info["spindown_timeout_seconds"]
                results["spindown_timeout_name"] = _get_spindown_timeout_name(spindown_info["spindown_timeout_seconds"])

        r_c = subprocess.run(
            ["sudo", "hdparm", "-C", f"/dev/{dev}"],
            capture_output=True, text=True, timeout=10,
        )
        if r_c.returncode == 0:
            results["status"] = _parse_hdparm_C_output(r_c.stdout)
    except Exception:
        pass

    response = {
        "device": dev,
        "success": len(errors) == 0,
        **results,
    }
    if errors:
        response["errors"] = errors

    return response
