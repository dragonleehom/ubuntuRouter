"""Wireless API — 基于 NetworkManager (nmcli) 的 WiFi 管理

所有操作委托给 nmcli:
- AP 模式: nmcli con add type wifi mode ap + nmcli con up
- Client 模式: nmcli dev wifi connect + nmcli con up
- 扫描: nmcli dev wifi list
- 状态: nmcli dev status / nmcli con show

优势: nmcli 自动处理 hostapd/wpa_supplicant, 配置持久化, DHCP
"""

import logging
import subprocess
import re
import time
import os
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import require_auth

logger = logging.getLogger(__name__)
router = APIRouter()

# ─── 模型 ──────────────────────────────────────────────────────────


class APConfigRequest(BaseModel):
    """AP 热点配置"""
    ssid: str = Field(..., min_length=1, max_length=32)
    password: Optional[str] = Field(None, min_length=8, max_length=63)
    band: Optional[str] = Field(None, pattern="^(a|bg|ax)?$")  # a=5GHz, bg=2.4GHz, ax=WiFi6
    channel: Optional[int] = Field(None, ge=1, le=165)


class ClientConnectRequest(BaseModel):
    """Client 连接请求"""
    ssid: str = Field(..., min_length=1, max_length=32)
    password: Optional[str] = None
    hidden: bool = False


class AdvancedSettingRequest(BaseModel):
    """高级参数设置"""
    txpower: Optional[int] = Field(None, ge=1, le=30)
    channel_width: Optional[int] = Field(None, ge=20, le=160)
    country: Optional[str] = Field(None, min_length=2, max_length=2)


class MacFilterAddRequest(BaseModel):
    """MAC 过滤添加"""
    mac: str = Field(..., pattern=r'^([0-9A-Fa-f]{2}[:.-]){5}[0-9A-Fa-f]{2}$')
    comment: Optional[str] = None


# ─── Nmcli 封装 ────────────────────────────────────────────────────


def _nmcli(args: list, timeout: int = 15) -> dict:
    """执行 nmcli 命令, 返回结构化结果"""
    cmd = ["sudo", "nmcli"] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        stdout = r.stdout.strip()
        stderr = r.stderr.strip()
        return {
            "success": r.returncode == 0,
            "stdout": stdout,
            "stderr": stderr,
            "returncode": r.returncode,
        }
    except FileNotFoundError:
        return {"success": False, "error": "nmcli not found"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "command timed out"}


def _run_iw(args: list, timeout: int = 10) -> dict:
    """执行 iw 命令"""
    cmd = ["sudo", "iw"] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {
            "success": r.returncode == 0,
            "stdout": r.stdout.strip(),
            "stderr": r.stderr.strip(),
            "returncode": r.returncode,
        }
    except FileNotFoundError:
        return {"success": False, "error": "iw not found"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "command timed out"}


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
    return mac_path.read_text().strip().upper() if mac_path.exists() else ""


# ─── 高级参数辅助 ────────────────────────────────────────────────


HOSTAPD_CONF = Path("/etc/hostapd/hostapd.conf")


def _read_hostapd_conf() -> dict:
    """读取 hostapd.conf 返回键值对"""
    config = {}
    if HOSTAPD_CONF.exists():
        for line in HOSTAPD_CONF.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                config[key.strip()] = val.strip()
    return config


def _write_hostapd_conf(config: dict):
    """写入 hostapd.conf"""
    HOSTAPD_CONF.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for k, v in config.items():
        lines.append(f"{k}={v}")
    HOSTAPD_CONF.write_text("\n".join(lines) + "\n")


def _get_macfilter_list() -> list:
    """从 hostapd.conf 读取 MAC 过滤列表"""
    config = _read_hostapd_conf()
    mode = config.get("macaddr_acl", "0")  # 0=disable, 1=allow, 2=deny
    acl_list = []
    # hostapd uses accept_mac_file / deny_mac_file or inline accept/deny
    # Try inline first
    i = 0
    while f"accept_mac{i}" in config or f"deny_mac{i}" in config:
        key = f"accept_mac{i}" if f"accept_mac{i}" in config else f"deny_mac{i}"
        acl_list.append(config[key])
        i += 1
    # If no inline, try file-based
    if not acl_list:
        file_key = "accept_mac_file" if mode == "1" else "deny_mac_file"
        file_path = config.get(file_key)
        if file_path:
            p = Path(file_path)
            if p.exists():
                acl_list = [l.strip() for l in p.read_text().splitlines()
                           if l.strip() and not l.strip().startswith("#")]
    return acl_list, mode


