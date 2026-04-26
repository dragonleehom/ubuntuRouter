"""Dashboard WebSocket — 实时推送系统状态与流量数据"""

import asyncio
import json
import time
import subprocess
from pathlib import Path
from fastapi import WebSocket, WebSocketDisconnect


class TrafficCollector:
    """网络流量采集器 — 读取 /proc/net/dev"""

    def __init__(self):
        self._last: dict[str, dict] = {}

    def _read_stats(self) -> dict[str, dict]:
        """读取当前接口流量统计"""
        data = {}
        try:
            content = Path("/proc/net/dev").read_text()
            for line in content.split("\n")[2:]:
                if not line.strip():
                    continue
                parts = line.split()
                iface = parts[0].rstrip(":")
                if iface == "lo":
                    continue
                data[iface] = {
                    "rx_bytes": int(parts[1]),
                    "tx_bytes": int(parts[9]),
                    "rx_packets": int(parts[2]),
                    "tx_packets": int(parts[10]),
                }
        except Exception:
            pass
        return data

    def get_rates(self) -> dict[str, dict]:
        """获取每秒速率（需要两次读取间隔1s）"""
        now1 = time.time()
        s1 = self._read_stats()
        time.sleep(1)
        now2 = time.time()
        s2 = self._read_stats()
        delta = now2 - now1 if now2 > now1 else 1

        result = {}
        for iface in s2:
            if iface not in s1:
                continue
            r1, r2 = s1[iface], s2[iface]
            result[iface] = {
                "rx_bps": round((r2["rx_bytes"] - r1["rx_bytes"]) / delta),
                "tx_bps": round((r2["tx_bytes"] - r1["tx_bytes"]) / delta),
                "rx_pps": round((r2["rx_packets"] - r1["rx_packets"]) / delta),
                "tx_pps": round((r2["tx_packets"] - r1["tx_packets"]) / delta),
                "rx_bytes": r2["rx_bytes"],
                "tx_bytes": r2["tx_bytes"],
            }
        return result


def get_cpu_percent() -> float:
    """获取 CPU 使用率"""
    try:
        r = subprocess.run(
            ["sh", "-c", "top -bn1 | grep 'Cpu(s)' | awk '{print $2+$4}'"],
            capture_output=True, text=True, timeout=3
        )
        return float(r.stdout.strip() or 0)
    except Exception:
        return 0.0


def get_memory_info() -> dict:
    """获取内存信息"""
    try:
        r = subprocess.run(
            ["sh", "-c", "free -m | awk '/Mem:/ {print $3, $2}'"],
            capture_output=True, text=True, timeout=3
        )
        parts = r.stdout.strip().split()
        if len(parts) == 2:
            return {"used_mb": int(parts[0]), "total_mb": int(parts[1])}
    except Exception:
        pass
    return {"used_mb": 0, "total_mb": 0}


class DashboardWSManager:
    """Dashboard WebSocket 连接管理器"""

    def __init__(self):
        self._connections: set[WebSocket] = set()
        self._collector = TrafficCollector()
        self._running = False

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.add(ws)

    def disconnect(self, ws: WebSocket):
        self._connections.discard(ws)

    async def broadcast(self, message: dict):
        dead = set()
        for ws in self._connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._connections.discard(ws)

    async def start_pushing(self):
        """开始定时推送流量和系统数据"""
        if self._running:
            return
        self._running = True

        while self._running:
            if not self._connections:
                await asyncio.sleep(2)
                continue

            # 流量速率
            rates = self._collector.get_rates()

            # 系统数据
            cpu = get_cpu_percent()
            mem = get_memory_info()

            await self.broadcast({
                "type": "traffic",
                "timestamp": time.time(),
                "traffic": rates,
                "system": {
                    "cpu_percent": cpu,
                    "memory": mem,
                }
            })

            # 每 2 秒推送一次
            await asyncio.sleep(2)


manager = DashboardWSManager()


async def websocket_endpoint(ws: WebSocket):
    """WebSocket 端点 — 推送实时数据"""
    # JWT 认证
    try:
        await ws.accept()
        data = await asyncio.wait_for(ws.receive_text(), timeout=5)
        token_data = json.loads(data)
        token = token_data.get("token", "")
    except Exception:
        await ws.close(code=4001, reason="认证失败")
        return

    from ..auth.jwt import verify_token
    payload = verify_token(token)
    if not payload:
        await ws.close(code=4001, reason="Token 失效")
        return

    await manager.connect(ws)

    # 启动推送（如果还没启动）
    asyncio.ensure_future(manager.start_pushing())

    try:
        while True:
            try:
                msg = await asyncio.wait_for(ws.receive_text(), timeout=30)
                if msg == "ping":
                    await ws.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                # 超时正常——保持连接
                await ws.send_json({"type": "keepalive"})
            except WebSocketDisconnect:
                break
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ws)
