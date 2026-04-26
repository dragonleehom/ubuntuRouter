"""Wireless API — WiFi AP mode (热点) + Client mode (中继/客户端)

两种工作模式 (由 device/wlx* 接口实现):
1. AP (Access Point) — 用 hostapd 提供 WiFi 覆盖, 接口桥接到 LAN
2. Client (Station/Managed) — 用 wpa_supplicant 连接上级 AP, 接口作为 WAN

一个物理 WiFi 网卡只能工作于一种模式, 切换模式需要关闭当前模式。
"""

import logging
import subprocess
import re
import os
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import require_auth

logger = logging.getLogger(__name__)
router = APIRouter()

# ─── 常量 ──────────────────────────────────────────────────────────

WIFI_CONFIG_DIR = Path("/etc/ubunturouter/wireless")
HOSTAPD_CONF = WIFI_CONFIG_DIR / "hostapd.conf"
WPA_SUPPLICANT_CONF = WIFI_CONFIG_DIR / "wpa_supplicant.conf"
WIFI_STATE = WIFI_CONFIG_DIR / "mode.state"  # 记录当前模式

# ─── 模型 ──────────────────────────────────────────────────────────


class APConfigRequest(BaseModel):
    """AP 模式配置"""
    ssid: str = Field(..., min_length=1, max_length=32)
    password: Optional[str] = Field(None, min_length=8, max_length=63)
    channel: int = Field(default=6, ge=1, le=165)
    hw_mode: str = Field(default="g", pattern="^(a|b|g)$")
    hidden: bool = False
    max_num_sta: int = Field(default=32, ge=1, le=128)


class ClientConnectRequest(BaseModel):
    """Client 模式连接请求"""
    ssid: str = Field(..., min_length=1, max_length=32)
    password: Optional[str] = None
    hidden: bool = False


class ModeSwitchRequest(BaseModel):
    """模式切换"""
    mode: str = Field(..., pattern="^(ap|client)$")


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


def _get_wifi_phy(interface: str) -> Optional[str]:
    """获取接口对应的 phy 名称"""
    try:
        r = subprocess.run(["iw", "dev"], capture_output=True, text=True, timeout=5)
        current_iface = None
        for line in r.stdout.split("\n"):
            line = line.strip()
            if line.startswith("Interface "):
                current_iface = line.split()[1]
            elif line.startswith("wiphy ") and current_iface == interface:
                return f"phy{line.split()[1]}"
        return None
    except FileNotFoundError:
        return None


def _read_mode_state() -> dict:
    """读取当前无线模式状态"""
    state = {"mode": None, "ap": {"running": False, "ssid": ""}, "client": {"running": False, "ssid": ""}}
    if WIFI_STATE.exists():
        try:
            with open(WIFI_STATE) as f:
                for line in f:
                    line = line.strip()
                    if "=" in line:
                        k, v = line.split("=", 1)
                        if k == "mode":
                            state["mode"] = v
                        elif k == "ap_ssid":
                            state["ap"]["ssid"] = v
                        elif k == "client_ssid":
                            state["client"]["ssid"] = v
        except Exception:
            pass
    return state


def _write_mode_state(state: dict):
    """写入模式状态"""
    WIFI_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append(f"mode={state.get('mode', '')}")
    if state.get("ap"):
        lines.append(f"ap_ssid={state['ap'].get('ssid', '')}")
    if state.get("client"):
        lines.append(f"client_ssid={state['client'].get('ssid', '')}")
    try:
        WIFI_STATE.write_text("\n".join(lines) + "\n")
    except Exception as e:
        logger.error("Failed to write WiFi state: %s", e)


def _is_process_running(process_name: str) -> bool:
    """检查进程是否在运行"""
    try:
        r = subprocess.run(
            ["pgrep", "-x", process_name],
            capture_output=True, text=True, timeout=5,
        )
        return r.returncode == 0
    except Exception:
        return False


def _get_wifi_ip(interface: str) -> Optional[str]:
    """获取 WiFi 接口的 IP 地址"""
    try:
        r = subprocess.run(
            ["ip", "-4", "addr", "show", interface],
            capture_output=True, text=True, timeout=5,
        )
        for line in r.stdout.split("\n"):
            if "inet " in line:
                return line.strip().split()[1]
    except Exception:
        pass
    return None


def _get_connected_stations(interface: str) -> list:
    """获取连接到 AP 的客户端列表 (AP 模式下)"""
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


# ─── AP 模式 ───────────────────────────────────────────────────────


