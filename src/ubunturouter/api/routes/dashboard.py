"""Dashboard 全量状态 API — + 快捷操作路由"""

import subprocess
import json
import asyncio
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from ..deps import require_auth
from ...engine.engine import ConfigEngine


router = APIRouter()


# --- 快捷操作 --------------------------------------------------


@router.post("/action/refresh-services")
async def action_refresh_services(auth=Depends(require_auth)):
    """刷新所有系统服务"""
    try:
        subprocess.run(["systemctl", "daemon-reload"], timeout=10)
        subprocess.run(["systemctl", "restart", "ubunturouter"], timeout=30)
        return {"ok": True, "message": "服务已刷新"}
    except Exception as e:
        raise HTTPException(500, f"刷新失败: {e}")


@router.post("/action/reboot")
async def action_reboot(auth=Depends(require_auth)):
    """重启系统"""
    try:
        subprocess.Popen(["sudo", "shutdown", "-r", "+1", "系统将在1分钟后重启"])
        return {"ok": True, "message": "系统将在1分钟后重启"}
    except Exception as e:
        raise HTTPException(500, f"重启失败: {e}")


@router.post("/action/shutdown")
async def action_shutdown(auth=Depends(require_auth)):
    """关机系统"""
    try:
        subprocess.Popen(["sudo", "shutdown", "-h", "+1", "系统将在1分钟后关机"])
        return {"ok": True, "message": "系统将在1分钟后关机"}
    except Exception as e:
        raise HTTPException(500, f"关机失败: {e}")


@router.post("/action/check-updates")
async def action_check_updates(auth=Depends(require_auth)):
    """检查系统更新"""
    try:
        r = subprocess.run(
            ["apt", "list", "--upgradable", "2>/dev/null"],
            capture_output=True, text=True, timeout=30, shell=True
        )
        lines = [l for l in r.stdout.split("\n") if l.strip() and "..." not in l]
        packages = []
        for l in lines[1:]:
            parts = l.split()
            if len(parts) >= 2:
                packages.append(parts[0])
        return {"ok": True, "updates_available": len(packages), "packages": packages[:20]}
    except Exception as e:
        raise HTTPException(500, f"检查更新失败: {e}")


