"""接口 API: list / status / configure / port-detail / edit"""

import subprocess
import json
import re
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Literal

from ..deps import require_auth

router = APIRouter()


# ═══════════════════════════════════════════════════════════════
# 接口信息
# ═══════════════════════════════════════════════════════════════


@router.get("/list")
async def list_interfaces(auth=Depends(require_auth)):
    """列出所有网络接口（含IP/速率/类型）"""
    ifaces = []
    try:
        r = subprocess.run(["ip", "-j", "link", "show"], capture_output=True, text=True, timeout=5)
        links = json.loads(r.stdout)
        r2 = subprocess.run(["ip", "-j", "addr", "show"], capture_output=True, text=True, timeout=5)
        addrs = json.loads(r2.stdout)

        addr_map = {}
        for entry in addrs:
            name = entry.get("ifname", "")
            addrs_list = [a.get("local", "") for a in entry.get("addr_info", []) if a.get("family") == "inet"]
            addr_map[name] = addrs_list

        for link in links:
            name = link.get("ifname", "")
            if name == "lo":
                continue
            speed = _get_iface_speed(name)
            ifaces.append({
                "name": name,
                "mac": link.get("address", ""),
                "state": "UP" if link.get("operstate") == "UP" else "DOWN",
                "mtu": link.get("mtu", 1500),
                "ipv4": addr_map.get(name, []),
                "speed": speed,
                "type": "physical" if Path(f"/sys/class/net/{name}/device").exists() else "virtual",
            })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"interfaces": ifaces}