def _write_macfilter_list(macs: list, mode: str):
    """写入 MAC 过滤列表到 hostapd.conf"""
    config = _read_hostapd_conf()
    config["macaddr_acl"] = mode
    # Remove old inline entries
    keys_to_remove = [k for k in config if k.startswith("accept_mac") or k.startswith("deny_mac")]
    for k in keys_to_remove:
        del config[k]
    # Remove old file entries
    for fk in ["accept_mac_file", "deny_mac_file"]:
        if fk in config:
            del config[fk]

    # Write inline entries
    for i, mac in enumerate(macs):
        if mode == "1":
            config[f"accept_mac{i}"] = mac
        else:
            config[f"deny_mac{i}"] = mac

    _write_hostapd_conf(config)

    # Reload hostapd if running
    subprocess.run(["sudo", "systemctl", "reload", "hostapd"],
                   capture_output=True, timeout=10)
    subprocess.run(["sudo", "systemctl", "reload-or-restart", "hostapd"],
                   capture_output=True, timeout=10)


# ─── API 路由 ──────────────────────────────────────────────────────


@router.get("/status")
async def wireless_status(auth=Depends(require_auth)):
    """获取无线状态"""
    iface = _detect_wifi_interface()
    if not iface:
        return {"available": False, "error": "未检测到无线网卡", "interface": None}

    mac = _get_wifi_mac(iface)
    result = {
        "available": True,
        "interface": iface,
        "mac": mac,
        "mode": "idle",
        "ap": {"running": False, "ssid": "", "band": "", "channel": 0, "stations": []},
        "client": {"running": False, "ssid": "", "ip": None, "signal_dbm": None},
    }

    # 1. 检查活跃连接
    r = _nmcli(["-t", "-f", "NAME,TYPE,DEVICE", "con", "show", "--active"])
    if r["success"]:
        for line in r["stdout"].split("\n"):
            parts = line.split(":")
            if len(parts) >= 3 and ("wifi" in parts[1] or "802-11" in parts[1]):
                conn_name = parts[0]
                # 判断是 AP 还是 client
                r_info = _nmcli(["-t", "-f", "802-11-wireless.mode,802-11-wireless.ssid,802-11-wireless-security.key-mgmt", "con", "show", conn_name])
                if r_info["success"]:
                    mode_line = [l for l in r_info["stdout"].split("\n") if l.startswith("802-11-wireless.mode:")]
                    ssid_line = [l for l in r_info["stdout"].split("\n") if l.startswith("802-11-wireless.ssid:")]
                    mode = mode_line[0].split(":", 1)[1].strip() if mode_line else ""
                    ssid = ssid_line[0].split(":", 1)[1].strip() if ssid_line else ""

                    if mode == "ap":
                        result["mode"] = "ap"
                        result["ap"]["running"] = True
                        result["ap"]["ssid"] = ssid

                        # 获取已连接设备
                        r_sta = subprocess.run(
                            ["iw", "dev", iface, "station", "dump"],
                            capture_output=True, text=True, timeout=5,
                        )
                        stations = []
                        cur = {}
                        for ln in r_sta.stdout.split("\n"):
                            ln = ln.strip()
                            if ln.startswith("Station "):
                                if cur.get("mac"):
                                    stations.append(cur)
                                cur = {"mac": ln.split()[1].upper()}
                            elif "signal:" in ln:
                                try:
                                    cur["signal_dbm"] = float(ln.split()[1].replace("dBm", ""))
                                except (ValueError, IndexError):
                                    pass
                            elif "tx bitrate:" in ln:
                                m = re.search(r"(\d+\.?\d*)\s*MBit/s", ln)
                                if m:
                                    cur["tx_bitrate"] = float(m.group(1))
                            elif "rx bitrate:" in ln:
                                m = re.search(r"(\d+\.?\d*)\s*MBit/s", ln)
                                if m:
                                    cur["rx_bitrate"] = float(m.group(1))
                            elif "connected time:" in ln:
                                try:
                                    cur["connected_sec"] = int(ln.split(":")[1].strip().split()[0])
                                except (ValueError, IndexError):
                                    pass
                        if cur.get("mac"):
                            stations.append(cur)
                        result["ap"]["stations"] = stations

                    else:  # client (infrastructure)
                        result["mode"] = "client"
                        result["client"]["running"] = True
                        result["client"]["ssid"] = ssid

                        # 从活跃连接获取 IP
                        r_ip = _nmcli(["-t", "-f", "IP4.ADDRESS", "con", "show", conn_name])
                        if r_ip["success"]:
                            for ln in r_ip["stdout"].split("\n"):
                                if ln.startswith("IP4.ADDRESS"):
                                    result["client"]["ip"] = ln.split(":", 1)[1].strip()
                                    break

                        # 从 iw link 获取信号
                        r_link = subprocess.run(
                            ["iw", "dev", iface, "link"],
                            capture_output=True, text=True, timeout=5,
                        )
                        for ln in r_link.stdout.split("\n"):
                            if "signal:" in ln:
                                for p in ln.split():
                                    if "dBm" in p:
                                        try:
                                            result["client"]["signal_dbm"] = float(p.replace("dBm", ""))
                                        except ValueError:
                                            pass
                                        break

    return result


