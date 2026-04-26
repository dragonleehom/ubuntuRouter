"""Wireless API — 基于 netplan + systemd-networkd 的 WiFi 管理

两种模式:
1. AP (Access Point) — 用 netplan 配置热点, systemd-networkd 自动启动 hostapd
2. Client (Station) — 用 netplan 配置上级AP连接, 自动获取 IP

核心: 写 netplan YAML → netplan apply → systemd-networkd 接管
运行时操作: iw scan / iw station dump 查看状态
"""

import logging
import subprocess
import re
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import require_auth

logger = logging.getLogger(__name__)
router = APIRouter()

# ─── 常量 ──────────────────────────────────────────────────────────

NETPLAN_DIR = Path("/etc/netplan")
WIFI_CONFIG_LABEL = "99-ubunturouter-wifi"  # netplan 配置文件名 (无后缀)

# ─── 模型 ──────────────────────────────────────────────────────────


class APConfigRequest(BaseModel):
    """AP 模式配置"""
    ssid: str = Field(..., min_length=1, max_length=32)
    password: Optional[str] = Field(None, min_length=8, max_length=63)
    channel: int = Field(default=6, ge=1, le=14)
    hidden: bool = False
    max_num_sta: int = Field(default=32, ge=1, le=128)
    dhcp_range_start: Optional[str] = None   # DHCP 分配起始 IP
    dhcp_range_end: Optional[str] = None     # DHCP 分配结束 IP
    dhcp_gateway: Optional[str] = None       # 网关 (默认 AP 接口 IP)


class ClientConnectRequest(BaseModel):
    """Client 模式连接请求"""
    ssid: str = Field(..., min_length=1, max_length=32)
    password: Optional[str] = None
    hidden: bool = False

# ─── 检测助手 ──────────────────────────────────────────────────────


def _detect_wifi_interface() -> Optional[str]:
    """检测第一块可用的 WiFi 接口"""
    net_dir = Path("/sys/class/net")
    if not net_dir.exists():
        return None
    for iface in sorted(net_dir.iterdir()):
        wireless_dir = iface / "wireless"
        if wireless_dir.exists():
            return iface.name
    return None


def _get_wifi_mac(interface: str) -> str:
    mac_path = Path(f"/sys/class/net/{interface}/address")
    if mac_path.exists():
        return mac_path.read_text().strip().upper()
    return ""


def _get_interface_state(interface: str) -> str:
    state_path = Path(f"/sys/class/net/{interface}/operstate")
    if state_path.exists():
        return state_path.read_text().strip()
    return "down"


