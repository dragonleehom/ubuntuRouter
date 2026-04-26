"""系统 API: status / logs / backup / snapshots / upgrade / reboot / shutdown"""

import subprocess
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import require_auth
from ...engine.engine import ConfigEngine
from ...engine.rollback import RollbackManager


router = APIRouter()

# ─── 状态 ───────────────────────────────────────────────────────────


@router.get("/status")
async def system_status(auth=Depends(require_auth)):
    """系统健康状态"""
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

# ─── OTA 在线升级 ─────────────────────────────────────────────────


@router.get("/upgrade/check")
async def check_upgrade(auth=Depends(require_auth)):
    """检查可升级的软件包 (apt list --upgradable)"""
    result = {
        "current_version": _get_app_version(),
        "upgradable": [],
        "count": 0,
        "has_updates": False,
    }
    try:
        r = subprocess.run(
            ["apt", "list", "--upgradable", "-q"],
            capture_output=True, text=True, timeout=30,
        )
        # 解析输出: pkg/stable 1.2.3 amd64 [upgradable from: 1.2.2]
        lines = r.stdout.strip().split("\n")
        # 跳过第一行 "Listing..."
        for line in lines:
            line = line.strip()
            if not line or line.startswith("Listing") or "..." in line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                pkg_info = parts[0]
                version_info = parts[1] if len(parts) > 1 else ""
                result["upgradable"].append({
                    "package": pkg_info,
                    "version": version_info,
                })
        result["count"] = len(result["upgradable"])
        result["has_updates"] = result["count"] > 0
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="apt list --upgradable 超时")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return result


@router.post("/upgrade/run")
async def run_upgrade(auth=Depends(require_auth)):
    """执行系统升级 (apt upgrade)"""
    try:
        # 后台运行，避免长时间阻塞 HTTP 请求
        proc = subprocess.Popen(
            ["apt-get", "upgrade", "-y"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = proc.communicate(timeout=600)
        return {
            "success": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": stdout.strip().split("\n")[-50:],
            "stderr": stderr.strip().split("\n")[-20:],
        }
    except subprocess.TimeoutExpired:
        proc.kill()
        raise HTTPException(status_code=504, detail="apt upgrade 超时 (10分钟)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upgrade/dist-upgrade")
async def run_dist_upgrade(auth=Depends(require_auth)):
    """执行发行版升级 (apt dist-upgrade)"""
    try:
        proc = subprocess.Popen(
            ["apt-get", "dist-upgrade", "-y"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = proc.communicate(timeout=600)
        return {
            "success": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": stdout.strip().split("\n")[-50:],
            "stderr": stderr.strip().split("\n")[-20:],
        }
    except subprocess.TimeoutExpired:
        proc.kill()
        raise HTTPException(status_code=504, detail="apt dist-upgrade 超时 (10分钟)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upgrade/apt-update")
async def run_apt_update(auth=Depends(require_auth)):
    """刷新包索引 (apt update)"""
    try:
        r = subprocess.run(
            ["apt-get", "update", "-qq"],
            capture_output=True, text=True, timeout=300,
        )
        return {
            "success": r.returncode == 0,
            "returncode": r.returncode,
            "stdout": r.stdout.strip().split("\n")[-20:],
            "stderr": r.stderr.strip().split("\n")[-20:],
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="apt update 超时")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─── 重启 / 关机 ─────────────────────────────────────────────────


class RebootShutdownRequest(BaseModel):
    delay: int = 0  # 延迟秒数


@router.post("/reboot")
async def reboot_system(body: RebootShutdownRequest = RebootShutdownRequest(), auth=Depends(require_auth)):
    """重启系统"""
    try:
        if body.delay > 0:
            subprocess.run(
                ["shutdown", "-r", f"+{body.delay // 60}" if body.delay >= 60 else f"+{body.delay // 60}"],
                capture_output=True, text=True, timeout=10,
            )
            return {"message": f"系统将在 {body.delay} 秒后重启", "delay": body.delay}
        else:
            # 立即重启
            subprocess.Popen(["systemctl", "reboot"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"message": "系统正在重启..."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/shutdown")
async def shutdown_system(body: RebootShutdownRequest = RebootShutdownRequest(), auth=Depends(require_auth)):
    """关机"""
    try:
        if body.delay > 0:
            subprocess.run(
                ["shutdown", "-h", f"+{body.delay // 60}"],
                capture_output=True, text=True, timeout=10,
            )
            return {"message": f"系统将在 {body.delay} 秒后关机", "delay": body.delay}
        else:
            subprocess.Popen(["systemctl", "poweroff"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"message": "系统正在关机..."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─── 辅助 ──────────────────────────────────────────────────────────


def _get_app_version() -> str:
    """获取当前应用版本号"""
    version_file = Path("/opt/ubunturouter/VERSION")
    if version_file.exists():
        return version_file.read_text().strip()
    return "0.1.0"


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