@router.get("/interfaces")
async def wireless_interfaces(auth=Depends(require_auth)):
    """列出无线接口"""
    iface = _detect_wifi_interface()
    if not iface:
        return {"available": False, "interfaces": []}

    r = _nmcli(["-t", "-f", "DEVICE,TYPE,STATE", "dev", "status"])
    info = {"name": iface, "mac": _get_wifi_mac(iface), "state": "down", "mode": ""}
    if r["success"]:
        for line in r["stdout"].split("\n"):
            parts = line.split(":")
            if len(parts) >= 3 and parts[0] == iface:
                info["state"] = parts[2]
                break

    try:
        r2 = subprocess.run(
            ["iw", "dev", iface, "info"], capture_output=True, text=True, timeout=5,
        )
        for line in r2.stdout.split("\n"):
            if "type " in line:
                info["mode"] = line.split()[-1]
    except Exception:
        pass

    return {"available": True, "count": 1, "interfaces": [info]}


@router.get("/scan")
async def scan_networks(auth=Depends(require_auth)):
    """扫描附近的 WiFi 网络 — 使用 nmcli dev wifi list"""
    iface = _detect_wifi_interface()
    if not iface:
        return {"success": False, "networks": [], "error": "无可用无线接口"}

    # 确保接口 up 且 WiFi radio on
    _nmcli(["radio", "wifi", "on"])

    r = _nmcli(["-t", "-f", "SSID,BSSID,MODE,CHAN,FREQ,RATE,SIGNAL,SECURITY", "dev", "wifi", "list", "--rescan", "yes"], timeout=30)
    if not r["success"]:
        return {"success": False, "networks": [], "error": r.get("stderr", r.get("error", "扫描失败"))[:200]}

    networks = []
    seen = set()
    for line in r["stdout"].split("\n"):
        if not line.strip():
            continue
        parts = line.split(":")
        if len(parts) >= 8:
            ssid = parts[0]
            bssid = parts[1]
            freq = parts[4]
            signal = parts[6]
            security = parts[7]

            if not ssid or ssid in seen:
                continue
            seen.add(ssid)

            try:
                freq_int = int(freq)
            except ValueError:
                freq_int = 0

            enc = "open"
            if security and security not in ("", "--", "WEP"):
                enc = "wpa2"

            try:
                sig_val = int(signal)
            except ValueError:
                sig_val = -100

            networks.append({
                "ssid": ssid,
                "bssid": bssid.upper() if bssid else "",
                "frequency": freq_int,
                "band": "5GHz" if freq_int > 4000 else "2.4GHz",
                "signal_dbm": sig_val,
                "encryption": enc,
            })

    networks.sort(key=lambda x: x["signal_dbm"], reverse=True)
    return {"success": True, "count": len(networks), "networks": networks}


