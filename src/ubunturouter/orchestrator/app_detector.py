"""DNS 应用识别 — 接收流量/DNS 查询，识别匹配的应用"""
import logging
from typing import List, Optional

from .app_db import AppDB, App

logger = logging.getLogger("ubunturouter.orchestrator.detector")


class AppDetector:
    """应用检测器

    通过 DNS 查询或网络流量的五元组信息识别匹配的应用。
    """

    def __init__(self, app_db: Optional[AppDB] = None):
        self._app_db = app_db or AppDB()

    # ─── 公共方法 ──────────────────────────────────────────────

    def analyze_dns(self, domain: str) -> Optional[App]:
        """分析 DNS 查询域名，返回匹配的应用

        Args:
            domain: DNS 查询域名 (如 www.youtube.com)

        Returns:
            匹配的 App 对象，未匹配返回 None
        """
        if not domain:
            return None
        app = self._app_db.match_by_domain(domain)
        if app:
            logger.debug("DNS match: %s -> %s", domain, app.name)
        else:
            logger.debug("DNS no match: %s", domain)
        return app

    def analyze_flow(
        self,
        src_ip: str,
        dst_ip: str,
        dst_port: int,
        protocol: str = "tcp",
    ) -> List[App]:
        """分析网络流量，返回匹配的应用列表

        Args:
            src_ip: 源 IP
            dst_ip: 目标 IP
            dst_port: 目标端口
            protocol: 协议 (tcp/udp)

        Returns:
            匹配的 App 对象列表（可能匹配多个）
        """
        matched: List[App] = []

        # 1. 按 IP 匹配
        app_by_ip = self._app_db.match_by_ip(dst_ip)
        if app_by_ip:
            matched.append(app_by_ip)

        # 2. 按协议匹配
        proto_key = f"{protocol}/{dst_port}"
        for app in self._app_db.get_all():
            for proto_def in app.protocols:
                if self._protocol_match(proto_key, proto_def):
                    if app not in matched:
                        matched.append(app)
                    break

        if matched:
            names = ", ".join(a.name for a in matched)
            logger.debug("Flow match %s -> %s:%s/%s: %s",
                         src_ip, dst_ip, dst_port, protocol, names)

        return matched

    # ─── 内部方法 ──────────────────────────────────────────────

    @staticmethod
    def _protocol_match(actual: str, pattern: str) -> bool:
        """检查实际协议是否匹配特征定义中的协议规则"""
        # 格式: tcp/443, udp/443, tcp/27015-27050
        try:
            actual_proto, actual_port_str = actual.split("/", 1)
            actual_port = int(actual_port_str)

            if "/" not in pattern:
                return False
            pattern_proto, pattern_port = pattern.split("/", 1)

            if actual_proto.lower() != pattern_proto.lower():
                return False

            # 端口范围匹配
            if "-" in pattern_port:
                lo, hi = pattern_port.split("-", 1)
                return int(lo) <= actual_port <= int(hi)
            else:
                return int(pattern_port) == actual_port
        except (ValueError, IndexError):
            return False
