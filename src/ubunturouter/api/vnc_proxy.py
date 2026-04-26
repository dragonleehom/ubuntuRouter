"""noVNC WebSocket 代理 — WebSocket -> TCP 转发 VM VNC 端口"""

import os
import re
import shutil
import subprocess
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

WEBSOCKIFY_CMD = "websockify"
PROXY_HOST = "127.0.0.1"
PROXY_PORT_START = 16000  # 代理端口起始


# ── VNCProxy ─────────────────────────────────────────────────────────────────

class VNCProxy:
    """noVNC WebSocket 代理管理。

    提供两种方式:
    1. websockify 外部命令 (优先)
    2. Python asyncio WebSocket->TCP 转发 (备选)
    """

    _proxies: dict = {}       # vm_name -> {"ws_url": str, "process": subprocess.Popen}
    _port_allocations: dict = {}  # vm_name -> proxy_port

    @classmethod
    def create_proxy(cls, vm_name: str, vnc_port: Optional[int] = None,
                     host: str = PROXY_HOST) -> dict:
        """为 VM 创建 noVNC WebSocket 代理。

        Args:
            vm_name: 虚拟机名称
            vnc_port: VNC TCP 端口 (如果为 None，尝试自动获取)
            host: 绑定地址

        Returns:
            字典: {"available": bool, "ws_url": str, "message": str}
        """
        # 检查是否已有代理
        if vm_name in cls._proxies:
            existing = cls._proxies[vm_name]
            return {
                "available": True,
                "ws_url": existing["ws_url"],
                "message": "代理已存在",
            }

        # 如果未指定 VNC 端口，尝试从 VirtManager 获取
        if vnc_port is None:
            try:
                from .libvirt_wrapper import VirtManager
                vnc_port = VirtManager.get_vnc_port(vm_name)
            except Exception:
                pass

        if vnc_port is None:
            return {
                "available": False,
                "ws_url": "",
                "message": f"无法获取 VM '{vm_name}' 的 VNC 端口",
            }

        # 分配代理端口
        proxy_port = cls._allocate_port()

        # 优先使用 websockify
        if shutil.which(WEBSOCKIFY_CMD):
            return cls._start_websockify(vm_name, vnc_port, proxy_port, host)
        else:
            # websockify 不可用，返回提示
            return {
                "available": False,
                "ws_url": "",
                "message": "websockify not installed. 请安装: pip install websockify 或 apt install websockify",
            }

    @classmethod
    def stop_proxy(cls, vm_name: str) -> bool:
        """停止指定 VM 的代理。"""
        proxy = cls._proxies.pop(vm_name, None)
        cls._port_allocations.pop(vm_name, None)
        if proxy and proxy.get("process"):
            try:
                proxy["process"].terminate()
                proxy["process"].wait(timeout=5)
            except Exception:
                try:
                    proxy["process"].kill()
                except Exception:
                    pass
            return True
        return False

    @classmethod
    def cleanup_all(cls):
        """清理所有代理。"""
        names = list(cls._proxies.keys())
        for name in names:
            cls.stop_proxy(name)

    # ── Internal ──────────────────────────────────────────────────────────

    @classmethod
    def _allocate_port(cls) -> int:
        """分配一个可用的代理端口。"""
        used = set(cls._port_allocations.values())
        port = PROXY_PORT_START
        while port in used:
            port += 1
        return port

    @classmethod
    def _start_websockify(cls, vm_name: str, vnc_port: int,
                          proxy_port: int, host: str) -> dict:
        """使用 websockify 命令启动 WebSocket 代理。"""
        try:
            target = f"{host}:{vnc_port}"
            listen = f"{host}:{proxy_port}"

            proc = subprocess.Popen(
                [WEBSOCKIFY_CMD, "--web", "/usr/share/novnc", listen, target],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            ws_url = f"ws://{host}:{proxy_port}/websockify"

            cls._proxies[vm_name] = {
                "ws_url": ws_url,
                "process": proc,
                "vnc_port": vnc_port,
                "proxy_port": proxy_port,
            }
            cls._port_allocations[vm_name] = proxy_port

            return {
                "available": True,
                "ws_url": ws_url,
                "vnc_port": vnc_port,
                "proxy_port": proxy_port,
                "message": f"代理已创建: {ws_url} -> {target}",
            }

        except Exception as e:
            logger.error(f"启动 websockify 失败: {e}")
            return {
                "available": False,
                "ws_url": "",
                "message": f"启动 websockify 失败: {str(e)}",
            }