@router.post("/ap/start")
async def start_ap(body: APConfigRequest, auth=Depends(require_auth)):
    """启动 AP 热点 — nmcli con add mode ap"""
    iface = _detect_wifi_interface()
    if not iface:
        raise HTTPException(status_code=400, detail="无可用无线接口")

    # 1. 先断开 Client 模式 (如果有)
    r_active = _nmcli(["-t", "-f", "NAME,TYPE", "con", "show", "--active"])
    if r_active["success"]:
        for line in r_active["stdout"].split("\n"):
            parts = line.split(":")
            if len(parts) >= 2 and ("wifi" in parts[1] or "802-11" in parts[1]):
                _nmcli(["con", "down", parts[0]])

    # 2. 构造连接名
    conn_name = f"AP-{body.ssid}"

    # 3. 删除已有同名连接
    _nmcli(["con", "delete", conn_name])

    # 4. 创建热点
    cmd_create = ["con", "add", "type", "wifi", "ifname", iface, "mode", "ap", "con-name", conn_name, "ssid", body.ssid]
    r = _nmcli(cmd_create)
    if not r["success"]:
        raise HTTPException(status_code=500, detail=f"创建热点失败: {r.get('stderr', '')}")

    # 5. 设置密码 (如果有)
    if body.password:
        _nmcli(["con", "modify", conn_name, "wifi-sec.key-mgmt", "wpa-psk"])
        _nmcli(["con", "modify", conn_name, "wifi-sec.psk", body.password])

    # 6. 设置频段
    if body.band:
        band_map = {"a": "a", "bg": "bg", "ax": "ax"}
        _nmcli(["con", "modify", conn_name, "802-11-wireless.band", band_map.get(body.band, "")])
    if body.channel:
        _nmcli(["con", "modify", conn_name, "802-11-wireless.channel", str(body.channel)])

    # 7. 启用 IP 共享 (DHCP + NAT)
    _nmcli(["con", "modify", conn_name, "ipv4.method", "shared"])

    # 8. 启动热点
    r = _nmcli(["con", "up", conn_name], timeout=30)
    if not r["success"]:
        raise HTTPException(status_code=500, detail=f"启动热点失败: {r.get('stderr', '')}")

    return {
        "success": True,
        "message": f"AP '{body.ssid}' 已启动",
        "interface": iface,
        "ssid": body.ssid,
        "connection": conn_name,
    }


@router.post("/ap/stop")
async def stop_ap(auth=Depends(require_auth)):
    """停止 AP 热点"""
    # 查找所有活跃的 AP 连接并停止
    r = _nmcli(["-t", "-f", "NAME,TYPE,DEVICE", "con", "show", "--active"])
    stopped = False
    if r["success"]:
        for line in r["stdout"].split("\n"):
            parts = line.split(":")
            if len(parts) >= 3 and ("wifi" in parts[1] or "802-11" in parts[1]):
                # 检查是否 AP 模式
                r_mode = _nmcli(["-t", "-f", "802-11-wireless.mode", "con", "show", parts[0]])
                if r_mode["success"] and "ap" in r_mode["stdout"]:
                    _nmcli(["con", "down", parts[0]])
                    _nmcli(["con", "delete", parts[0]])
                    stopped = True

    if not stopped:
        raise HTTPException(status_code=400, detail="没有活跃的 AP 热点")
    return {"success": True, "message": "AP 已停止"}


@router.post("/client/connect")
async def client_connect(body: ClientConnectRequest, auth=Depends(require_auth)):
    """连接上级 AP — nmcli dev wifi connect"""
    iface = _detect_wifi_interface()
    if not iface:
        raise HTTPException(status_code=400, detail="无可用无线接口")

    _nmcli(["radio", "wifi", "on"])

    # 1. 先停掉 AP 模式
    r_active = _nmcli(["-t", "-f", "NAME,TYPE", "con", "show", "--active"])
    if r_active["success"]:
        for line in r_active["stdout"].split("\n"):
            parts = line.split(":")
            if len(parts) >= 2 and ("wifi" in parts[1] or "802-11" in parts[1]):
                _nmcli(["con", "down", parts[0]])

    # 2. 用 nmcli 连接
    cmd = ["dev", "wifi", "connect", body.ssid, "ifname", iface]
    if body.password:
        cmd += ["password", body.password]
    if body.hidden:
        cmd += ["--hidden"]

    r = _nmcli(cmd, timeout=30)
    if not r["success"]:
        raise HTTPException(status_code=500, detail=f"连接失败: {r.get('stderr', r.get('error', ''))}")

    time.sleep(2)

    # 获取 IP
    ip = None
    r_ip = _nmcli(["-t", "-f", "IP4.ADDRESS", "con", "show", body.ssid])
    if r_ip["success"]:
        for line in r_ip["stdout"].split("\n"):
            if line.startswith("IP4.ADDRESS"):
                ip = line.split(":", 1)[1].strip()
                break

    return {
        "success": True,
        "message": f"已连接到 {body.ssid}",
        "interface": iface,
        "ssid": body.ssid,
        "ip": ip,
    }