@router.get("/status/{ifname}")
async def interface_status(ifname: str, auth=Depends(require_auth)):
    """获取单个接口详细状态（含统计信息）"""
    try:
        r = subprocess.run(["ip", "-j", "link", "show", ifname], capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            raise HTTPException(status_code=404, detail=f"接口 {ifname} 不存在")
        links = json.loads(r.stdout)
        if not links:
            raise HTTPException(status_code=404, detail=f"接口 {ifname} 不存在")
        link = links[0]

        # 统计信息
        stats_dir = Path(f"/sys/class/net/{ifname}/statistics")
        stats = {}
        if stats_dir.exists():
            for name in ["rx_bytes", "rx_packets", "tx_bytes", "tx_packets", "rx_errors", "tx_errors"]:
                f = stats_dir / name
                if f.exists():
                    try:
                        stats[name] = int(f.read_text().strip())
                    except Exception:
                        pass

        # IPv4 详情
        r2 = subprocess.run(["ip", "-j", "addr", "show", ifname], capture_output=True, text=True, timeout=5)
        ipv4_info = []
        try:
            addr_data = json.loads(r2.stdout)
            for entry in addr_data:
                for a in entry.get("addr_info", []):
                    if a.get("family") == "inet":
                        ipv4_info.append({
                            "address": a.get("local"),
                            "prefixlen": a.get("prefixlen"),
                            "broadcast": a.get("broadcast"),
                        })
        except Exception:
            pass

        return {
            "name": ifname,
            "mac": link.get("address", ""),
            "state": link.get("operstate", "unknown"),
            "mtu": link.get("mtu", 1500),
            "speed": _get_iface_speed(ifname),
            "ipv4": ipv4_info,
            "statistics": stats,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/port/{ifname}")
async def port_detail(ifname: str, auth=Depends(require_auth)):
    """获取物理端口详细信息（ethtool）"""
    # 检查是否是物理设备
    dev_path = Path(f"/sys/class/net/{ifname}/device")
    if not dev_path.exists():
        raise HTTPException(status_code=400, detail=f"{ifname} 不是物理设备或无驱动信息")

    result = {
        "name": ifname,
        "driver": None,
        "firmware": None,
        "bus_info": None,
        "supported_links": [],
        "advertised_links": [],
        "duplex": None,
        "auto_negotiation": None,
        "rx_checksum": None,
        "tx_checksum": None,
        "wol": None,
    }

    try:
        # 驱动信息
        drv_path = dev_path / "driver"
        if drv_path.exists():
            result["driver"] = drv_path.resolve().name
        fw_path = dev_path / "firmware_version"
        if fw_path.exists():
            result["firmware"] = fw_path.read_text().strip()
        # bus_info 通常通过 ethtool -i
        r = subprocess.run(
            ["ethtool", "-i", ifname],
            capture_output=True, text=True, timeout=5
        )
        for line in r.stdout.split("\n"):
            if "bus-info" in line:
                result["bus_info"] = line.split(":")[-1].strip()
            if "firmware-version" in line and not result["firmware"]:
                result["firmware"] = line.split(":")[-1].strip()

        # ethtool 基本设置
        r = subprocess.run(
            ["ethtool", ifname],
            capture_output=True, text=True, timeout=5
        )
        for line in r.stdout.split("\n"):
            line = line.strip()
            if "Supported link modes" in line:
                result["supported_links"] = [x.strip() for x in line.split(":")[-1].split("/") if x.strip()]
            elif "Advertised link modes" in line:
                result["advertised_links"] = [x.strip() for x in line.split(":")[-1].split("/") if x.strip()]
            elif "Duplex" in line and ":" in line:
                result["duplex"] = line.split(":")[-1].strip()
            elif "Auto-negotiation" in line and ":" in line:
                result["auto_negotiation"] = line.split(":")[-1].strip()

        # Offload 信息
        r = subprocess.run(
            ["ethtool", "-k", ifname],
            capture_output=True, text=True, timeout=5
        )
        for line in r.stdout.split("\n"):
            line = line.strip()
            if "rx-checksumming" in line:
                result["rx_checksum"] = line.split(":")[-1].strip()
            elif "tx-checksumming" in line:
                result["tx_checksum"] = line.split(":")[-1].strip()

        # Wake-on-LAN
        r = subprocess.run(
            ["ethtool", ifname],
            capture_output=True, text=True, timeout=5
        )
        for line in r.stdout.split("\n"):
            if "Wake-on" in line and ":" in line:
                result["wol"] = line.split(":")[-1].strip()

    except FileNotFoundError:
        # ethtool 可能没装
        result["_note"] = "ethtool 未安装，部分信息不可用"
    except Exception as e:
        result["_error"] = str(e)

    return {"port": result}


# ═══════════════════════════════════════════════════════════════
# 接口配置修改（完整编辑）
# ═══════════════════════════════════════════════════════════════


class IfaceUpdateModel(BaseModel):
    """接口配置编辑请求体"""
    name: str
    protocol: Literal["dhcp", "static", "pppoe", "disabled"]
    address: Optional[str] = None        # 如 "192.168.1.1/24"
    gateway: Optional[str] = None         # 如 "192.168.1.254"
    dns: Optional[List[str]] = None       # DNS 服务器列表
    mtu: Optional[int] = Field(None, ge=576, le=9000)
    pppoe_username: Optional[str] = None
    pppoe_password: Optional[str] = None
    mac: Optional[str] = None


@router.put("/config")
async def configure_interface(cfg: IfaceUpdateModel, auth=Depends(require_auth)):
    """
    配置网络接口（运行时生效 + 持久化到 netplan）

    支持协议：
    - dhcp: 自动获取
    - static: 静态 IP（需 address + gateway）
    - pppoe: 拨号（需 username + password）
    - disabled: 关闭该接口
    """
    try:
        ifname = cfg.name

        # ── 1. 运行时生效（用 ip 命令直接操作）──

        # 清除现有 IP
        subprocess.run(["ip", "addr", "flush", "dev", ifname],
                       capture_output=True, text=True, timeout=5)

        # 清除默认路由
        subprocess.run(["ip", "route", "flush", "dev", ifname],
                       capture_output=True, text=True, timeout=5)

        # 根据协议配置
        if cfg.protocol == "dhcp":
            # 启动 DHCP 客户端（用 dhclient）
            subprocess.run(["dhclient", "-v", ifname],
                           capture_output=True, text=True, timeout=15)

        elif cfg.protocol == "static":
            if not cfg.address:
                return {"success": False, "message": "静态IP模式需要提供 address (CIDR格式)"}
            # 设置 IP
            r = subprocess.run(["ip", "addr", "add", cfg.address, "dev", ifname],
                               capture_output=True, text=True, timeout=5)
            if r.returncode != 0:
                return {"success": False, "message": f"设置IP失败: {r.stderr.strip()}"}
            # 设置网关
            if cfg.gateway:
                subprocess.run(["ip", "route", "add", "default", "via", cfg.gateway, "dev", ifname],
                               capture_output=True, text=True, timeout=5)
            # 设置 DNS（写入 resolv.conf）
            if cfg.dns:
                _write_resolv_conf(ifname, cfg.dns)

        elif cfg.protocol == "pppoe":
            # 启动 PPPoE 连接
            username = cfg.pppoe_username or ""
            password = cfg.pppoe_password or ""
            if not username or not password:
                return {"success": False, "message": "PPPoE 模式需要提供用户名和密码"}
            r = _start_pppoe(ifname, username, password)
            if not r["success"]:
                return r

        elif cfg.protocol == "disabled":
            # 禁用接口
            subprocess.run(["ip", "link", "set", ifname, "down"],
                           capture_output=True, text=True, timeout=5)

        # 设置 MTU
        if cfg.mtu:
            subprocess.run(["ip", "link", "set", "dev", ifname, "mtu", str(cfg.mtu)],
                           capture_output=True, text=True, timeout=5)

        # ── 2. 持久化到 netplan（重写 01-netcfg.yaml）──
        _write_netplan(ifname, cfg)

        return {
            "success": True,
            "message": f"接口 {ifname} 配置已更新 (协议: {cfg.protocol})"
        }

    except Exception as e:
        return {"success": False, "message": str(e)}


def _write_resolv_conf(ifname: str, dns_servers: List[str]):
    """写入临时 resolv.conf（供 dhclient 覆盖或直接使用）"""
    try:
        content = "\n".join(f"nameserver {dns}" for dns in dns_servers) + "\n"
        # NetworkManager 接管时写入 /etc/resolv.conf 会被覆盖
        # 尝试写入 /etc/resolvconf/resolv.conf.d/head (Ubuntu 传统)
        resolv_head = Path("/etc/resolvconf/resolv.conf.d/head")
        if resolv_head.parent.exists():
            resolv_head.write_text(content)
            subprocess.run(["resolvconf", "-u"], capture_output=True, timeout=5)
        else:
            # 直接写入 /etc/resolv.conf
            Path("/etc/resolv.conf").write_text(
                f"# Generated by UbuntuRouter for {ifname}\n{content}"
            )
    except Exception:
        pass  # 非关键操作


def _start_pppoe(ifname: str, username: str, password: str) -> dict:
    """启动 PPPoE 连接"""
    try:
        # 写入 PPPoE 配置
        pppoe_config = f"""
# UbuntuRouter PPPoE config for {ifname}
noauth
defaultroute
replacedefaultroute
persist
maxfail 0
holdoff 10
plugin rp-pppoe.so {ifname}
user "{username}"
password "{password}"
mtu 1492
mru 1492
"""
        config_path = Path(f"/etc/ppp/peers/ubunturouter-{ifname}")
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(pppoe_config.strip())

        # 启动 PPPoE
        r = subprocess.run(
            ["pon", f"ubunturouter-{ifname}"],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode != 0 and "already running" not in r.stderr:
            return {"success": False, "message": f"PPPoE 启动失败: {r.stderr.strip() or r.stdout.strip()}"}
        return {"success": True, "message": "PPPoE 连接已启动"}

    except Exception as e:
        return {"success": False, "message": f"PPPoE 启动异常: {e}"}


def _write_netplan(ifname: str, cfg: IfaceUpdateModel):
    """写入 netplan 配置（持久化）"""
    netplan_dir = Path("/etc/netplan")
    netplan_dir.mkdir(parents=True, exist_ok=True)

    # 读取或创建 netplan 配置
    netplan_file = netplan_dir / "01-netcfg.yaml"
    netplan_data = {"network": {"version": 2, "renderer": "networkd", "ethernets": {}}}

    if netplan_file.exists():
        try:
            import yaml
            netplan_data = yaml.safe_load(netplan_file.read_text()) or netplan_data
        except Exception:
            pass

    # 生成接口配置
    iface_config = {}
    if cfg.protocol == "dhcp":
        iface_config["dhcp4"] = True
    elif cfg.protocol == "static":
        iface_config["dhcp4"] = False
        if cfg.address:
            iface_config["addresses"] = [cfg.address]
        if cfg.gateway:
            iface_config["routes"] = [{"to": "default", "via": cfg.gateway}]
    elif cfg.protocol == "pppoe":
        # PPPoE 不走 netplan 直接管理
        iface_config["dhcp4"] = False
        # ppp 接口由 pppd 管理
    elif cfg.protocol == "disabled":
        iface_config["dhcp4"] = False

    if cfg.dns:
        iface_config["nameservers"] = {"addresses": cfg.dns}
    if cfg.mtu:
        iface_config["mtu"] = cfg.mtu
    if cfg.mac:
        iface_config["match"] = {"macaddress": cfg.mac}

    iface_config["optional"] = True

    # 确保 ethernets 存在
    if "ethernets" not in netplan_data["network"]:
        netplan_data["network"]["ethernets"] = {}
    netplan_data["network"]["ethernets"][ifname] = iface_config

    # 写入
    import yaml
    netplan_file.write_text(
        yaml.dump(netplan_data, default_flow_style=False, allow_unicode=True, indent=2, sort_keys=False)
    )

    # apply
    subprocess.run(["netplan", "apply"], capture_output=True, text=True, timeout=30)


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════


def _get_iface_speed(name: str) -> Optional[int]:
    speed_file = Path(f"/sys/class/net/{name}/speed")
    if speed_file.exists():
        try:
            val = speed_file.read_text().strip()
            return int(val) if val.isdigit() else None
        except Exception:
            return None
    return None
