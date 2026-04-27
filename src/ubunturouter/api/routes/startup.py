"""启动项管理 API: systemctl enable/disable + 开机自启服务管理"""

import subprocess
from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException

from ..deps import require_auth


router = APIRouter()


def _list_services(enabled_only: bool = False) -> List[Dict]:
    """列出系统服务"""
    args = ["systemctl", "list-unit-files", "--type=service", "--no-pager"]
    if enabled_only:
        args.append("--state=enabled")

    r = subprocess.run(args, capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        raise HTTPException(500, f"获取服务列表失败: {r.stderr.strip()}")

    services = []
    in_table = False
    for line in r.stdout.split("\n"):
        stripped = line.strip()
        if stripped.startswith("UNIT FILE") and "STATE" in stripped:
            in_table = True
            continue
        if in_table and stripped and not stripped.startswith("─"):
            parts = stripped.split()
            if len(parts) >= 2:
                name = parts[0]
                state = parts[1]
                services.append({
                    "name": name,
                    "state": state,
                    "enabled": state == "enabled",
                    "is_user": "user" in name.lower() or "session" in name.lower(),
                })

    return services


def _is_active(name: str) -> bool:
    r = subprocess.run(
        ["systemctl", "is-active", name],
        capture_output=True, text=True, timeout=5,
    )
    return r.stdout.strip() == "active"


def _get_enabled_services() -> List[str]:
    """获取已启用自启的服务名列表"""
    r = subprocess.run(
        ["systemctl", "list-unit-files", "--type=service", "--state=enabled", "--no-pager"],
        capture_output=True, text=True, timeout=10,
    )
    services = []
    in_table = False
    for line in r.stdout.split("\n"):
        stripped = line.strip()
        if stripped.startswith("UNIT FILE"):
            in_table = True
            continue
        if in_table and stripped and not stripped.startswith("─"):
            parts = stripped.split()
            if parts:
                services.append(parts[0])
    return services


def _filter_relevant(services: List[Dict]) -> List[Dict]:
    """过滤出与路由器相关的关键服务"""
    keywords = [
        "dnsmasq", "nftables", "ssh", "cron", "networkd", "netplan",
        "docker", "ufw", "systemd-resolved", "systemd-timesyncd",
        "nginx", "apache", "samba", "smbd", "nmbd", "frp", "frps",
        "tailscale", "wireguard", "openvpn", "strongswan",
        "miniupnpd", "upnp", "nfs", "rpcbind", "vsftpd",
        "ubunturouter", "ttyd",
    ]
    relevant = []
    for svc in services:
        name = svc["name"]
        for kw in keywords:
            if kw in name.lower():
                svc["keyword"] = kw
                relevant.append(svc)
                break
    return relevant


# ─── API ─────────────────────────────────────────────────────────────


@router.get("/startup")
async def list_startup_items(auth=Depends(require_auth)):
    """列出所有启动项（相关服务）"""
    all_services = _list_services()
    relevant = _filter_relevant(all_services)

    items = []
    for svc in relevant:
        active = _is_active(svc["name"])
        items.append({
            "name": svc["name"],
            "active": active,
            "enabled": svc["enabled"],
            "state": svc["state"],
            "category": _categorize(svc["name"]),
            "description": _describe(svc["name"]),
        })

    # 按分类排序
    items.sort(key=lambda x: (x["category"], x["name"]))

    return {
        "items": items,
        "categories": ["网络", "系统", "安全", "应用", "存储", "远程"],
    }


@router.put("/startup/{service_name}")
async def toggle_startup(service_name: str, enabled: bool = True, auth=Depends(require_auth)):
    """启用/禁用服务的开机自启"""
    action = "enable" if enabled else "disable"
    r = subprocess.run(
        ["systemctl", action, service_name],
        capture_output=True, text=True, timeout=15,
    )
    if r.returncode != 0:
        raise HTTPException(
            500, f"{action} {service_name} 失败: {r.stderr.strip()}"
        )
    return {
        "message": f"{service_name} 已{'启用' if enabled else '禁用'}开机自启",
        "name": service_name,
        "enabled": enabled,
    }


@router.get("/startup/all")
async def list_all_services(auth=Depends(require_auth)):
    """列出所有系统服务（供搜索）"""
    services = _list_services()
    result = []
    for svc in services:
        active = _is_active(svc["name"])
        result.append({
            "name": svc["name"],
            "active": active,
            "enabled": svc["enabled"],
            "state": svc["state"],
        })
    return {"services": result}


@router.get("/startup/status")
async def startup_service_status(name: str, auth=Depends(require_auth)):
    """查询单个服务状态"""
    active = _is_active(name)
    r = subprocess.run(
        ["systemctl", "is-enabled", name],
        capture_output=True, text=True, timeout=5,
    )
    enabled = r.stdout.strip()
    return {"name": name, "active": active, "enabled": enabled}


@router.post("/service/control")
async def control_service(req: dict, auth=Depends(require_auth)):
    """启动/停止/重启服务"""
    name = req.get("name", "")
    action = req.get("action", "restart")
    if not name:
        raise HTTPException(400, "服务名不能为空")
    if action not in ("start", "stop", "restart"):
        raise HTTPException(400, "操作必须是 start/stop/restart")
    r = subprocess.run(
        ["systemctl", action, name],
        capture_output=True, text=True, timeout=15,
    )
    if r.returncode != 0:
        raise HTTPException(500, f"{action} {name} 失败: {r.stderr.strip()}")
    return {"message": f"{name} 已{action}", "name": name, "action": action}


# ─── 辅助函数 ────────────────────────────────────────────────────────


def _categorize(name: str) -> str:
    """按服务类型分类"""
    n = name.lower()
    if any(kw in n for kw in ["dnsmasq", "networkd", "netplan", "nftables",
                               "ufw", "frp", "frps", "tailscale", "wireguard",
                               "openvpn", "strongswan", "miniupnpd", "upnp",
                               "ttyd"]):
        return "网络"
    if any(kw in n for kw in ["ssh", "cron", "systemd-resolved",
                               "systemd-timesyncd", "ubunturouter"]):
        return "系统"
    if any(kw in n for kw in ["docker", "nginx", "apache"]):
        return "应用"
    if any(kw in n for kw in ["samba", "smbd", "nmbd", "nfs",
                               "rpcbind", "vsftpd"]):
        return "存储"
    return "其他"


def _describe(name: str) -> str:
    """生成简短描述"""
    descriptions = {
        "dnsmasq": "DHCP/DNS 服务",
        "nftables": "防火墙服务",
        "ssh": "SSH 远程登录",
        "ssh.service": "SSH 远程登录",
        "cron": "定时任务服务",
        "cron.service": "定时任务服务",
        "systemd-networkd": "网络管理服务",
        "systemd-networkd.service": "网络管理服务",
        "systemd-resolved": "DNS 解析服务",
        "systemd-resolved.service": "DNS 解析服务",
        "systemd-timesyncd": "时间同步服务",
        "systemd-timesyncd.service": "时间同步服务",
        "docker": "容器引擎",
        "docker.service": "容器引擎",
        "nginx": "Web 服务器",
        "nginx.service": "Web 服务器",
        "samba": "Samba 文件共享",
        "samba-ad-dc": "Samba 域控制器",
        "smbd": "SMB 文件共享服务",
        "smbd.service": "SMB 文件共享服务",
        "nmbd": "NetBIOS 名称服务",
        "nmbd.service": "NetBIOS 名称服务",
        "nfs": "NFS 文件共享",
        "nfs-server": "NFS 文件共享",
        "nfs-server.service": "NFS 文件共享",
        "tailscale": "Tailscale VPN",
        "tailscaled": "Tailscale VPN 守护进程",
        "wireguard": "WireGuard VPN",
        "wireguard.service": "WireGuard VPN",
        "openvpn": "OpenVPN 服务",
        "openvpn.service": "OpenVPN 服务",
        "frpc": "FRP 客户端",
        "frps": "FRP 服务端",
        "miniupnpd": "UPnP 端口转发",
        "miniupnpd.service": "UPnP 端口转发",
        "ufw": "UFW 防火墙",
        "ufw.service": "UFW 防火墙",
        "ttyd": "Web 终端",
        "ttyd.service": "Web 终端",
        "netplan": "网络配置管理",
        "netplan.service": "网络配置管理",
        "ubunturouter": "UbuntuRouter 主服务",
        "ubunturouter.service": "UbuntuRouter 主服务",
    }
    return descriptions.get(name, "系统服务")