def _is_process_running(name: str) -> bool:
    try:
        r = subprocess.run(["pgrep", "-x", name], capture_output=True, text=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def _get_connected_stations(interface: str) -> list:
    """获取连接到 AP 的客户端列表 (iw station dump)"""
    stations = []
    try:
        r = subprocess.run(
            ["iw", "dev", interface, "station", "dump"],
            capture_output=True, text=True, timeout=5,
        )
        current = {}
        for line in r.stdout.split("\n"):
            line = line.strip()
            if line.startswith("Station "):
                if current.get("mac"):
                    stations.append(current)
                current = {"mac": line.split()[1].upper()}
            elif "signal:" in line:
                try:
                    current["signal_dbm"] = float(line.split()[1].replace("dBm", ""))
                except (ValueError, IndexError):
                    pass
            elif "tx bitrate:" in line:
                m = re.search(r"(\d+\.?\d*)\s*MBit/s", line)
                if m:
                    current["tx_bitrate"] = float(m.group(1))
            elif "rx bitrate:" in line:
                m = re.search(r"(\d+\.?\d*)\s*MBit/s", line)
                if m:
                    current["rx_bitrate"] = float(m.group(1))
            elif "connected time:" in line:
                try:
                    current["connected_sec"] = int(line.split(":")[1].strip().split()[0])
                except (ValueError, IndexError):
                    pass
        if current.get("mac"):
            stations.append(current)
        return stations
    except Exception:
        return []


def _get_client_info(interface: str) -> dict:
    """获取 Client 模式连接详情 (wpa_cli status)"""
    info = {"ssid": "", "ip": None, "signal_dbm": None, "bssid": ""}
    if not _is_process_running("wpa_supplicant"):
        # 可能通过 netplan → systemd-networkd 管理的, 网络已经是 DHCP 状态
        # 尝试从 ip addr 获取
        try:
            r = subprocess.run(
                ["ip", "-4", "addr", "show", interface],
                capture_output=True, text=True, timeout=5,
            )
            for line in r.stdout.split("\n"):
                if "inet " in line:
                    info["ip"] = line.strip().split()[1]
                    break
        except Exception:
            pass
        return info

    try:
        r = subprocess.run(
            ["wpa_cli", "-i", interface, "status"],
            capture_output=True, text=True, timeout=5,
        )
        for line in r.stdout.split("\n"):
            if line.startswith("ssid="):
                info["ssid"] = line.split("=", 1)[1].strip()
            elif line.startswith("ip_address="):
                ip = line.split("=", 1)[1].strip()
                info["ip"] = ip if ip else None
            elif line.startswith("bssid="):
                info["bssid"] = line.split("=", 1)[1].strip().upper()
            elif "signal" in line.lower():
                try:
                    info["signal_dbm"] = int(line.split("=")[1].strip())
                except (ValueError, IndexError):
                    pass
    except Exception:
        pass

    # 如果没有 wpa_cli 信息但有 IP, 说明是 netplan 管理的
    if not info["ip"]:
        try:
            r = subprocess.run(
                ["ip", "-4", "addr", "show", interface],
                capture_output=True, text=True, timeout=5,
            )
            for line in r.stdout.split("\n"):
                if "inet " in line:
                    info["ip"] = line.strip().split()[1]
                    break
        except Exception:
            pass

    return info


def _detect_ap_ssid(interface: str) -> str:
    """从 hostapd.conf 或 netplan 配置检测当前 AP SSID"""
    # 先读 netplan 配置
    netplan_path = NETPLAN_DIR / f"{WIFI_CONFIG_LABEL}.yaml"
    if netplan_path.exists():
        try:
            content = netplan_path.read_text()
            # 提取 ssid
            m = re.search(r'password:\s*"?(.+?)"?\n', content)
            # 更好的方式: 找 access-points 下的 key
            lines = content.split("\n")
            in_aps = False
            for line in lines:
                if "access-points" in line:
                    in_aps = True
                elif in_aps and line.strip().startswith("-"):
                    # YAML list item: "- SSID:" 或 "- SSID:"
                    m2 = re.search(r'"(.+?)"|([^":\s]+)', line.strip())
                    if m2:
                        return m2.group(1) or m2.group(2)
                elif in_aps and ":" in line and not line.strip().startswith("#"):
                    # key-value in dict
                    pass
        except Exception:
            pass
    # fallback: hostapd.conf
    hostapd_conf = Path("/etc/hostapd/hostapd.conf")
    if hostapd_conf.exists():
        try:
            for line in hostapd_conf.read_text().split("\n"):
                if line.startswith("ssid="):
                    return line.split("=", 1)[1].strip()
        except Exception:
            pass
    return ""


def _read_netplan_wifi_config() -> dict:
    """从 netplan 配置中读取 WiFi 设置"""
    result = {"mode": None, "ssid": "", "has_password": False}
    netplan_path = NETPLAN_DIR / f"{WIFI_CONFIG_LABEL}.yaml"
    if not netplan_path.exists():
        return result
    try:
        content = netplan_path.read_text()
        # 判断模式: 搜索 mode: ap
        if "mode: ap" in content:
            result["mode"] = "ap"
        elif "access-points" in content:
            result["mode"] = "client"
        # 提取 SSID
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("- ") or (stripped.startswith('"') and ":" in stripped):
                parts = stripped.split(":", 1)
                ssid_candidate = parts[0].strip().strip('"').strip("-").strip()
                if ssid_candidate and not any(k in ssid_candidate for k in ["mode", "password", "dhcp", "network"]):
                    result["ssid"] = ssid_candidate
            if "password:" in stripped:
                result["has_password"] = True
    except Exception:
        pass
    return result


# ─── Netplan 操作 ──────────────────────────────────────────────────


def _netplan_apply(timeout: int = 30) -> dict:
    """执行 netplan apply"""
    try:
        r = subprocess.run(
            ["netplan", "apply"],
            capture_output=True, text=True, timeout=timeout,
        )
        if r.returncode != 0:
            return {"success": False, "error": r.stderr[:500]}
        return {"success": True}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "netplan apply 超时"}
    except FileNotFoundError:
        return {"success": False, "error": "netplan 未安装"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _write_netplan(mode: str, interface: str, config: dict) -> dict:
    """写 netplan YAML 配置"""
    NETPLAN_DIR.mkdir(parents=True, exist_ok=True)

    # 读取已有 netplan 配置 (保留已有有线配置)
    existing_config = ""
    for f in sorted(NETPLAN_DIR.glob("*.yaml")):
        if f.name.startswith(WIFI_CONFIG_LABEL):
            continue
        try:
            existing_config += f.read_text() + "\n"
        except Exception:
            pass

    # 构建 WiFi 配置
    wifi_block = f"network:\n  version: 2\n  renderer: networkd\n"

    if mode == "ap":
        ssid = config["ssid"]
        password = config.get("password")
        channel = config.get("channel", 6)
        hidden = config.get("hidden", False)

        # netplan AP 模式: mode: ap, 需要 dhcp4 或静态IP
        # systemd-networkd 处理 AP: 启动 hostapd, 分配 DHCP
        ap_block = f"""  wifis:
    {interface}:
      access-points:
        "{ssid}":
          mode: ap
          channel: {channel}
"""
        if hidden:
            ap_block += "          hidden: true\n"
        if password:
            ap_block += f'          password: "{password}"\n'
        else:
            ap_block += "          # open network\n"

        # AP 接口通常需要静态IP + DHCP 服务
        # 这里用静态IP, DNSMASQ 或 systemd-networkd 处理 DHCP
        ap_block += f"""      dhcp4: false
      dhcp6: false
      addresses:
        - 192.168.21.1/24
      optional: true
"""
        wifi_block += ap_block

    else:  # client
        ssid = config["ssid"]
        password = config.get("password")
        hidden = config.get("hidden", False)

        client_block = f"""  wifis:
    {interface}:
      access-points:
        "{ssid}":
"""
        if password:
            client_block += f'          password: "{password}"\n'
        if hidden:
            client_block += "          hidden: true\n"
        client_block += f"""      dhcp4: true
      dhcp6: true
      optional: true
"""
        wifi_block += client_block

    # 写入文件
    netplan_path = NETPLAN_DIR / f"{WIFI_CONFIG_LABEL}.yaml"
    try:
        netplan_path.write_text(wifi_block)
    except PermissionError:
        # 需要通过 sudo
        import tempfile
        tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml")
        tmp.write(wifi_block)
        tmp.close()
        r = subprocess.run(
            ["sudo", "cp", tmp.name, str(netplan_path)],
            capture_output=True, text=True, timeout=10,
        )
        Path(tmp.name).unlink(missing_ok=True)
        if r.returncode != 0:
            return {"success": False, "error": f"写入 netplan 失败: {r.stderr}"}

    return {"success": True, "netplan_file": str(netplan_path)}


# ─── API 路由 ──────────────────────────────────────────────────────


@router.get("/status")
async def wireless_status(auth=Depends(require_auth)):
    """获取无线状态: 硬件信息, 当前模式, 连接详情"""
    iface = _detect_wifi_interface()
    if not iface:
        return {"available": False, "error": "未检测到无线网卡", "interface": None}

    mac = _get_wifi_mac(iface)
    state = _get_interface_state(iface)
    netplan_cfg = _read_netplan_wifi_config()

    # 判断实际运行模式
    hostapd_running = _is_process_running("hostapd")
    wpa_running = _is_process_running("wpa_supplicant")
    netplan_mode = netplan_cfg.get("mode")

    actual_mode = "idle"
    if hostapd_running:
        actual_mode = "ap"
    elif wpa_running or (state == "up" and netplan_mode == "client"):
        actual_mode = "client"
    elif netplan_mode:
        actual_mode = netplan_mode  # netplan 已配置但未运行

    result = {
        "available": True,
        "interface": iface,
        "mac": mac,
        "state": state,
        "mode": actual_mode,
        "netplan_mode": netplan_mode,
        "ap": {"running": hostapd_running, "ssid": "", "channel": 0, "stations": []},
        "client": {"running": wpa_running or actual_mode == "client", "ssid": "", "ip": None, "signal_dbm": None},
    }

    if hostapd_running:
        result["ap"]["ssid"] = _detect_ap_ssid(iface) or netplan_cfg.get("ssid", "")
        result["ap"]["stations"] = _get_connected_stations(iface)
    elif netplan_mode == "ap":
        result["ap"]["ssid"] = netplan_cfg.get("ssid", "")

    if wpa_running or actual_mode == "client":
        client_info = _get_client_info(iface)
        result["client"].update(client_info)
        if not result["client"]["ssid"]:
            result["client"]["ssid"] = netplan_cfg.get("ssid", "")

    return result


@router.get("/interfaces")
async def wireless_interfaces(auth=Depends(require_auth)):
    """列出无线接口信息"""
    iface = _detect_wifi_interface()
    if not iface:
        return {"available": False, "interfaces": []}

    info = {
        "name": iface,
        "mac": _get_wifi_mac(iface),
        "state": _get_interface_state(iface),
    }

    try:
        r = subprocess.run(["iw", "dev", iface, "info"], capture_output=True, text=True, timeout=5)
        for line in r.stdout.split("\n"):
            if "type " in line:
                info["mode"] = line.split()[-1]
    except Exception:
        pass

    return {"available": True, "count": 1, "interfaces": [info]}


@router.get("/scan")
async def scan_networks(interface: Optional[str] = None, auth=Depends(require_auth)):
    """扫描附近的 WiFi 网络"""
    iface = interface or _detect_wifi_interface()
    if not iface:
        return {"success": False, "networks": [], "error": "无可用无线接口"}

    # 确保接口 up
    subprocess.run(["ip", "link", "set", iface, "up"], capture_output=True, timeout=5)
    time.sleep(0.5)

    try:
        r = subprocess.run(
            ["iw", "dev", iface, "scan", "-u"],
            capture_output=True, text=True, timeout=20,
        )
        if r.returncode != 0:
            return {"success": False, "networks": [], "error": r.stderr[:200]}
    except FileNotFoundError:
        return {"success": False, "networks": [], "error": "iw 未安装"}
    except subprocess.TimeoutExpired:
        return {"success": False, "networks": [], "error": "扫描超时"}

    networks = []
    current = {}
    for raw_line in r.stdout.split("\n"):
        line = raw_line.strip()
        if line.startswith("BSS "):
            if current.get("ssid"):
                networks.append(dict(current))
            current = {"bssid": line.split()[1].upper()}
        elif line.startswith("SSID:") and "list" not in line:
            ssid = line.split(":", 1)[1].strip().strip('"')
            if ssid:
                current["ssid"] = ssid
        elif line.startswith("freq:"):
            try:
                current["frequency"] = int(line.split()[1])
            except (ValueError, IndexError):
                pass
        elif line.startswith("signal:"):
            for p in line.split():
                if "dBm" in p:
                    try:
                        current["signal_dbm"] = float(p.replace("dBm", ""))
                    except ValueError:
                        pass
                    break
        elif "RSN:" in line or "WPA:" in line:
            current["encrypted"] = True
        elif "WEP:" in line:
            current["wep"] = True

    if current.get("ssid"):
        networks.append(dict(current))

    # 去重 (保留信号最强)
    seen = {}
    for net in networks:
        ssid = net["ssid"]
        if ssid not in seen or net.get("signal_dbm", -100) > seen[ssid].get("signal_dbm", -100):
            seen[ssid] = net

    result = []
    for ssid, net in seen.items():
        enc = "open"
        if net.get("encrypted"):
            enc = "wpa2"
        elif net.get("wep"):
            enc = "wep"
        result.append({
            "ssid": ssid,
            "bssid": net.get("bssid", ""),
            "frequency": net.get("frequency", 0),
            "band": "5GHz" if net.get("frequency", 0) > 4000 else "2.4GHz",
            "signal_dbm": net.get("signal_dbm", -100),
            "encryption": enc,
        })

    result.sort(key=lambda x: x["signal_dbm"], reverse=True)
    return {"success": True, "count": len(result), "networks": result}


@router.post("/ap/start")
async def start_ap(body: APConfigRequest, auth=Depends(require_auth)):
    """启动 AP 模式 — 通过 netplan 配置, systemd-networkd 自动启动 hostapd"""
    iface = _detect_wifi_interface()
    if not iface:
        raise HTTPException(status_code=400, detail="无可用无线接口")

    # 先清除 client 配置 (如果有)
    if _is_process_running("wpa_supplicant"):
        subprocess.run(["wpa_cli", "-i", iface, "terminate"], capture_output=True, timeout=5)

    # 写入 netplan
    result = _write_netplan("ap", iface, body.model_dump())
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "配置写入失败"))

    # netplan apply
    apply = _netplan_apply()
    if not apply["success"]:
        raise HTTPException(status_code=500, detail=apply.get("error", "netplan apply 失败"))

    time.sleep(2)

    # 确认 hostapd 已启动
    if not _is_process_running("hostapd"):
        # 等待一下, systemd-networkd 可能还在处理
        time.sleep(3)

    return {
        "success": True,
        "message": f"AP '{body.ssid}' 已启动 (channel {body.channel})",
        "interface": iface,
        "ssid": body.ssid,
    }


