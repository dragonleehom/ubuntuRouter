"""系统 API: status / logs / backup / snapshots / upgrade"""

import subprocess
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException

from ..deps import require_auth
from ...engine.engine import ConfigEngine
from ...engine.rollback import RollbackManager


router = APIRouter()


@router.get("/status")
async def system_status(auth=Depends(require_auth)):
    """系统健康状态"""
    # 检查配置
    engine = ConfigEngine()
    initialized = engine.exists()

    # 检查服务
    services = {}
    for svc in ["dnsmasq", "nftables", "ssh", "systemd-networkd"]:
        try:
            r = subprocess.run(["systemctl", "is-active", svc], capture_output=True, text=True, timeout=5)
            r2 = subprocess.run(["systemctl", "is-enabled", svc], capture_output=True, text=True, timeout=5)
            services[svc] = {"active": r.stdout.strip() == "active", "enabled": r2.stdout.strip() == "enabled"}
        except Exception:
            services[svc] = {"active": False, "enabled": False}

    return {
        "initialized": initialized,
        "hostname": _get_hostname(),
        "os": _get_os_info(),
        "services": services,
    }


@router.get("/logs")
async def system_logs(lines: int = 50, service: str = "ubunturouter", auth=Depends(require_auth)):
    """查看系统日志"""
    try:
        r = subprocess.run(
            ["journalctl", "-u", service, "-n", str(lines), "--no-pager", "-o", "short-precise"],
            capture_output=True, text=True, timeout=10
        )
        return {"service": service, "lines": r.stdout.split("\n")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapshots")
async def list_snapshots(auth=Depends(require_auth)):
    """列出配置快照"""
    engine = ConfigEngine()
    rollback = RollbackManager(snapshot_dir=engine.snapshot_dir)
    snaps = rollback.list_snapshots()
    return {"snapshots": snaps}


@router.get("/upgrade")
async def check_upgrade(auth=Depends(require_auth)):
    """检查更新（占位）"""
    return {
        "current_version": "0.1.0",
        "latest_version": "0.1.0",
        "upgrade_available": False,
    }


def _get_hostname() -> str:
    try:
        return Path("/etc/hostname").read_text().strip()
    except Exception:
        try:
            r = subprocess.run(["hostname"], capture_output=True, text=True, timeout=3)
            return r.stdout.strip()
        except Exception:
            return "ubunturouter"


def _get_os_info() -> dict:
    info = {"distro": "Ubuntu"}
    os_file = Path("/etc/os-release")
    if os_file.exists():
        for line in os_file.read_text().split("\n"):
            if line.startswith("VERSION_ID="):
                info["version"] = line.split("=")[1].strip('"')
            elif line.startswith("VERSION_CODENAME="):
                info["codename"] = line.split("=")[1].strip('"')
    return info
