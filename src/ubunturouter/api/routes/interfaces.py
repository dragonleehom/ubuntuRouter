"""接口 API: list / detect / status"""

import subprocess
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException

from ..deps import require_auth
from ...engine.engine import ConfigEngine
from ...engine.initializer import Initializer


router = APIRouter()


@router.get("/list")
async def list_interfaces(auth=Depends(require_auth)):
    """列出所有网络接口"""
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
            speed_file = Path(f"/sys/class/net/{name}/speed")
            speed = None
            if speed_file.exists():
                try:
                    speed = int(speed_file.read_text().strip())
                except Exception:
                    pass
            ifaces.append({
                "name": name,
                "mac": link.get("address", ""),
                "state": link.get("operstate", "unknown"),
                "mtu": link.get("mtu", 1500),
                "ipv4": addr_map.get(name, []),
                "speed": speed,
                "type": "physical" if Path(f"/sys/class/net/{name}/device").exists() else "virtual",
            })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"interfaces": ifaces}


@router.get("/detect")
async def detect_interfaces(auth=Depends(require_auth)):
    """检测并分配角色（预览，不 Apply）"""
    engine = ConfigEngine()
    init = Initializer(engine)
    nics = init.detect_physical_nics()
    assignment = init.auto_assign_roles(nics)
    config = init.generate_initial_config(assignment)

    return {
        "nics": [{"name": n.name, "speed": n.speed, "link": n.link, "driver": n.driver} for n in nics],
        "assignment": {
            "mode": "wanlan" if assignment.wanlan else "normal",
            "wan": assignment.wan.name if assignment.wan else None,
            "wanlan": assignment.wanlan.name if assignment.wanlan else None,
            "lans": [l.name for l in assignment.lans],
        },
        "config_preview": {
            "interfaces": [{"name": i.name, "role": i.role.value, "device": i.device} for i in config.interfaces],
            "dhcp": {"range": f"{config.dhcp.range_start} - {config.dhcp.range_end}"} if config.dhcp else None,
        }
    }


@router.get("/status/{ifname}")
async def interface_status(ifname: str, auth=Depends(require_auth)):
    """获取单个接口状态"""
    try:
        r = subprocess.run(
            ["ip", "-j", "link", "show", ifname],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode != 0:
            raise HTTPException(status_code=404, detail=f"接口 {ifname} 不存在")

        links = json.loads(r.stdout)
        if not links:
            raise HTTPException(status_code=404, detail=f"接口 {ifname} 不存在")

        link = links[0]

        # 统计信息
        stats_file = Path(f"/sys/class/net/{ifname}/statistics")
        stats = {}
        if stats_file.exists():
            for name in ["rx_bytes", "rx_packets", "tx_bytes", "tx_packets", "rx_errors", "tx_errors"]:
                f = stats_file / name
                if f.exists():
                    try:
                        stats[name] = int(f.read_text().strip())
                    except Exception:
                        pass

        return {
            "name": ifname,
            "mac": link.get("address", ""),
            "state": link.get("operstate", ""),
            "mtu": link.get("mtu", 1500),
            "statistics": stats,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── 接口配置修改 ─────────────────────────────────────────

from pydantic import BaseModel, Field

class InterfaceConfigModel(BaseModel):
    name: str
    ip: str = ""
    gateway: str = ""
    dhcp: bool = False


@router.post("/config")
async def configure_interface(cfg: InterfaceConfigModel, auth=Depends(require_auth)):
    """修改接口 IP 配置（写入 netplan 并 apply）"""
    try:
        # 使用 ip addr 临时配置（运行时生效）
        if cfg.ip:
            # 清除现有 IP
            subprocess.run(
                ["ip", "addr", "flush", "dev", cfg.name],
                capture_output=True, text=True, timeout=5
            )
            # 设置新 IP
            r = subprocess.run(
                ["ip", "addr", "add", cfg.ip, "dev", cfg.name],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode != 0:
                return {"success": False, "message": f"设置 IP 失败: {r.stderr.strip()}"}

        if cfg.gateway:
            # 更新默认路由
            subprocess.run(
                ["ip", "route", "replace", "default", "via", cfg.gateway, "dev", cfg.name],
                capture_output=True, text=True, timeout=5
            )

        return {"success": True, "message": f"接口 {cfg.name} 配置已更新"}
    except Exception as e:
        return {"success": False, "message": str(e)}
