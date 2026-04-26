"""WebSocket 实时推送"""

import asyncio
import json
import time
from fastapi import WebSocket, WebSocketDisconnect
from ..deps import require_auth


class DashboardWSManager:
    """Dashboard WebSocket 连接管理器"""

    def __init__(self):
        self._connections: set[WebSocket] = set()

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


manager = DashboardWSManager()


async def websocket_endpoint(ws: WebSocket):
    """WebSocket 端点 — 实时推送 Dashboard 数据"""
    # 先认证：客户端发送第一个消息必须是 JWT token
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

    try:
        while True:
            # 接收客户端消息（用于心跳）
            try:
                msg = await asyncio.wait_for(ws.receive_text(), timeout=10)
                if msg == "ping":
                    await ws.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                break
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ws)