def _start_ap(interface: str, config: dict) -> dict:
    """启动 AP 模式: 写 hostapd.conf → 启动 hostapd → 分配 IP + DHCP"""
    WIFI_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    ssid = config["ssid"]
    password = config.get("password")
    channel = config.get("channel", 6)
    hw_mode = config.get("hw_mode", "g")
    hidden = config.get("hidden", False)
    max_sta = config.get("max_num_sta", 32)

    # 构建 hostapd.conf
    conf_lines = [
        f"interface={interface}",
        f"driver=nl80211",
        f"ssid={ssid}",
        f"hw_mode={hw_mode}",
        f"channel={channel}",
        f"max_num_sta={max_sta}",
        f"ignore_broadcast_ssid={'2' if hidden else '0'}",
        "wmm_enabled=1",
        "macaddr_acl=0",
        "auth_algs=1",
    ]

    if password:
        conf_lines += [
            "wpa=2",
            "wpa_key_mgmt=WPA-PSK",
            "rsn_pairwise=CCMP",
            f"wpa_passphrase={password}",
        ]
    else:
        conf_lines.append("wpa=0")  # 开放网络

    try:
        HOSTAPD_CONF.write_text("\n".join(conf_lines) + "\n")
    except Exception as e:
        return {"success": False, "error": f"无法写入 hostapd.conf: {e}"}

    # 先终止已有 hostapd
    subprocess.run(["pkill", "-x", "hostapd"], capture_output=True, timeout=5)

    # 给接口分配静态 IP (192.168.21.x 与当前 LAN 网段一致，方便桥接)
    # 实际上这个 IP 用于 WiFi 客户端所在的子网，这里统一用 LAN 网段
    try:
        subprocess.run(
            ["ip", "addr", "add", "192.168.21.1/24", "dev", interface],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        pass  # 可能已经存在

    try:
        subprocess.run(["ip", "link", "set", interface, "up"], capture_output=True, timeout=5)
    except Exception as e:
        return {"success": False, "error": f"无法启动接口: {e}"}

    # 启动 hostapd (后台)
    proc = subprocess.Popen(
        ["hostapd", "-B", str(HOSTAPD_CONF)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    time.sleep(1)

    if not _is_process_running("hostapd"):
        return {"success": False, "error": "hostapd 启动失败, 检查日志: journalctl -u hostapd"}

    # 记录状态
    _write_mode_state({
        "mode": "ap",
        "ap": {"ssid": ssid, "channel": channel, "password": bool(password), "hidden": hidden},
        "client": {},
    })

    return {"success": True, "message": f"AP '{ssid}' on {interface} (channel {channel})", "interface": interface}


def _stop_ap(interface: str) -> dict:
    """停止 AP 模式"""
    subprocess.run(["pkill", "-x", "hostapd"], capture_output=True, timeout=5)
    try:
        subprocess.run(["ip", "link", "set", interface, "down"], capture_output=True, timeout=5)
    except Exception:
        pass
    # 清除 IP
    try:
        subprocess.run(
            ["ip", "addr", "flush", "dev", interface],
            capture_output=True, timeout=5,
        )
    except Exception:
        pass
    _write_mode_state({"mode": None, "ap": {}, "client": {}})
    return {"success": True, "message": "AP 已停止"}


# ─── Client 模式 ───────────────────────────────────────────────────


def _start_client(interface: str, config: dict) -> dict:
    """启动 Client 模式: 写 wpa_supplicant.conf → 连接 AP → DHCP 获取 IP"""
    WIFI_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    ssid = config["ssid"]
    password = config.get("password")
    hidden = config.get("hidden", False)

    # 构建 wpa_supplicant.conf
    conf_lines = [
        "ctrl_interface=/var/run/wpa_supplicant",
        "update_config=1",
        "country=CN",
    ]

    if password:
        # 用 wpa_passphrase 生成
        try:
            r = subprocess.run(
                ["wpa_passphrase", ssid, password],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                # 提取 network 块
                network_block = ""
                in_block = False
                for line in r.stdout.split("\n"):
                    if line.strip() == "network={":
                        in_block = True
                        network_block = "network={\n"
                    elif in_block:
                        network_block += line + "\n"
                        if line.strip() == "}":
                            break
            else:
                return {"success": False, "error": "wpa_passphrase 失败"}
        except FileNotFoundError:
            return {"success": False, "error": "wpa_passphrase 未安装"}
    else:
        network_block = f'network={{\n\tssid="{ssid}"\n\tkey_mgmt=NONE\n}}\n'

    if hidden:
        # 在网络块中添加 scan_ssid=1
        network_block = network_block.replace(
            "\tssid=", "\tscan_ssid=1\n\tssid="
        )

    conf_lines.append(network_block)

    try:
        WPA_SUPPLICANT_CONF.write_text("\n".join(conf_lines) + "\n")
    except Exception as e:
        return {"success": False, "error": f"无法写入 wpa_supplicant.conf: {e}"}

    # 终止已有 wpa_supplicant
    try:
        subprocess.run(
            ["wpa_cli", "-i", interface, "terminate"],
            capture_output=True, timeout=5,
        )
    except Exception:
        pass

    time.sleep(0.5)

    # 启动 wpa_supplicant
    try:
        r = subprocess.run(
            ["wpa_supplicant", "-B", "-i", interface, "-c", str(WPA_SUPPLICANT_CONF)],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            return {"success": False, "error": f"wpa_supplicant 启动失败: {r.stderr}"}
    except FileNotFoundError:
        return {"success": False, "error": "wpa_supplicant 未安装"}

    # 等待连接 (最多 15 秒)
    connected = False
    for _ in range(15):
        time.sleep(1)
        try:
            r = subprocess.run(
                ["wpa_cli", "-i", interface, "status"],
                capture_output=True, text=True, timeout=5,
            )
            for line in r.stdout.split("\n"):
                if line.startswith("wpa_state="):
                    if "COMPLETED" in line:
                        connected = True
                    break
        except Exception:
            pass
        if connected:
            break

    if not connected:
        return {"success": False, "error": "连接超时, 请检查 SSID 和密码"}

    # 通过 DHCP 获取 IP
    try:
        subprocess.run(["dhclient", "-v", interface], capture_output=True, text=True, timeout=30)
    except Exception:
        pass

    # 获取 IP
    ip = _get_wifi_ip(interface)

    _write_mode_state({
        "mode": "client",
        "ap": {},
        "client": {"ssid": ssid},
    })

    return {
        "success": True,
        "message": f"已连接到 {ssid}",
        "interface": interface,
        "ip": ip,
        "ssid": ssid,
    }


def _stop_client(interface: str) -> dict:
    """停止 Client 模式"""
    try:
        subprocess.run(["dhclient", "-r", interface], capture_output=True, timeout=5)
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["wpa_cli", "-i", interface, "terminate"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        pass
    try:
        subprocess.run(["ip", "link", "set", interface, "down"], capture_output=True, timeout=5)
    except Exception:
        pass
    try:
        subprocess.run(["ip", "addr", "flush", "dev", interface], capture_output=True, timeout=5)
    except Exception:
        pass
    _write_mode_state({"mode": None, "ap": {}, "client": {}})
    return {"success": True, "message": "Client 已断开"}


# ─── API 路由 ──────────────────────────────────────────────────────


@router.get("/status")
async def wireless_status(auth=Depends(require_auth)):
    """获取无线状态: 硬件信息, 当前模式, 连接详情"""
    iface = _detect_wifi_interface()
    if not iface:
        return {
            "available": False,
            "error": "未检测到无线网卡",
            "interface": None,
        }

    phy = _get_wifi_phy(iface)
    state = _read_mode_state()
    mode = state.get("mode")

    # 检测进程是否真的在运行
    hostapd_running = _is_process_running("hostapd")
    wpa_running = _is_process_running("wpa_supplicant")

    # 实际模式 vs 记录模式
    actual_mode = "idle"
    if hostapd_running:
        actual_mode = "ap"
    elif wpa_running:
        actual_mode = "client"
    else:
        actual_mode = "idle"

    result = {
        "available": True,
        "interface": iface,
        "phy": phy,
        "mac": "",
        "mode": actual_mode,
        "last_mode": mode,
        "ap": {"running": hostapd_running, "ssid": "", "channel": 0, "stations": []},
        "client": {"running": wpa_running, "ssid": "", "ip": None, "signal_dbm": None},
    }

    # 获取 MAC
    mac_path = Path(f"/sys/class/net/{iface}/address")
    if mac_path.exists():
        result["mac"] = mac_path.read_text().strip().upper()

    # 获取 AP 详情
    if hostapd_running and HOSTAPD_CONF.exists():
        try:
            conf = HOSTAPD_CONF.read_text()
            for line in conf.split("\n"):
                if line.startswith("ssid="):
                    result["ap"]["ssid"] = line.split("=", 1)[1].strip()
                elif line.startswith("channel="):
                    try:
                        result["ap"]["channel"] = int(line.split("=")[1].strip())
                    except ValueError:
                        pass
            result["ap"]["stations"] = _get_connected_stations(iface)
        except Exception:
            pass

    # 获取 Client 详情
    if wpa_running:
        try:
            r = subprocess.run(
                ["wpa_cli", "-i", iface, "status"],
                capture_output=True, text=True, timeout=5,
            )
            for line in r.stdout.split("\n"):
                if line.startswith("ssid="):
                    result["client"]["ssid"] = line.split("=", 1)[1].strip()
                elif line.startswith("ip_address="):
                    ip = line.split("=", 1)[1].strip()
                    result["client"]["ip"] = ip if ip else None
                elif "signal" in line.lower():
                    try:
                        result["client"]["signal_dbm"] = int(line.split("=")[1].strip())
                    except (ValueError, IndexError):
                        pass
        except Exception:
            pass

    return result


@router.get("/scan")
async def scan_networks(interface: Optional[str] = None, auth=Depends(require_auth)):
    """扫描附近的 WiFi 网络"""
    iface = interface or _detect_wifi_interface()
    if not iface:
        return {"success": False, "networks": [], "error": "无可用无线接口"}

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
        elif "SSID:" in line and not line.startswith("SSID list"):
            ssid = line.split(":", 1)[1].strip().strip('"')
            if ssid:
                current["ssid"] = ssid
        elif line.startswith("freq:"):
            try:
                current["frequency"] = int(line.split()[1])
            except (ValueError, IndexError):
                pass
        elif line.startswith("signal:"):
            parts = line.split()
            for p in parts:
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

    # 去重 (保留信号最强的)
    seen = {}
    for net in networks:
        ssid = net["ssid"]
        if ssid not in seen or net.get("signal_dbm", -100) > seen[ssid].get("signal_dbm", -100):
            seen[ssid] = net

    result = []
    for ssid, net in seen.items():
        enc = "open"
        if net.get("encrypted") or net.get("wep"):
            enc = "wpa2" if net.get("encrypted") else "wep"
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
    """启动 AP 模式 (热点) — 提供 WiFi 覆盖"""
    iface = _detect_wifi_interface()
    if not iface:
        raise HTTPException(status_code=400, detail="无可用无线接口")

    # 如果是 Client 模式, 先停止
    if _is_process_running("wpa_supplicant"):
        _stop_client(iface)
        time.sleep(1)

    # 确保接口可以操作
    try:
        subprocess.run(["ip", "link", "set", iface, "down"], capture_output=True, timeout=5)
        time.sleep(0.5)
        subprocess.run(["ip", "link", "set", iface, "up"], capture_output=True, timeout=5)
    except Exception:
        pass

    # 设置到正确的频段 (2.4GHz)
    hw_mode_map = {"a": "a", "b": "b", "g": "g"}
    config = body.model_dump()
    config["hw_mode"] = hw_mode_map.get(body.hw_mode, "g")

    result = _start_ap(iface, config)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "AP 启动失败"))

    return result


@router.post("/ap/stop")
async def stop_ap(auth=Depends(require_auth)):
    """停止 AP 模式"""
    iface = _detect_wifi_interface()
    if not iface:
        raise HTTPException(status_code=400, detail="无可用无线接口")
    return _stop_ap(iface)


@router.post("/client/connect")
async def client_connect(body: ClientConnectRequest, auth=Depends(require_auth)):
    """以 Client 模式连接上级 AP — 此接口成为 WAN"""
    iface = _detect_wifi_interface()
    if not iface:
        raise HTTPException(status_code=400, detail="无可用无线接口")

    # 如果是 AP 模式, 先停止
    if _is_process_running("hostapd"):
        _stop_ap(iface)
        time.sleep(1)

    result = _start_client(iface, body.model_dump())
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "连接失败"))

    return result


@router.post("/client/disconnect")
async def client_disconnect(auth=Depends(require_auth)):
    """断开 Client 模式连接"""
    iface = _detect_wifi_interface()
    if not iface:
        raise HTTPException(status_code=400, detail="无可用无线接口")
    return _stop_client(iface)


@router.post("/reset")
async def wireless_reset(auth=Depends(require_auth)):
    """重置无线 (停止所有服务)"""
    iface = _detect_wifi_interface()
    if not iface:
        return {"success": False, "message": "无无线接口"}
    _stop_ap(iface)
    _stop_client(iface)
    return {"success": True, "message": "无线已重置"}


@router.get("/interfaces")
async def wireless_interfaces(auth=Depends(require_auth)):
    """列出无线接口信息"""
    iface = _detect_wifi_interface()
    if not iface:
        return {"available": False, "interfaces": []}

    info = {
        "name": iface,
        "mac": "",
        "state": "down",
        "mode": "n/a",
    }

    mac_path = Path(f"/sys/class/net/{iface}/address")
    if mac_path.exists():
        info["mac"] = mac_path.read_text().strip().upper()

    oper_path = Path(f"/sys/class/net/{iface}/operstate")
    if oper_path.exists():
        info["state"] = oper_path.read_text().strip()

    # 通过 iw 获取更多信息
    try:
        r = subprocess.run(["iw", "dev", iface, "info"], capture_output=True, text=True, timeout=5)
        for line in r.stdout.split("\n"):
            if "type " in line:
                info["mode"] = line.split()[-1]
    except Exception:
        pass

    return {"available": True, "count": 1, "interfaces": [info]}