@router.post("/ap/stop")
async def stop_ap(auth=Depends(require_auth)):
    """停止 AP 模式 — 删除 netplan WiFi 配置后 apply"""
    iface = _detect_wifi_interface()
    if not iface:
        raise HTTPException(status_code=400, detail="无可用无线接口")

    # 删除 netplan WiFi 配置文件
    netplan_path = NETPLAN_DIR / f"{WIFI_CONFIG_LABEL}.yaml"
    if netplan_path.exists():
        try:
            netplan_path.unlink()
        except PermissionError:
            subprocess.run(["sudo", "rm", "-f", str(netplan_path)], capture_output=True, timeout=5)

    # netplan apply 恢复
    _netplan_apply()
    time.sleep(1)

    return {"success": True, "message": "AP 已停止"}


@router.post("/client/connect")
async def client_connect(body: ClientConnectRequest, auth=Depends(require_auth)):
    """连接上级 AP — 通过 netplan 配置 Client 模式"""
    iface = _detect_wifi_interface()
    if not iface:
        raise HTTPException(status_code=400, detail="无可用无线接口")

    # 写入 netplan
    result = _write_netplan("client", iface, body.model_dump())
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "配置写入失败"))

    # netplan apply
    apply = _netplan_apply(timeout=60)
    if not apply["success"]:
        raise HTTPException(status_code=500, detail=apply.get("error", "netplan apply 失败"))

    # 等待 DHCP
    time.sleep(3)
    ip = None
    try:
        r = subprocess.run(
            ["ip", "-4", "addr", "show", iface],
            capture_output=True, text=True, timeout=5,
        )
        for line in r.stdout.split("\n"):
            if "inet " in line:
                ip = line.strip().split()[1]
                break
    except Exception:
        pass

    return {
        "success": True,
        "message": f"已连接到 {body.ssid}" if not ip else f"已连接到 {body.ssid}, IP: {ip}",
        "interface": iface,
        "ip": ip,
        "ssid": body.ssid,
    }


