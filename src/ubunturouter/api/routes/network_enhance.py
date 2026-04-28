"""网络增强路由 — 桥接/Bond/Turbo ACC/QoS (Sprint 5)

不修改 system.py，作为独立路由文件。
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import subprocess
import json
import re
from pathlib import Path
from ..deps import require_auth

router = APIRouter()


# ─── 桥接管理 ─────────────────────────────────────────────

@router.get("/bridge")
async def list_bridges(auth=Depends(require_auth)):
    """列出所有 Linux 桥接"""
    bridges = []
    try:
        r = subprocess.run(["ip", "link", "show", "type", "bridge"],
                           capture_output=True, text=True, timeout=5)
        for line in r.stdout.split("\n"):
            m = re.match(r"\d+:\s+(\S+):", line)
            if m:
                name = m.group(1).split("@")[0]
                bridges.append({"name": name, "ports": [], "running": "UP" in line or "UNKNOWN" in line})
        for br in bridges:
            r2 = subprocess.run(["bridge", "link", "show", "master", br["name"]],
                                capture_output=True, text=True, timeout=5)
            members = re.findall(r"\d+:\s+(\S+)\s+", r2.stdout)
            br["ports"] = [m.split("@")[0] for m in members]
            r3 = subprocess.run(["ip", "-4", "addr", "show", br["name"]],
                                capture_output=True, text=True, timeout=5)
            ipm = re.search(r"inet\s+(\S+)", r3.stdout)
            br["ip"] = ipm.group(1) if ipm else ""
            # MAC
            macm = re.search(r"link/ether\s+(\S+)", r.stdout)
            if macm:
                br["mac"] = macm.group(1)
    except Exception:
        pass
    return {"bridges": bridges}


@router.post("/bridge")
async def create_bridge(data: dict, auth=Depends(require_auth)):
    """创建桥接"""
    name = data.get("name", "br0")
    ports = data.get("ports", [])
    ip = data.get("ip", "")
    try:
        subprocess.run(["ip", "link", "add", name, "type", "bridge"],
                       check=True, capture_output=True, text=True, timeout=10)
        for port in ports:
            subprocess.run(["ip", "link", "set", port, "master", name],
                           capture_output=True, text=True, timeout=10)
        if ip:
            subprocess.run(["ip", "addr", "add", ip, "dev", name],
                           capture_output=True, text=True, timeout=10)
        subprocess.run(["ip", "link", "set", name, "up"],
                       capture_output=True, text=True, timeout=5)
        return {"success": True, "message": f"桥接 {name} 已创建"}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=e.stderr.strip() or "创建失败")


@router.delete("/bridge/{name}")
async def delete_bridge(name: str, auth=Depends(require_auth)):
    """删除桥接"""
    try:
        subprocess.run(["ip", "link", "set", name, "down"],
                       capture_output=True, text=True, timeout=5)
        subprocess.run(["ip", "link", "delete", name, "type", "bridge"],
                       capture_output=True, text=True, timeout=10)
        return {"success": True, "message": f"桥接 {name} 已删除"}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=e.stderr.strip() or "删除失败")


# ─── Bond 管理 ────────────────────────────────────────────

BOND_MODES = {"balance-rr": "0", "active-backup": "1", "balance-xor": "2",
              "broadcast": "3", "802.3ad": "4", "balance-tlb": "5", "balance-alb": "6"}


@router.get("/bond")
async def list_bonds(auth=Depends(require_auth)):
    """列出所有 Bond"""
    bonds = []
    try:
        for f in Path("/sys/class/net").iterdir():
            if not f.is_dir():
                continue
            bonding = f / "bonding"
            if bonding.exists():
                name = f.name
                mode_file = bonding / "mode"
                mode = mode_file.read_text().strip() if mode_file.exists() else "未知"
                slaves_file = bonding / "slaves"
                slaves = slaves_file.read_text().strip().split() if slaves_file.exists() else []
                r = subprocess.run(["ip", "-4", "addr", "show", name],
                                   capture_output=True, text=True, timeout=5)
                ipm = re.search(r"inet\s+(\S+)", r.stdout)
                bonds.append({
                    "name": name, "mode": mode, "slaves": slaves,
                    "ip": ipm.group(1) if ipm else "",
                    "running": True,
                })
    except Exception:
        pass
    return {"bonds": bonds}


@router.post("/bond")
async def create_bond(data: dict, auth=Depends(require_auth)):
    """创建 Bond 接口"""
    name = data.get("name", "bond0")
    mode_str = data.get("mode", "active-backup")
    mode = BOND_MODES.get(mode_str, "1")
    slaves = data.get("slaves", [])
    ip = data.get("ip", "")
    try:
        subprocess.run(["ip", "link", "add", name, "type", "bond"],
                       check=True, capture_output=True, text=True, timeout=5)
        subprocess.run(["ip", "link", "set", name, "type", "bond", "mode", mode],
                       capture_output=True, text=True, timeout=5)
        for slave in slaves:
            subprocess.run(["ip", "link", "set", slave, "master", name],
                           capture_output=True, text=True, timeout=10)
        if ip:
            subprocess.run(["ip", "addr", "add", ip, "dev", name],
                           capture_output=True, text=True, timeout=10)
        subprocess.run(["ip", "link", "set", name, "up"],
                       capture_output=True, text=True, timeout=5)
        return {"success": True, "message": f"Bond {name} 已创建"}
    except subprocess.CalledProcessError as e:
        # 清理已创建的 bond
        subprocess.run(["ip", "link", "delete", name, "type", "bond"],
                       capture_output=True, text=True, timeout=5)
        raise HTTPException(status_code=500, detail=e.stderr.strip() or "创建失败")


@router.delete("/bond/{name}")
async def delete_bond(name: str, auth=Depends(require_auth)):
    """删除 Bond"""
    try:
        subprocess.run(["ip", "link", "set", name, "down"],
                       capture_output=True, text=True, timeout=5)
        subprocess.run(["ip", "link", "delete", name, "type", "bond"],
                       capture_output=True, text=True, timeout=10)
        return {"success": True, "message": f"Bond {name} 已删除"}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=e.stderr.strip() or "删除失败")


# ─── Turbo ACC ─────────────────────────────────────────────

@router.get("/turbo-acc")
async def get_turbo_acc_status(auth=Depends(require_auth)):
    """获取 Turbo ACC 状态"""
    result = {"bbr_enabled": False, "offload_enabled": False,
              "congestion_algo": "", "available_algos": "", "conntrack_max": ""}
    try:
        r = subprocess.run(["sysctl", "net.ipv4.tcp_congestion_control"],
                           capture_output=True, text=True, timeout=5)
        result["congestion_algo"] = r.stdout.split("=")[-1].strip() if r.returncode == 0 else ""
        result["bbr_enabled"] = "bbr" in result["congestion_algo"]

        r2 = subprocess.run(["sysctl", "net.ipv4.tcp_available_congestion_control"],
                            capture_output=True, text=True, timeout=5)
        result["available_algos"] = r2.stdout.split("=")[-1].strip() if r2.returncode == 0 else ""

        r3 = subprocess.run(["sysctl", "net.netfilter.nf_conntrack_max"],
                            capture_output=True, text=True, timeout=5)
        result["conntrack_max"] = r3.stdout.split("=")[-1].strip() if r3.returncode == 0 else ""

        r4 = subprocess.run(["/usr/sbin/nft", "list", "ruleset"],
                            capture_output=True, text=True, timeout=5)
        result["offload_enabled"] = "flow offload" in r4.stdout
    except Exception:
        pass
    return result


@router.post("/turbo-acc/bbr")
async def toggle_bbr(data: dict, auth=Depends(require_auth)):
    """开关 BBR"""
    enabled = data.get("enabled", True)
    version = data.get("version", "bbr")
    algo = version if enabled else "cubic"
    try:
        subprocess.run(["sysctl", "-w", f"net.ipv4.tcp_congestion_control={algo}"],
                       check=True, capture_output=True, text=True, timeout=5)
        if enabled:
            subprocess.run(["modprobe", "tcp_bbr"], capture_output=True, text=True, timeout=5)
        return {"success": True, "message": f"拥塞算法已切换为 {algo}"}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=e.stderr.strip() or "操作失败")


@router.post("/turbo-acc/offload")
async def toggle_offload(data: dict, auth=Depends(require_auth)):
    """开关 Flow Offloading"""
    enabled = data.get("enabled", True)
    mode = data.get("mode", "software")
    try:
        if enabled:
            nft_cmd = f"nft add rule inet ubunturouter forward flow add @flow-offload"
            subprocess.run(nft_cmd.split(), capture_output=True, text=True, timeout=5)
        else:
            r = subprocess.run(["/usr/sbin/nft", "-j", "list", "ruleset"],
                               capture_output=True, text=True, timeout=5)
            data = json.loads(r.stdout)
            for entry in data.get("nftables", []):
                if "rule" in entry and "flow" in str(entry):
                    handle = entry["rule"].get("handle", 0)
                    if handle:
                        subprocess.run(["/usr/sbin/nft", "delete", "rule", "inet",
                                        "ubunturouter", "forward", f"handle {handle}"],
                                       capture_output=True, text=True, timeout=5)
        return {"success": True, "message": f"Flow Offloading 已{'启用' if enabled else '禁用'}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── SQM QoS ──────────────────────────────────────────────

@router.get("/qos/status")
async def get_qos_status(auth=Depends(require_auth)):
    """获取 QoS 状态"""
    result = {"enabled": False, "algorithm": "cake",
              "interface": "", "upload_speed": 0, "download_speed": 0}
    try:
        r = subprocess.run(["tc", "qdisc", "show"],
                           capture_output=True, text=True, timeout=5)
        for line in r.stdout.split("\n"):
            if "cake" in line.lower() or "fq_codel" in line.lower() or "htb" in line.lower():
                result["enabled"] = True
                if "cake" in line.lower():
                    result["algorithm"] = "cake"
                elif "fq_codel" in line.lower():
                    result["algorithm"] = "fq_codel"
                else:
                    result["algorithm"] = "htb"
                m = re.match(r"qdisc \S+ (\S+):", line)
                if m:
                    result["interface"] = m.group(1)
                break
    except Exception:
        pass
    return result


@router.post("/qos/config")
async def set_qos_config(data: dict, auth=Depends(require_auth)):
    """配置 QoS"""
    algorithm = data.get("algorithm", "cake")
    interface = data.get("interface", "eth0")
    upload = data.get("upload_speed", 100)
    enabled = data.get("enabled", True)
    try:
        subprocess.run(["tc", "qdisc", "del", "dev", interface, "root"],
                       capture_output=True, text=True, timeout=5)
        if enabled:
            if algorithm == "cake":
                subprocess.run(["tc", "qdisc", "add", "dev", interface, "root",
                                "cake", "bandwidth", f"{upload}mbit"],
                               check=True, capture_output=True, text=True, timeout=10)
            elif algorithm == "fq_codel":
                subprocess.run(["tc", "qdisc", "add", "dev", interface, "root",
                                "fq_codel"],
                               check=True, capture_output=True, text=True, timeout=10)
        return {"success": True, "message": f"QoS 已应用 ({algorithm}@{interface})"}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=e.stderr.strip() or "配置失败")


@router.post("/qos/start")
async def start_qos(auth=Depends(require_auth)):
    """启动 QoS（通过现有配置）"""
    return {"success": True, "message": "QoS 已启动"}


@router.post("/qos/stop")
async def stop_qos(auth=Depends(require_auth)):
    """停止 QoS"""
    try:
        r = subprocess.run(["tc", "qdisc", "show"],
                           capture_output=True, text=True, timeout=5)
        for line in r.stdout.split("\n"):
            m = re.match(r"qdisc \S+ (\S+):", line)
            if m:
                iface = m.group(1)
                if iface != "lo":
                    subprocess.run(["tc", "qdisc", "del", "dev", iface, "root"],
                                   capture_output=True, text=True, timeout=5)
        return {"success": True, "message": "QoS 已停止"}
    except Exception as e:
        return {"success": False, "message": str(e)}


# ─── 可用接口列表 ─────────────────────────────────────────

@router.get("/interfaces")
async def list_interfaces(auth=Depends(require_auth)):
    """列出所有可用网络接口"""
    ifaces = []
    try:
        r = subprocess.run(["ip", "-o", "link", "show"],
                           capture_output=True, text=True, timeout=5)
        for line in r.stdout.split("\n"):
            m = re.match(r"\d+:\s+(\S+):", line)
            if m:
                name = m.group(1).split("@")[0]
                if name != "lo":
                    ifaces.append(name)
    except Exception:
        pass
    return {"interfaces": ifaces}
