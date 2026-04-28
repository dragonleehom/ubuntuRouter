"""FTP / LED / SNMP 管理路由 — Sprint 7 (P3补齐)

vsftpd, 系统指示灯, snmpd 配置管理
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import subprocess
from pathlib import Path
from ..deps import require_auth

router = APIRouter()


# ─── FTP (vsftpd) ─────────────────────────────────────────

VSFTPD_CONF = Path("/etc/vsftpd.conf")


def _read_vsftpd_conf() -> dict:
    config = {"enabled": False, "local_enable": "NO", "write_enable": "NO",
              "anonymous_enable": "NO", "local_umask": "022", "port": 21,
              "pasv_min_port": 30000, "pasv_max_port": 31000}
    if not VSFTPD_CONF.exists():
        return config
    for line in VSFTPD_CONF.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            config[k.strip()] = v.strip()
    # 检查服务状态
    r = subprocess.run(["systemctl", "is-active", "vsftpd"],
                       capture_output=True, text=True, timeout=5)
    config["enabled"] = r.stdout.strip() == "active"
    return config


def _write_vsftpd_conf(config: dict):
    VSFTPD_CONF.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "listen=YES",
        "listen_port=21",
        "anonymous_enable=NO",
        "local_enable=YES",
        "write_enable=YES",
        "local_umask=022",
        "dirmessage_enable=YES",
        "xferlog_enable=YES",
        "connect_from_port_20=YES",
        "seccomp_sandbox=NO",
        "pasv_enable=YES",
        "pasv_min_port=30000",
        "pasv_max_port=31000",
        "chroot_local_user=YES",
        "allow_writeable_chroot=YES",
    ]
    VSFTPD_CONF.write_text("\n".join(lines) + "\n")


@router.get("/ftp/status")
async def ftp_status(auth=Depends(require_auth)):
    """获取 FTP 服务状态"""
    config = _read_vsftpd_conf()
    return {
        "enabled": config.get("enabled", False),
        "port": config.get("listen_port", 21),
        "mode": "主动+被动",
        "local_enable": config.get("local_enable", "YES"),
        "anonymous_enable": config.get("anonymous_enable", "NO"),
    }


@router.post("/ftp/enable")
async def ftp_enable(auth=Depends(require_auth)):
    """启用 FTP 服务"""
    _write_vsftpd_conf({})
    subprocess.run(["systemctl", "enable", "vsftpd"],
                   capture_output=True, text=True, timeout=10)
    r = subprocess.run(["systemctl", "start", "vsftpd"],
                       capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        raise HTTPException(status_code=500, detail=r.stderr.strip() or "启动失败")
    return {"success": True, "message": "FTP 服务已启用"}


@router.post("/ftp/disable")
async def ftp_disable(auth=Depends(require_auth)):
    """禁用 FTP 服务"""
    subprocess.run(["systemctl", "stop", "vsftpd"],
                   capture_output=True, text=True, timeout=10)
    subprocess.run(["systemctl", "disable", "vsftpd"],
                   capture_output=True, text=True, timeout=10)
    return {"success": True, "message": "FTP 服务已禁用"}


# ─── LED ──────────────────────────────────────────────────

LED_PATHS = [
    Path("/sys/class/leds"),
]


def _list_leds() -> list:
    leds = []
    for base in LED_PATHS:
        if not base.exists():
            continue
        for led in base.iterdir():
            try:
                brightness = int((led / "brightness").read_text().strip())
                max_brightness = int((led / "max_brightness").read_text().strip()) if (led / "max_brightness").exists() else 1
                trigger = (led / "trigger").read_text().strip() if (led / "trigger").exists() else ""
            except (OSError, ValueError):
                brightness = 0; max_brightness = 1; trigger = ""
            leds.append({
                "name": led.name,
                "brightness": brightness,
                "max_brightness": max_brightness,
                "enabled": brightness > 0,
                "trigger": trigger,
            })
    return leds


@router.get("/led")
async def list_leds(auth=Depends(require_auth)):
    """列出系统 LED"""
    leds = _list_leds()
    return {"leds": leds, "count": len(leds)}


@router.post("/led/{name}/on")
async def led_on(name: str, auth=Depends(require_auth)):
    """点亮 LED"""
    for base in LED_PATHS:
        led_path = base / name / "brightness"
        if led_path.exists():
            try:
                max_val = int((base / name / "max_brightness").read_text().strip())
            except (OSError, ValueError):
                max_val = 1
            led_path.write_text(str(max_val))
            return {"success": True, "message": f"LED {name} 已点亮"}
    raise HTTPException(status_code=404, detail=f"LED {name} 未找到")


@router.post("/led/{name}/off")
async def led_off(name: str, auth=Depends(require_auth)):
    """熄灭 LED"""
    for base in LED_PATHS:
        led_path = base / name / "brightness"
        if led_path.exists():
            led_path.write_text("0")
            return {"success": True, "message": f"LED {name} 已熄灭"}
    raise HTTPException(status_code=404, detail=f"LED {name} 未找到")


@router.post("/led/{name}/trigger")
async def led_set_trigger(name: str, data: dict, auth=Depends(require_auth)):
    """设置 LED 触发模式"""
    trigger = data.get("trigger", "none")
    for base in LED_PATHS:
        trigger_path = base / name / "trigger"
        if trigger_path.exists():
            trigger_path.write_text(trigger)
            return {"success": True, "message": f"LED {name} 触发模式已设为 {trigger}"}
    raise HTTPException(status_code=404, detail=f"LED {name} 未找到")


# ─── SNMP ─────────────────────────────────────────────────

SNMPD_CONF = Path("/etc/snmp/snmpd.conf")


def _read_snmpd_conf() -> dict:
    config = {"enabled": False, "community": "public", "location": "",
              "contact": "", "port": 161, "allowed_networks": ["127.0.0.1"]}
    if SNMPD_CONF.exists():
        for line in SNMPD_CONF.read_text().splitlines():
            line = line.strip()
            if line.startswith("rocommunity"):
                parts = line.split()
                if len(parts) >= 2:
                    config["community"] = parts[1]
                if len(parts) >= 3:
                    config["allowed_networks"] = [parts[2]]
            elif line.startswith("sysLocation"):
                config["location"] = line.split(None, 1)[1].strip('"') if " " in line else ""
            elif line.startswith("sysContact"):
                config["contact"] = line.split(None, 1)[1].strip('"') if " " in line else ""
    r = subprocess.run(["systemctl", "is-active", "snmpd"],
                       capture_output=True, text=True, timeout=5)
    config["enabled"] = r.stdout.strip() == "active"
    config["port"] = 161
    return config


@router.get("/snmp/status")
async def snmp_status(auth=Depends(require_auth)):
    """获取 SNMP 状态"""
    return _read_snmpd_conf()


@router.post("/snmp/config")
async def snmp_config(data: dict, auth=Depends(require_auth)):
    """配置 SNMP"""
    community = data.get("community", "public")
    location = data.get("location", "")
    contact = data.get("contact", "")
    allowed = data.get("allowed_networks", ["127.0.0.1"])
    SNMPD_CONF.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"rocommunity {community} {' '.join(allowed)}",
        f"sysLocation \"{location}\"" if location else "",
        f"sysContact \"{contact}\"" if contact else "",
        "sysServices 79",
        "proc mountd",
        "proc nfsd",
        "disk / 10%",
        "load 12 10 5",
    ]
    SNMPD_CONF.write_text("\n".join([l for l in lines if l]) + "\n")
    subprocess.run(["systemctl", "restart", "snmpd"],
                   capture_output=True, text=True, timeout=10)
    return {"success": True, "message": "SNMP 配置已更新"}


@router.post("/snmp/enable")
async def snmp_enable(auth=Depends(require_auth)):
    """启用 SNMP"""
    subprocess.run(["systemctl", "enable", "snmpd"],
                   capture_output=True, text=True, timeout=10)
    r = subprocess.run(["systemctl", "start", "snmpd"],
                       capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        raise HTTPException(status_code=500, detail=r.stderr.strip() or "启动失败")
    return {"success": True, "message": "SNMP 已启用"}


@router.post("/snmp/disable")
async def snmp_disable(auth=Depends(require_auth)):
    """禁用 SNMP"""
    subprocess.run(["systemctl", "stop", "snmpd"],
                   capture_output=True, text=True, timeout=10)
    subprocess.run(["systemctl", "disable", "snmpd"],
                   capture_output=True, text=True, timeout=10)
    return {"success": True, "message": "SNMP 已禁用"}