@router.post("/client/disconnect")
async def client_disconnect(auth=Depends(require_auth)):
    """断开 Client 连接"""
    r = _nmcli(["-t", "-f", "NAME,TYPE", "con", "show", "--active"])
    disconnected = False
    if r["success"]:
        for line in r["stdout"].split("\n"):
            parts = line.split(":")
            if len(parts) >= 2 and ("wifi" in parts[1] or "802-11" in parts[1]):
                _nmcli(["con", "down", parts[0]])
                _nmcli(["con", "delete", parts[0]])
                disconnected = True

    if not disconnected:
        return {"success": True, "message": "没有活跃的 WiFi 连接"}
    return {"success": True, "message": "已断开"}


@router.post("/reset")
async def wireless_reset(auth=Depends(require_auth)):
    """重置无线 (删除所有 WiFi 连接)"""
    r = _nmcli(["-t", "-f", "NAME,TYPE", "con", "show"])
    if r["success"]:
        for line in r["stdout"].split("\n"):
            parts = line.split(":")
            if len(parts) >= 2 and ("wifi" in parts[1] or "802-11" in parts[1]):
                _nmcli(["con", "down", parts[0]])
                _nmcli(["con", "delete", parts[0]])
    return {"success": True, "message": "无线已重置"}


# ─── 高级参数端点 ──────────────────────────────────────────────────


@router.get("/advanced/{iface}")
async def get_advanced_params(iface: str, auth=Depends(require_auth)):
    """获取无线高级参数: txpower / channel_width / country"""
    result = {
        "txpower": None,
        "channel_width": None,
        "country": None,
        "supported_txpower": [5, 10, 15, 20, 30],
        "supported_widths": [20, 40, 80, 160],
    }

    # 1. 获取 txpower — iw dev iface info
    r = _run_iw(["dev", iface, "info"])
    if r["success"]:
        for line in r["stdout"].split("\n"):
            line = line.strip()
            m = re.search(r"txpower\s+(\d+\.?\d*)\s*dBm", line)
            if m:
                result["txpower"] = int(float(m.group(1)))
            m2 = re.search(r"channel\s+\d+\s+\((\d+)\s*MHz", line)
            if m2:
                ch_width = int(m2.group(1))
                # Determine channel width from center freq and primary channel
                result["channel_width"] = 20  # default, could refine

    # Try to get channel width from iw link or iw survey
    r2 = _run_iw(["dev", iface, "survey", "dump"])
    if r2["success"] and result["channel_width"] is None:
        for line in r2["stdout"].split("\n"):
            m = re.search(r"in\s+use.*?(\d+)\s*MHz", line)
            if m:
                result["channel_width"] = int(m.group(1))
                break

    # 2. 国家码 — iw reg get
    r3 = _run_iw(["reg", "get"])
    if r3["success"]:
        for line in r3["stdout"].split("\n"):
            line = line.strip()
            m = re.search(r"country\s+(\w{2})", line)
            if m:
                result["country"] = m.group(1).upper()
                break

    return result


