"""语音助手 API — 统一状态查询 + 各平台 Webhook

支持:
- Google Assistant (Dialogflow Fulfillment Webhook)
- Amazon Alexa (Alexa Skills Kit)
- Apple Siri (Shortcuts URL)
- Home Assistant (REST API)
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Dict
import subprocess
import json
import time
from ..deps import require_auth

router = APIRouter()


# ─── 统一状态查询 ─────────────────────────────────────────

def _get_system_summary() -> Dict:
    """获取系统状态摘要（语音友好格式）"""
    result = {
        "system": {"cpu": 0, "memory": 0, "uptime": "0s"},
        "network": {"wan_ip": "", "devices": 0},
        "traffic": {"upload": "0bps", "download": "0bps"},
        "services": {},
    }

    # CPU / 内存
    try:
        cpu = subprocess.run(
            ["top", "-bn1", "|", "grep", "'Cpu(s)'", "|", "awk", "'{print $2}'"],
            capture_output=True, text=True, timeout=5, shell=True
        )
        if cpu.returncode == 0 and cpu.stdout.strip():
            result["system"]["cpu"] = float(cpu.stdout.strip().split(",")[0].split("%")[0])

        mem = subprocess.run(
            ["free", "-m"],
            capture_output=True, text=True, timeout=5
        )
        for line in mem.stdout.split("\n"):
            if line.startswith("Mem:"):
                parts = line.split()
                if len(parts) >= 3:
                    total = int(parts[1])
                    used = int(parts[2])
                    result["system"]["memory"] = round(used / total * 100, 1)
                break
    except Exception:
        pass

    # 运行时间
    try:
        upt = subprocess.run(["uptime", "-p"], capture_output=True, text=True, timeout=5)
        result["system"]["uptime"] = upt.stdout.strip() if upt.returncode == 0 else "0s"
    except Exception:
        pass

    # WAN IP
    try:
        r = subprocess.run(["ip", "-4", "addr", "show"],
                           capture_output=True, text=True, timeout=5)
        for line in r.stdout.split("\n"):
            if "inet " in line and "127.0.0." not in line:
                parts = line.strip().split()
                if len(parts) >= 2:
                    result["network"]["wan_ip"] = parts[1].split("/")[0]
                    break
    except Exception:
        pass

    # 设备数 (ARP)
    try:
        r = subprocess.run(["arp", "-n"], capture_output=True, text=True, timeout=5)
        result["network"]["devices"] = len([l for l in r.stdout.split("\n") if "incomplete" not in l and l.strip()]) - 1
        if result["network"]["devices"] < 0:
            result["network"]["devices"] = 0
    except Exception:
        pass

    # 流量
    try:
        r = subprocess.run(["cat", "/proc/net/dev"],
                           capture_output=True, text=True, timeout=5)
        rx_total, tx_total = 0, 0
        for line in r.stdout.split("\n"):
            if ":" in line and "lo:" not in line:
                parts = line.strip().split()
                if len(parts) >= 10:
                    rx_total += int(parts[1])
                    tx_total += int(parts[9])

        def fmt_bps(b):
            if b < 1024: return f"{b}Bps"
            elif b < 1024**2: return f"{b/1024:.1f}KBps"
            elif b < 1024**3: return f"{b/1024**2:.1f}MBps"
            else: return f"{b/1024**3:.1f}GBps"

        result["traffic"]["download"] = fmt_bps(rx_total)
        result["traffic"]["upload"] = fmt_bps(tx_total)
    except Exception:
        pass

    # 服务状态
    services = ["docker", "ssh", "nginx", "ubunturouter"]
    for svc in services:
        try:
            r = subprocess.run(["systemctl", "is-active", svc],
                               capture_output=True, text=True, timeout=5)
            result["services"][svc] = r.stdout.strip() if r.returncode == 0 else "inactive"
        except Exception:
            result["services"][svc] = "unknown"

    # 语音摘要
    summary_parts = []
    summary_parts.append(f"路由器运行正常。CPU使用率{result['system']['cpu']}%，"
                         f"内存使用率{result['system']['memory']}%，"
                         f"已运行{result['system']['uptime']}。")
    summary_parts.append(f"连接设备{result['network']['devices']}台，"
                         f"WAN口IP {result['network']['wan_ip']}。")
    summary_parts.append(f"当前下行{result['traffic']['download']}，"
                         f"上行{result['traffic']['upload']}。")

    active_services = [k for k, v in result["services"].items() if v == "active"]
    if active_services:
        summary_parts.append(f"运行中的服务：{'、'.join(active_services)}。")

    result["summary"] = " ".join(summary_parts)

    return result


# ─── 统一状态查询 API ─────────────────────────────────────

@router.get("/status")
async def get_voice_status(auth=Depends(require_auth)):
    """获取路由器状态摘要（语音友好）"""
    return _get_system_summary()


@router.get("/status/{module}")
async def get_voice_module_status(module: str, auth=Depends(require_auth)):
    """获取特定模块状态"""
    full = _get_system_summary()
    if module in full:
        return full[module]
    if module in full.get("services", {}):
        return {"name": module, "status": full["services"][module]}
    raise HTTPException(status_code=404, detail=f"未知模块: {module}")


# ─── Google Assistant / Dialogflow Webhook ────────────────

@router.post("/google")
async def google_assistant_webhook(request: Request, auth=Depends(require_auth)):
    """Google Assistant Dialogflow Fulfillment Webhook

    支持意图:
      - get_router_status — 获取路由器整体状态
      - get_traffic — 流量信息
      - get_device_count — 设备数量
      - get_service_status — 服务状态
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="无效的请求体")

    intent = ""
    params = {}
    if "queryResult" in body:
        intent = body["queryResult"].get("intent", {}).get("displayName", "")
        params = body["queryResult"].get("parameters", {})
    elif "originalDetectIntentRequest" in body:
        intent = body.get("session", "")

    status = _get_system_summary()

    # 处理意图
    if "status" in intent.lower() and "router" in intent.lower():
        speech = status["summary"]
    elif "traffic" in intent.lower():
        speech = f"当前下行{status['traffic']['download']}，上行{status['traffic']['upload']}"
    elif "device" in intent.lower():
        speech = f"当前有{status['network']['devices']}台设备连接到路由器"
    elif "service" in intent.lower():
        svc_name = params.get("service_name", "")
        if svc_name and svc_name in status["services"]:
            svc_status = status["services"][svc_name]
            speech = f"{svc_name}服务{svc_status}"
        else:
            active = [k for k, v in status["services"].items() if v == "active"]
            speech = f"运行中的服务有{'、'.join(active)}"
    else:
        speech = status["summary"]

    return {
        "fulfillmentText": speech,
        "fulfillmentMessages": [{"text": {"text": [speech]}}],
        "source": "ubuntu-router",
    }