@router.post("/client/disconnect")
async def client_disconnect(auth=Depends(require_auth)):
    """断开 Client 连接 — 删除 netplan WiFi 配置后 apply"""
    iface = _detect_wifi_interface()
    if not iface:
        return {"success": True, "message": "无无线接口"}

    netplan_path = NETPLAN_DIR / f"{WIFI_CONFIG_LABEL}.yaml"
    if netplan_path.exists():
        try:
            netplan_path.unlink()
        except PermissionError:
            subprocess.run(["sudo", "rm", "-f", str(netplan_path)], capture_output=True, timeout=5)

    _netplan_apply()

    # 清理 wpa_supplicant
    subprocess.run(["wpa_cli", "-i", iface, "terminate"], capture_output=True, timeout=5)
    subprocess.run(["dhclient", "-r", iface], capture_output=True, timeout=5)
    subprocess.run(["ip", "link", "set", iface, "down"], capture_output=True, timeout=5)
    subprocess.run(["ip", "addr", "flush", "dev", iface], capture_output=True, timeout=5)

    return {"success": True, "message": "Client 已断开"}


@router.post("/reset")
async def wireless_reset(auth=Depends(require_auth)):
    """重置无线 — 删除配置 + 停所有进程"""
    iface = _detect_wifi_interface()
    if not iface:
        return {"success": True, "message": "无无线接口"}

    netplan_path = NETPLAN_DIR / f"{WIFI_CONFIG_LABEL}.yaml"
    if netplan_path.exists():
        try:
            netplan_path.unlink()
        except PermissionError:
            subprocess.run(["sudo", "rm", "-f", str(netplan_path)], capture_output=True, timeout=5)

    _netplan_apply()

    subprocess.run(["pkill", "-9", "hostapd"], capture_output=True, timeout=5)
    subprocess.run(["wpa_cli", "-i", iface, "terminate"], capture_output=True, timeout=5)
    subprocess.run(["dhclient", "-r", iface], capture_output=True, timeout=5)
    subprocess.run(["ip", "link", "set", iface, "down"], capture_output=True, timeout=5)
    subprocess.run(["ip", "addr", "flush", "dev", iface], capture_output=True, timeout=5)

    return {"success": True, "message": "无线已重置"}