@router.post("/advanced/{iface}")
async def set_advanced_params(iface: str, body: AdvancedSettingRequest, auth=Depends(require_auth)):
    """设置无线高级参数: txpower / channel_width / country"""
    results = {}

    if body.txpower is not None:
        # iw dev iface set txpower fixed <value>
        r = _run_iw(["dev", iface, "set", "txpower", "fixed", str(body.txpower)])
        results["txpower"] = {
            "success": r["success"],
            "message": "发射功率已设置" if r["success"] else f"设置失败: {r.get('stderr', '')}",
        }

    if body.country is not None:
        # iw reg set <country>
        r = _run_iw(["reg", "set", body.country.upper()])
        if r["success"]:
            # Also set via hostapd.conf for AP mode
            hostapd_config = _read_hostapd_conf()
            if hostapd_config:
                hostapd_config["country_code"] = body.country.upper()
                _write_hostapd_conf(hostapd_config)
                subprocess.run(["sudo", "systemctl", "reload-or-restart", "hostapd"],
                               capture_output=True, timeout=10)
        results["country"] = {
            "success": r["success"],
            "message": f"国家码已设为 {body.country.upper()}" if r["success"] else f"设置失败: {r.get('stderr', '')}",
        }

    if body.channel_width is not None:
        # Channel width is set via hostapd.conf (ht_capab / vht_oper_chwidth)
        hostapd_config = _read_hostapd_conf()
        if hostapd_config:
            # For 802.11n (HT): ht_capab includes channel width
            width_map = {
                20: "[HT40-]",
                40: "[HT40+]",
                80: "[HT40+][HT80]",
                160: "[HT40+][HT80][HT160]",
            }
            if body.channel_width in width_map:
                hostapd_config["ht_capab"] = width_map[body.channel_width]
            if body.channel_width >= 80:
                # VHT (802.11ac) channel width
                vht_width = 1 if body.channel_width == 80 else (2 if body.channel_width == 160 else 0)
                hostapd_config["vht_oper_chwidth"] = str(vht_width)
            _write_hostapd_conf(hostapd_config)
            subprocess.run(["sudo", "systemctl", "reload-or-restart", "hostapd"],
                           capture_output=True, timeout=10)
        results["channel_width"] = {
            "success": True,
            "message": f"信道宽度已设为 {body.channel_width}MHz",
        }

    # If nothing was set
    if not results:
        raise HTTPException(status_code=400, detail="未提供任何可设置的参数")

    return {"success": True, "results": results}


# ─── MAC 过滤端点 ──────────────────────────────────────────────────


@router.get("/macfilter/{iface}")
async def get_macfilter(iface: str, auth=Depends(require_auth)):
    """获取 MAC 过滤配置"""
    mac_list, mode = _get_macfilter_list()
    return {
        "enabled": mode != "0",
        "mode": "allow" if mode == "1" else ("deny" if mode == "2" else "disable"),
        "mode_raw": mode,
        "macs": mac_list,
    }


@router.post("/macfilter/{iface}")
async def set_macfilter(iface: str, body: dict, auth=Depends(require_auth)):
    """设置 MAC 过滤 (整体保存)"""
    enabled = body.get("enabled", False)
    mode = body.get("mode", "deny")  # "allow" or "deny"
    macs = body.get("macs", [])

    raw_mode = "0"
    if enabled:
        raw_mode = "1" if mode == "allow" else "2"

    _write_macfilter_list(macs, raw_mode)

    return {
        "success": True,
        "message": "MAC 过滤配置已更新",
        "enabled": enabled,
        "mode": mode,
        "macs": macs,
    }


@router.post("/macfilter/{iface}/add")
async def add_macfilter(iface: str, body: MacFilterAddRequest, auth=Depends(require_auth)):
    """添加单个 MAC 地址到过滤列表"""
    mac_list, mode = _get_macfilter_list()
    # Normalize MAC
    mac = body.mac.upper().replace("-", ":").replace(".", ":")
    if mac in mac_list:
        raise HTTPException(status_code=400, detail="MAC 地址已在列表中")
    mac_list.append(mac)
    _write_macfilter_list(mac_list, mode)
    return {"success": True, "message": f"MAC {mac} 已添加", "macs": mac_list}


@router.delete("/macfilter/{iface}/{mac:path}")
async def delete_macfilter(iface: str, mac: str, auth=Depends(require_auth)):
    """删除单个 MAC 地址"""
    mac_list, mode = _get_macfilter_list()
    # Normalize
    target = mac.upper().replace("-", ":").replace(".", ":")
    if target not in mac_list:
        raise HTTPException(status_code=404, detail="MAC 地址不在列表中")
    mac_list = [m for m in mac_list if m != target]
    _write_macfilter_list(mac_list, mode)
    return {"success": True, "message": f"MAC {target} 已删除", "macs": mac_list}