# ─── Amazon Alexa Skill Endpoint ─────────────────────────

@router.post("/alexa")
async def alexa_skill_endpoint(request: Request, auth=Depends(require_auth)):
    """Amazon Alexa Skills Kit 端点

    支持意图:
      - GetRouterStatus
      - GetTraffic
      - GetDevices
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="无效的请求体")

    request_type = body.get("request", {}).get("type", "")
    intent_name = body.get("request", {}).get("intent", {}).get("name", "")
    status = _get_system_summary()

    if request_type == "LaunchRequest":
        speech = status["summary"]
    elif intent_name == "GetRouterStatus":
        speech = status["summary"]
    elif intent_name == "GetTraffic":
        speech = f"当前下行{status['traffic']['download']}，上行{status['traffic']['upload']}"
    elif intent_name == "GetDevices":
        speech = f"当前有{status['network']['devices']}台设备连接"
    else:
        speech = status["summary"]

    return {
        "version": "1.0",
        "response": {
            "outputSpeech": {"type": "PlainText", "text": speech},
            "shouldEndSession": True,
        },
    }


# ─── Apple Siri Shortcuts ─────────────────────────────────

@router.get("/siri")
async def siri_shortcuts(auth=Depends(require_auth)):
    """Apple Siri Shortcuts 查询端点

    通过 iOS Shortcuts App 配置 GET 请求获取状态
    """
    status = _get_system_summary()
    return {
        "speech": status["summary"],
        "status": status,
    }


# ─── Home Assistant 状态查询 ─────────────────────────────

@router.get("/home-assistant")
async def home_assistant_sensors(auth=Depends(require_auth)):
    """Home Assistant 传感器状态 — 适用于 RESTful Sensor 配置"""
    status = _get_system_summary()
    return {
        "state": "running",
        "attributes": {
            "cpu_percent": status["system"]["cpu"],
            "memory_percent": status["system"]["memory"],
            "uptime": status["system"]["uptime"],
            "wan_ip": status["network"]["wan_ip"],
            "devices": status["network"]["devices"],
            "upload_speed": status["traffic"]["upload"],
            "download_speed": status["traffic"]["download"],
            "friendly_name": "UbuntuRouter",
            "unit_of_measurement": "",
        },
    }


# ─── Home Assistant 配置模板 ─────────────────────────────

@router.get("/home-assistant/config")
async def home_assistant_config(auth=Depends(require_auth)):
    """Home Assistant 配置示例 — YAML 片段"""
    config = """
# UbuntuRouter 传感器配置
sensor:
  - platform: rest
    name: ubunturouter_status
    resource: "http://YOUR_ROUTER_IP:8080/api/v1/voice/home-assistant"
    method: GET
    headers:
      Authorization: "Bearer YOUR_API_TOKEN"
    value_template: "{{ value_json.state }}"
    scan_interval: 30
    json_attributes:
      - cpu_percent
      - memory_percent
      - uptime
      - wan_ip
      - devices
      - upload_speed
      - download_speed
"""
    return {"config": config.strip()}
