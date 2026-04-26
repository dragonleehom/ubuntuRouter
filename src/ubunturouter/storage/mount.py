"""Mount management using findmnt, mount, and umount"""

import json
import subprocess
from typing import Optional


def list_mounts() -> list[dict]:
    """List all mounts with usage information via findmnt -J.

    Returns a list of dicts with: target, source, fs_type, size, used, avail,
    use_percent, options.
    """
    try:
        r = subprocess.run(
            ["findmnt", "-J", "-o", "TARGET,SOURCE,FSTYPE,SIZE,USED,AVAIL,USE%,OPTIONS"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            return _error_result("findmnt returned non-zero exit", stderr=r.stderr.strip())
    except FileNotFoundError:
        return _error_result("findmnt not installed")
    except subprocess.TimeoutExpired:
        return _error_result("findmnt timed out")
    except PermissionError:
        return _error_result("insufficient permissions to list mounts")
    except Exception as exc:
        return _error_result(f"failed to list mounts: {exc}")

    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return _error_result("failed to parse findmnt output")

    filesystems = data.get("filesystems", [])
    return [_parse_mount(fs) for fs in filesystems]


def _parse_mount(item: dict) -> dict:
    """Parse a single findmnt filesystem entry."""
    size_raw = item.get("size", "")
    used_raw = item.get("used", "")
    avail_raw = item.get("avail", "")
    use_pct = item.get("use%", "")

    return {
        "target": item.get("target", ""),
        "source": item.get("source", ""),
        "fs_type": item.get("fstype", ""),
        "size": size_raw,
        "size_bytes": _parse_findmnt_size(size_raw),
        "used": used_raw,
        "used_bytes": _parse_findmnt_size(used_raw),
        "avail": avail_raw,
        "avail_bytes": _parse_findmnt_size(avail_raw),
        "use_percent": use_pct,
        "options": item.get("options", ""),
    }


def _parse_findmnt_size(raw: str) -> Optional[int]:
    """Convert findmnt size strings like '238.5G' to bytes.

    findmnt can output sizes like '238.5G', '1.2T', '512M', '0', or '-' for no info.
    """
    if not raw or raw == "-" or raw == "0":
        return 0
    raw = raw.strip().upper()
    try:
        if raw.endswith("P"):
            return int(float(raw[:-1]) * 1024 ** 5)
        if raw.endswith("T"):
            return int(float(raw[:-1]) * 1024 ** 4)
        if raw.endswith("G"):
            return int(float(raw[:-1]) * 1024 ** 3)
        if raw.endswith("M"):
            return int(float(raw[:-1]) * 1024 ** 2)
        if raw.endswith("K"):
            return int(float(raw[:-1]) * 1024)
        return int(raw)
    except (ValueError, TypeError):
        return 0


def mount(device: str, target: str, fs_type: Optional[str] = None) -> dict:
    """Mount a device to a target path.

    Args:
        device: Device name (e.g. 'sda1')
        target: Mount target path
        fs_type: Optional filesystem type

    Returns:
        dict with success status and message.
    """
    cmd = ["mount"]
    if fs_type:
        cmd.extend(["-t", fs_type])
    cmd.extend([f"/dev/{device}", target])

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            return {"success": True, "message": f"Mounted /dev/{device} on {target}"}
        else:
            stderr = r.stderr.strip()
            return {"success": False, "message": stderr or "mount failed"}
    except FileNotFoundError:
        return {"success": False, "message": "mount command not found"}
    except subprocess.TimeoutExpired:
        return {"success": False, "message": "mount timed out"}
    except PermissionError:
        return {"success": False, "message": "insufficient permissions to mount"}
    except Exception as exc:
        return {"success": False, "message": f"mount failed: {exc}"}


def unmount(target: str) -> dict:
    """Unmount a filesystem by target path.

    Args:
        target: Mount target path to unmount

    Returns:
        dict with success status and message.
    """
    try:
        r = subprocess.run(["umount", target], capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            return {"success": True, "message": f"Unmounted {target}"}
        else:
            stderr = r.stderr.strip()
            return {"success": False, "message": stderr or "umount failed"}
    except FileNotFoundError:
        return {"success": False, "message": "umount command not found"}
    except subprocess.TimeoutExpired:
        return {"success": False, "message": "umount timed out"}
    except PermissionError:
        return {"success": False, "message": "insufficient permissions to unmount"}
    except Exception as exc:
        return {"success": False, "message": f"umount failed: {exc}"}


def _error_result(message: str, stderr: str = "") -> list[dict]:
    """Return a list with a single error entry."""
    entry: dict = {"error": message}
    if stderr:
        entry["stderr"] = stderr
    return [entry]
