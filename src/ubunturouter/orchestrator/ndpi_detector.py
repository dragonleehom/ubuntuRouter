"""nDPI 兜底检测器 — 非 TLS 流量的协议特征分析

当 DNS 缓存和 TLS SNI 都无法识别时，使用 nDPI 对非 TLS
流量做深度包检测作为兜底方案。
"""
import logging
from typing import Optional

logger = logging.getLogger("ubunturouter.orchestrator.ndpi_detector")

# ─── 端口→协议推断（无 nDPI 时的回退）────────────────────
PORT_PROTOCOL_MAP = {
    # HTTP/HTTPS (TLS 已由 SNI 覆盖)
    80: ("tcp", "HTTP"),
    443: ("tcp", "HTTPS"),
    # DNS
    53: ("udp", "DNS"),
    853: ("tcp", "DoT"),
    # 邮件
    25: ("tcp", "SMTP"),
    465: ("tcp", "SMTPS"),
    587: ("tcp", "SMTP Submission"),
    110: ("tcp", "POP3"),
    995: ("tcp", "POP3S"),
    143: ("tcp", "IMAP"),
    993: ("tcp", "IMAPS"),
    # FTP
    20: ("tcp", "FTP-DATA"),
    21: ("tcp", "FTP"),
    990: ("tcp", "FTPS"),
    # SSH
    22: ("tcp", "SSH"),
    # Telnet
    23: ("tcp", "Telnet"),
    # DHCP
    67: ("udp", "DHCP Server"),
    68: ("udp", "DHCP Client"),
    # NTP
    123: ("udp", "NTP"),
    # SNMP
    161: ("udp", "SNMP"),
    162: ("udp", "SNMP Trap"),
    # LDAP
    389: ("tcp", "LDAP"),
    636: ("tcp", "LDAPS"),
    # RDP
    3389: ("tcp", "RDP"),
    # VNC
    5900: ("tcp", "VNC"),
    5901: ("tcp", "VNC-1"),
    # SIP/VoIP
    5060: ("udp", "SIP"),
    5061: ("tcp", "SIPS"),
    3478: ("udp", "STUN/TURN"),
    # QUIC / HTTP3
    443: ("udp", "QUIC/HTTP3"),
    # 游戏
    27015: ("udp", "Steam Game"),
    27016: ("udp", "Steam Game"),
    3074: ("udp", "Xbox Live"),
    27036: ("tcp", "Steam Networking"),
    # BitTorrent
    6881: ("tcp", "BitTorrent"),
    6882: ("tcp", "BitTorrent"),
    6889: ("tcp", "BitTorrent"),
    # WireGuard
    51820: ("udp", "WireGuard"),
    51821: ("udp", "WireGuard"),
    # OpenVPN
    1194: ("udp", "OpenVPN"),
    # IPSec
    500: ("udp", "IPSec IKE"),
    4500: ("udp", "IPSec NAT-T"),
    # PPTP
    1723: ("tcp", "PPTP"),
    # L2TP
    1701: ("udp", "L2TP"),
    # MongoDB
    27017: ("tcp", "MongoDB"),
    # MySQL
    3306: ("tcp", "MySQL"),
    # PostgreSQL
    5432: ("tcp", "PostgreSQL"),
    # Redis
    6379: ("tcp", "Redis"),
    # Elasticsearch
    9200: ("tcp", "Elasticsearch"),
    9300: ("tcp", "Elasticsearch Transport"),
    # Kafka
    9092: ("tcp", "Kafka"),
    # RabbitMQ
    5672: ("tcp", "RabbitMQ"),
    15672: ("tcp", "RabbitMQ Management"),
    # NFS
    2049: ("tcp", "NFS"),
    # SMB
    445: ("tcp", "SMB/CIFS"),
    139: ("tcp", "NetBIOS-SSN"),
    # RTMP / RTSP
    1935: ("tcp", "RTMP"),
    554: ("tcp", "RTSP"),
    # Syslog
    514: ("udp", "Syslog"),
    # Docker
    2375: ("tcp", "Docker API"),
    2376: ("tcp", "Docker TLS"),
    # Kubernetes
    6443: ("tcp", "Kubernetes API"),
    10250: ("tcp", "Kubelet"),
}


class NdpiDetector:
    """nDPI 深度包检测器

    对非 TLS 流量做协议特征分析。
    当系统安装了 nDPI 库时使用原生 nDPI，否则使用端口推断。

    注意: nDPI 原生绑定需要 C 扩展，此处先提供基于端口+协议的推断，
    后续可以用 `pyndpi` 或 ctypes 调用 libndpi.so。
    """

    def __init__(self, use_ndpi_lib: bool = False):
        self._use_ndpi = use_ndpi_lib
        self._detected_count = 0
        self._unknown_count = 0

    def detect(self, src_ip: str, dst_ip: str, sport: int,
               dport: int, protocol: str) -> Optional[str]:
        """检测非 TLS 流量的应用协议

        Args:
            src_ip: 源 IP
            dst_ip: 目标 IP
            sport: 源端口
            dport: 目标端口
            protocol: 传输协议 (tcp/udp)

        Returns:
            应用名，未识别返回 None
        """
        # TLS 流量由 SNI 处理，跳过
        if protocol == "tcp" and dport == 443:
            return None

        if self._use_ndpi:
            return self._ndpi_detect(src_ip, dst_ip, sport, dport, protocol)

        # 端口推断
        app = self._port_detect(dport, protocol)
        if app:
            self._detected_count += 1
            return app

        # 源端口也检查（对等连接）
        if sport != dport:
            app = self._port_detect(sport, protocol)
            if app:
                self._detected_count += 1
                return app

        self._unknown_count += 1
        return None

    def _port_detect(self, port: int, protocol: str) -> Optional[str]:
        """基于端口+协议的简单推断"""
        entry = PORT_PROTOCOL_MAP.get(port)
        if entry and entry[0] == protocol:
            return entry[1]
        return None

    def _ndpi_detect(self, src_ip: str, dst_ip: str, sport: int,
                     dport: int, protocol: str) -> Optional[str]:
        """使用 nDPI lib 检测（占位）

        需要安装 pyndpi 或通过 ctypes 调用 libndpi.so
        """
        try:
            # 占位: 当使用 pyndpi 时
            # import pyndpi
            # result = pyndpi.detection_process(
            #     src_ip, sport, dst_ip, dport, protocol
            # )
            # return result.protocol.app_name
            logger.debug("nDPI not yet integrated, using port fallback")
            return self._port_detect(dport, protocol)
        except ImportError:
            logger.warning("nDPI library not available, using port fallback")
            return self._port_detect(dport, protocol)

    @property
    def stats(self) -> dict:
        return {
            "detected": self._detected_count,
            "unknown": self._unknown_count,
        }
