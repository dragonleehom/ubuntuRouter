"""Wireless API — WiFi interface detection, AP scanning, connection management

Uses iw (nl80211) for scanning and wpa_supplicant for client mode,
and hostapd for AP mode. Falls back gracefully if no WiFi hardware detected.
"""

import logging
import subprocess
import re
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import require_auth

logger = logging.getLogger(__name__)
router = APIRouter()

# ─── Models ────────────────────────────────────────────────────────


class WiFiConnectRequest(BaseModel):
    ssid: str = Field(..., min_length=1, max_length=32)
    password: Optional[str] = None
    hidden: bool = False


class WiFiConfigRequest(BaseModel):
    mode: str = Field(default="client", pattern="^(client|ap)$")  # client or ap
    ssid: str = Field(..., min_length=1, max_length=32)
    password: Optional[str] = None
    channel: Optional[int] = None


# ─── Helpers ───────────────────────────────────────────────────────


def _detect_wifi_interfaces() -> list:
    """Detect physical WiFi interfaces using iw or sysfs."""
    # Try iw first
    try:
        r = subprocess.run(["iw", "dev"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            interfaces = []
            current = {}
            for line in r.stdout.split("\n"):
                line = line.strip()
                if line.startswith("Interface "):
                    if current.get("name"):
                        interfaces.append(current)
                    current = {"name": line.split()[1]}
                elif line.startswith("wiphy "):
                    current["phy"] = int(line.split()[1])
                elif line.startswith("addr "):
                    current["mac"] = line.split()[1].upper()
                elif line.startswith("type "):
                    current["type"] = line.split()[1]
            if current.get("name"):
                interfaces.append(current)
            return interfaces
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: scan /sys/class/net for wireless phy
    wifi_ifaces = []
    net_dir = Path("/sys/class/net")
    if net_dir.exists():
        for iface in net_dir.iterdir():
            wireless_dir = iface / "wireless"
            if wireless_dir.exists():
                wifi_ifaces.append({"name": iface.name, "type": "unknown", "mac": ""})
    return wifi_ifaces


def _run_iw_command(args: list, timeout: int = 10) -> dict:
    """Run an iw command and return structured result."""
    try:
        r = subprocess.run(["iw"] + args, capture_output=True, text=True, timeout=timeout)
        return {
            "success": r.returncode == 0,
            "stdout": r.stdout,
            "stderr": r.stderr,
            "returncode": r.returncode,
        }
    except FileNotFoundError:
        return {"success": False, "error": "iw command not found"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "command timed out"}


# ─── Routes ────────────────────────────────────────────────────────


@router.get("/interfaces")
async def list_wifi_interfaces(auth=Depends(require_auth)):
    """List detected WiFi interfaces with capabilities."""
    interfaces = _detect_wifi_interfaces()

    # Check if wireless is available at all
    try:
        r = subprocess.run(["iwconfig"], capture_output=True, text=True, timeout=5)
        has_wireless_tools = r.returncode == 0
    except FileNotFoundError:
        has_wireless_tools = False

    # Check wpa_supplicant status
    wpa_running = False
    try:
        r = subprocess.run(
            ["systemctl", "is-active", "wpa_supplicant"],
            capture_output=True, text=True, timeout=5,
        )
        wpa_running = r.stdout.strip() == "active"
    except Exception:
        pass

    return {
        "available": len(interfaces) > 0,
        "count": len(interfaces),
        "interfaces": interfaces,
        "has_wireless_tools": has_wireless_tools,
        "wpa_supplicant_running": wpa_running,
    }


@router.get("/scan")
async def scan_wifi_networks(interface: str = "wlan0", auth=Depends(require_auth)):
    """Scan for available WiFi networks on the given interface."""
    result = _run_iw_command(["dev", interface, "scan", "-u"], timeout=15)
    if not result["success"]:
        return {"success": False, "networks": [], "error": result.get("error", result.get("stderr", ""))[:200]}

    # Parse iw scan output
    networks = []
    current = {}
    ssid_keys = {}

    for raw_line in result["stdout"].split("\n"):
        line = raw_line.strip()

        if line.startswith("BSS "):
            if current.get("ssid"):
                networks.append(current)
            current = {"bssid": line.split()[1].upper()}
            ssid_keys = {}

        elif line.startswith("SSID:"):
            ssid = line[5:].strip().strip('"')
            if ssid:
                current["ssid"] = ssid

        elif line.startswith("freq:"):
            try:
                current["frequency"] = int(line.split()[1])
            except (IndexError, ValueError):
                pass

        elif line.startswith("signal:"):
            parts = line.split()
            for p in parts:
                try:
                    current["signal_dbm"] = float(p.replace("dBm", ""))
                    break
                except ValueError:
                    continue

        elif line.startswith("WPA:"):
            current["wpa"] = True

        elif line.startswith("RSN:"):
            current["wpa2"] = True

        elif line.startswith("WEP:"):
            current["wep"] = True

        elif "Authentication" in line and ":" in line:
            current["auth"] = line.split(":", 1)[1].strip()

        elif "Group cipher" in line and ":" in line:
            current["group_cipher"] = line.split(":", 1)[1].strip()

    if current.get("ssid"):
        networks.append(current)

    # Deduplicate by SSID, keep strongest signal
    seen = {}
    for net in networks:
        ssid = net.get("ssid", "")
        if ssid in seen:
            if net.get("signal_dbm", -100) > seen[ssid].get("signal_dbm", -100):
                seen[ssid] = net
        else:
            seen[ssid] = net

    # Detect encryption type
    result_networks = []
    for ssid, net in seen.items():
        enc = "open"
        if net.get("wpa2"):
            enc = "wpa2"
        elif net.get("wpa"):
            enc = "wpa"
        elif net.get("wep"):
            enc = "wep"

        result_networks.append({
            "ssid": ssid,
            "bssid": net.get("bssid", ""),
            "frequency": net.get("frequency", 0),
            "band": "5GHz" if net.get("frequency", 0) > 4000 else "2.4GHz",
            "signal_dbm": net.get("signal_dbm", -100),
            "encryption": enc,
        })

    result_networks.sort(key=lambda x: x["signal_dbm"], reverse=True)

    return {"success": True, "count": len(result_networks), "networks": result_networks}


@router.get("/status")
async def wifi_status(auth=Depends(require_auth)):
    """Get WiFi interface status (connected SSID, signal, IP)."""
    interfaces = _detect_wifi_interfaces()
    if not interfaces:
        return {"available": False, "connected": False, "message": "No WiFi hardware detected"}

    results = []
    for iface in interfaces:
        name = iface["name"]
        info = {"interface": name, "connected": False}

        # Get link status from iw link
        link = _run_iw_command(["dev", name, "link"])
        if link["success"]:
            for raw_line in link["stdout"].split("\n"):
                line = raw_line.strip()
                if "Connected to" in line:
                    info["connected"] = True
                    m = re.search(r"([0-9a-fA-F:]{17})", line)
                    if m:
                        info["bssid"] = m.group(1).upper()
                elif line.startswith("SSID:"):
                    info["ssid"] = line[5:].strip().strip('"')
                elif line.startswith("freq:"):
                    try:
                        info["frequency"] = int(line.split()[1])
                    except (ValueError, IndexError):
                        pass
                elif line.startswith("signal:"):
                    parts = line.split()
                    for p in parts:
                        try:
                            info["signal_dbm"] = float(p.replace("dBm", ""))
                            break
                        except ValueError:
                            continue
                elif line.startswith("tx bitrate:"):
                    info["tx_bitrate"] = line.split(":", 1)[1].strip()

        # Get IP from ip addr
        try:
            r = subprocess.run(
                ["ip", "-4", "addr", "show", name],
                capture_output=True, text=True, timeout=5,
            )
            for line in r.stdout.split("\n"):
                if "inet " in line:
                    parts = line.strip().split()
                    info["ip"] = parts[1] if len(parts) > 1 else ""
                    break
        except Exception:
            pass

        results.append(info)

    return {
        "available": True,
        "count": len(results),
        "interfaces": results,
    }


@router.post("/connect")
async def wifi_connect(body: WiFiConnectRequest, interface: str = "wlan0", auth=Depends(require_auth)):
    """Connect to a WiFi network using wpa_supplicant."""
    # Generate wpa_supplicant config
    if body.password:
        # Use wpa_passphrase to generate PSK
        try:
            r = subprocess.run(
                ["wpa_passphrase", body.ssid, body.password],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode != 0:
                raise HTTPException(status_code=400, detail="Invalid SSID or password")
            wpa_config = r.stdout
            # Ensure network block has scan_ssid=1 for hidden networks
            if body.hidden:
                wpa_config = wpa_config.replace(
                    "}",
                    "\tscan_ssid=1\n}",
                )
        except FileNotFoundError:
            raise HTTPException(status_code=400, detail="wpa_passphrase not available")
    else:
        # Open network
        wpa_config = f"""network={{
    ssid="{body.ssid}"
    key_mgmt=NONE
}}"""

    # Write config to /etc/wpa_supplicant/
    config_path = Path(f"/etc/wpa_supplicant/wpa_supplicant-{interface}.conf")
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(wpa_config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write config: {e}")

    # Restart wpa_supplicant for this interface
    try:
        subprocess.run(
            ["wpa_supplicant", "-B", "-i", interface, "-c", str(config_path)],
            capture_output=True, text=True, timeout=10,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start wpa_supplicant: {e}")

    # Get IP via DHCP
    try:
        subprocess.run(
            ["dhclient", "-v", interface],
            capture_output=True, text=True, timeout=30,
        )
    except Exception:
        pass

    return {"success": True, "message": f"Connected to {body.ssid}", "interface": interface}


@router.post("/disconnect")
async def wifi_disconnect(interface: str = "wlan0", auth=Depends(require_auth)):
    """Disconnect from WiFi network."""
    try:
        subprocess.run(
            ["wpa_cli", "-i", interface, "terminate"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        pass
    try:
        subprocess.run(
            ["dhclient", "-r", interface],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        pass
    return {"success": True, "message": f"Disconnected {interface}"}


@router.get("/driver-capabilities")
async def wifi_driver_capabilities(interface: str = "wlan0", auth=Depends(require_auth)):
    """Check if interface supports AP mode, monitor mode, etc."""
    result = _run_iw_command(["dev", interface, "info"])
    caps = {
        "interface": interface,
        "support_ap": False,
        "support_monitor": False,
        "support_ibss": False,
        "channels_2ghz": [],
        "channels_5ghz": [],
    }

    if result["success"]:
        for line in result["stdout"].split("\n"):
            if "Supported interface modes" in line:
                pass
            elif "* AP" in line:
                caps["support_ap"] = True
            elif "* monitor" in line:
                caps["support_monitor"] = True
            elif "* IBSS" in line:
                caps["support_ibss"] = True

    # Get channel info from iw list
    # (This is verbose but useful)
    return caps
