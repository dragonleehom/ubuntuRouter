"""UPnP 端口转发 API — miniupnpd 配置管理"""

import subprocess
import re
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import require_auth


router = APIRouter()

UPNPD_CONFIG = Path("/etc/miniupnpd/miniupnpd.conf")


class UpnpRule(BaseModel):
    """UPnP 端口转发规则"""
    id: str = ""
    enabled: bool = True
    external_port: int = Field(..., ge=1, le=65535)
    internal_port: int = Field(..., ge=1, le=65535)
    protocol: str = Field("TCP", pattern="^(TCP|UDP|BOTH)$")
    internal_ip: str = Field(..., description="目标内网 IP")
    description: str = ""


class UpnpRuleCreate(BaseModel):
    """创建 UPnP 规则"""
    external_port: int = Field(..., ge=1, le=65535)
    internal_port: int = Field(..., ge=1, le=65535)
    protocol: str = Field("TCP", pattern="^(TCP|UDP|BOTH)$")
    internal_ip: str = Field(..., description="目标内网 IP")
    description: str = ""
    enabled: bool = True


def _get_status() -> dict:
    """获取 miniupnpd 服务状态"""
    r = subprocess.run(
        ["systemctl", "is-active", "miniupnpd"],
        capture_output=True, text=True, timeout=5,
    )
    running = r.stdout.strip() == "active"
    r2 = subprocess.run(
        ["systemctl", "is-enabled", "miniupnpd"],
        capture_output=True, text=True, timeout=5,
    )
    enabled = r2.stdout.strip() == "enabled"
    return {"running": running, "enabled": enabled}


def _read_rules() -> List[dict]:
    """从 miniupnpd.conf 读取端口转发规则"""
    rules = []
    if not UPNPD_CONFIG.exists():
        return rules
    try:
        content = UPNPD_CONFIG.read_text()
    except Exception:
        return rules

    # 解析 port_forwarding 规则
    # miniupnpd.conf 格式: 52134:192.168.1.100:80  # description
    for i, line in enumerate(content.split("\n")):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("ext_ifname") or \
           line.startswith("listening_ip") or line.startswith("port"):
            continue
        # 尝试匹配端口转发条目
        m = re.match(r"^(\d+):([\d.]+):(\d+)\s*(?:#\s*(.*))?$", line)
        if m:
            rules.append({
                "id": str(i),
                "external_port": int(m.group(1)),
                "internal_ip": m.group(2),
                "internal_port": int(m.group(3)),
                "description": m.group(4) or "",
                "enabled": True,
                "protocol": "TCP",
            })
    return rules


def _write_rules(rules: List[dict]):
    """写入 miniupnpd.conf（保留原 ext_ifname 等配置）"""
    if not UPNPD_CONFIG.exists():
        # 创建默认配置
        UPNPD_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        UPNPD_CONFIG.write_text("""ext_ifname=eth0
listening_ip=192.168.1.1
port=0
enable_natpmp=yes
enable_upnp=yes
system_uptime=yes
""")

    # 读取现有配置，保留 ext_ifname 等头部
    content = UPNPD_CONFIG.read_text()
    header_lines = []
    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            header_lines.append(line)
            continue
        # 如果行是端口转发格式则跳过
        if re.match(r"^\d+:[\d.]+:\d+", stripped):
            continue
        header_lines.append(line)

    # 生成新的转发规则
    rule_lines = []
    for r in rules:
        if not r.get("enabled", True):
            continue
        desc = f"  # {r['description']}" if r.get("description") else ""
        rule_lines.append(f"{r['external_port']}:{r['internal_ip']}:{r['internal_port']}{desc}")

    # 写入
    new_content = "\n".join(header_lines) + "\n"
    if rule_lines:
        new_content += "\n" + "\n".join(rule_lines) + "\n"
    UPNPD_CONFIG.write_text(new_content)


@router.get("/status")
async def get_upnp_status(auth=Depends(require_auth)):
    """获取 UPnP 服务状态"""
    return _get_status()


@router.post("/enable")
async def enable_upnp(auth=Depends(require_auth)):
    """启用 UPnP 服务"""
    try:
        subprocess.run(["systemctl", "enable", "miniupnpd"], capture_output=True, text=True, timeout=10)
        subprocess.run(["systemctl", "start", "miniupnpd"], capture_output=True, text=True, timeout=10)
        return {"success": True, "message": "UPnP 服务已启用"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启用 UPnP 失败: {e}")


@router.post("/disable")
async def disable_upnp(auth=Depends(require_auth)):
    """禁用 UPnP 服务"""
    try:
        subprocess.run(["systemctl", "stop", "miniupnpd"], capture_output=True, text=True, timeout=10)
        subprocess.run(["systemctl", "disable", "miniupnpd"], capture_output=True, text=True, timeout=10)
        return {"success": True, "message": "UPnP 服务已禁用"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"禁用 UPnP 失败: {e}")


@router.get("/rules")
async def list_rules(auth=Depends(require_auth)):
    """列出 UPnP 端口转发规则"""
    rules = _read_rules()
    return {"rules": rules, "count": len(rules)}


@router.post("/rules")
async def create_rule(rule: UpnpRuleCreate, auth=Depends(require_auth)):
    """创建端口转发规则"""
    rules = _read_rules()
    new_id = str(len(rules) + 1)
    rules.append({
        "id": new_id,
        "external_port": rule.external_port,
        "internal_port": rule.internal_port,
        "protocol": rule.protocol,
        "internal_ip": rule.internal_ip,
        "description": rule.description,
        "enabled": rule.enabled,
    })
    _write_rules(rules)
    # 重启服务以应用
    subprocess.run(["systemctl", "restart", "miniupnpd"], capture_output=True, text=True, timeout=10)
    return {"success": True, "message": "端口转发规则已创建", "id": new_id}


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str, auth=Depends(require_auth)):
    """删除端口转发规则"""
    rules = _read_rules()
    new_rules = [r for r in rules if r["id"] != rule_id]
    if len(new_rules) == len(rules):
        raise HTTPException(status_code=404, detail="规则未找到")
    _write_rules(new_rules)
    subprocess.run(["systemctl", "restart", "miniupnpd"], capture_output=True, text=True, timeout=10)
    return {"success": True, "message": "端口转发规则已删除"}