@router.post("/action/apply-updates")
async def action_apply_updates(auth=Depends(require_auth)):
    """应用系统更新"""
    try:
        subprocess.Popen(
            ["sudo", "apt", "upgrade", "-y"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return {"ok": True, "message": "系统更新已开始（后台运行）"}
    except Exception as e:
        raise HTTPException(500, f"更新失败: {e}")


@router.post("/action/start-service/{name}")
async def action_start_service(name: str, auth=Depends(require_auth)):
    """启动指定服务"""
    try:
        r = subprocess.run(
            ["sudo", "systemctl", "start", name],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode != 0:
            raise HTTPException(500, r.stderr.strip())
        return {"ok": True, "message": f"{name} 已启动"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"启动失败: {e}")


@router.post("/action/stop-service/{name}")
async def action_stop_service(name: str, auth=Depends(require_auth)):
    """停止指定服务"""
    try:
        r = subprocess.run(
            ["sudo", "systemctl", "stop", name],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode != 0:
            raise HTTPException(500, r.stderr.strip())
        return {"ok": True, "message": f"{name} 已停止"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"停止失败: {e}")


@router.post("/action/restart-service/{name}")
async def action_restart_service(name: str, auth=Depends(require_auth)):
    """重启指定服务"""
    try:
        r = subprocess.run(
            ["sudo", "systemctl", "restart", name],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode != 0:
            raise HTTPException(500, r.stderr.strip())
        return {"ok": True, "message": f"{name} 已重启"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"重启失败: {e}")


# --- Dashboard 状态 --------------------------------------------


def _get_system_stats() -> dict:
    """获取系统统计信息"""
    stats = {}
    try:
        # CPU
        r = subprocess.run(
            ["sh", "-c", "top -bn1 | grep 'Cpu(s)' | awk '{print $2+$4}'"],
            capture_output=True, text=True, timeout=5
        )
        stats["cpu_usage"] = float(r.stdout.strip() or 0)

        # 内存
        r = subprocess.run(
            ["sh", "-c", "free -m | awk '/Mem:/ {print $3, $2}'"],
            capture_output=True, text=True, timeout=5
        )
        parts = r.stdout.strip().split()
        if len(parts) == 2:
            stats["memory"] = {"used_mb": int(parts[0]), "total_mb": int(parts[1])}

        # 磁盘
        r = subprocess.run(
            ["df", "-h", "/"],
            capture_output=True, text=True, timeout=5
        )
        for line in r.stdout.split("\n")[1:]:
            parts = line.split()
            if len(parts) >= 5:
                stats["disk"] = {
                    "total": parts[1],
                    "used": parts[2],
                    "avail": parts[3],
                    "usage_percent": parts[4],
                }
                break

        # 运行时间
        r = subprocess.run(
            ["sh", "-c", "cat /proc/uptime | awk '{print $1}'"],
            capture_output=True, text=True, timeout=5
        )
        uptime_seconds = float(r.stdout.strip() or 0)
        stats["uptime_seconds"] = uptime_seconds

        # 系统温度
        try:
            r = subprocess.run(
                ["cat", "/sys/class/thermal/thermal_zone0/temp"],
                capture_output=True, text=True, timeout=5
            )
            temp = float(r.stdout.strip()) / 1000 if r.stdout.strip() else 0
            stats["temperature_c"] = round(temp, 1)
        except Exception:
            stats["temperature_c"] = None

    except Exception as e:
        stats["error"] = str(e)

    return stats


def _get_iface_stats() -> list:
    """获取接口状态统计"""
    ifaces = []
    try:
        r = subprocess.run(
            ["ip", "-j", "link", "show"],
            capture_output=True, text=True, timeout=5
        )
        links = json.loads(r.stdout)

        r2 = subprocess.run(
            ["ip", "-j", "addr", "show"],
            capture_output=True, text=True, timeout=5
        )
        addrs = json.loads(r2.stdout)

        addr_map = {}
        for entry in addrs:
            name = entry.get("ifname", "")
            addr_info = []
            for a in entry.get("addr_info", []):
                if a.get("family") == "inet":
                    addr_info.append(f"{a['local']}/{a['prefixlen']}")
            addr_map[name] = addr_info

        # 读取 /proc/net/dev 流量数据
        traffic_map = {}
        try:
            with open("/proc/net/dev") as f:
                for line in f.readlines()[2:]:
                    parts = line.strip().split(":")
                    if len(parts) == 2:
                        name = parts[0].strip()
                        vals = parts[1].split()
                        if len(vals) >= 9:
                            traffic_map[name] = {
                                "rx_bytes": int(vals[0]),
                                "tx_bytes": int(vals[8]),
                            }
        except Exception:
            pass

        for link in links:
            name = link.get("ifname", "")
            if name == "lo":
                continue
            entry = {
                "name": name,
                "mac": link.get("address", ""),
                "state": "UP" if link.get("operstate") == "UP" else "DOWN",
                "mtu": link.get("mtu", 1500),
                "ipv4": addr_map.get(name, []),
                "speed": _get_iface_speed(name),
            }
            if name in traffic_map:
                entry["rx_bytes"] = traffic_map[name]["rx_bytes"]
                entry["tx_bytes"] = traffic_map[name]["tx_bytes"]
            ifaces.append(entry)
    except Exception as e:
        ifaces.append({"error": str(e)})

    return ifaces


def _get_iface_speed(name: str) -> Optional[int]:
    """获取接口速率"""
    speed_file = Path(f"/sys/class/net/{name}/speed")
    if speed_file.exists():
        try:
            val = speed_file.read_text().strip()
            return int(val) if val.isdigit() else None
        except Exception:
            return None
    return None


def _get_apps_status() -> list:
    """获取应用/服务状态"""
    services = ["dnsmasq", "nftables", "ssh", "ubunturouter-init", "ubunturouter"]
    statuses = []
    for svc in services:
        try:
            r = subprocess.run(
                ["systemctl", "is-active", svc],
                capture_output=True, text=True, timeout=5
            )
            status = r.stdout.strip()
            r2 = subprocess.run(
                ["systemctl", "is-enabled", svc],
                capture_output=True, text=True, timeout=5
            )
            enabled = r2.stdout.strip()
            statuses.append({
                "name": svc,
                "active": status == "active",
                "enabled": enabled == "enabled",
                "status": status,
            })
        except Exception:
            statuses.append({"name": svc, "active": False, "enabled": False, "status": "unknown"})
    return statuses


@router.get("/status")
async def dashboard_status(auth=Depends(require_auth)):
    """获取 Dashboard 全量状态"""
    engine = ConfigEngine()

    system_stats = _get_system_stats()
    ifaces = _get_iface_stats()
    apps = _get_apps_status()

    # 配置信息
    config_info = {"initialized": engine.exists()}
    if engine.exists():
        try:
            config = engine.load()
            config_info["interfaces"] = [{
                "name": i.name,
                "role": i.role.value,
                "device": i.device,
            } for i in config.interfaces]
            config_info["dhcp"] = {
                "range": f"{config.dhcp.range_start} - {config.dhcp.range_end}"
            } if config.dhcp else None
        except Exception as e:
            config_info["error"] = str(e)

    return {
        "system": system_stats,
        "interfaces": ifaces,
        "apps": apps,
        "config": config_info,
        "version": "0.1.0",
    }
