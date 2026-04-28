"""TLS SNI 提取器 — 从 TLS Client Hello 首包提取 SNI 域名

原理：TLS Client Hello 首包明文包含 SNI (Server Name Indication)。
通过 nfqueue 只截取每个流的第一包做 SNI 解析。
"""
import struct
import logging
from typing import Optional, Callable

logger = logging.getLogger("ubunturouter.orchestrator.sni_extractor")


class SniExtractor:
    """TLS SNI 提取器

    使用方式:
        extractor = SniExtractor(resolve_callback=app_db.match_by_domain)
        sni = extractor.extract_sni(tcp_payload_bytes)
        if sni:
            app = extractor.resolve_app(sni)
    """

    def __init__(self, resolve_callback: Optional[Callable] = None):
        self._resolve_callback = resolve_callback
        # 统计
        self._total_packets = 0
        self._sni_found = 0
        self._app_matched = 0

    def extract_sni(self, payload: bytes) -> Optional[str]:
        """从 TLS Client Hello 提取 SNI

        Args:
            payload: TCP 负载字节（已剥离 IP/TCP 头）

        Returns:
            SNI 域名，不是 TLS Client Hello 则返回 None
        """
        self._total_packets += 1

        if not self._is_tls_client_hello(payload):
            return None

        try:
            sni = self._parse_sni(payload)
            if sni:
                self._sni_found += 1
            return sni
        except Exception as e:
            logger.debug("SNI parse error: %s", e)
            return None

    def resolve_app(self, sni: str) -> Optional[str]:
        """通过 SNI 域名解析应用名"""
        if not self._resolve_callback:
            return None
        try:
            result = self._resolve_callback(sni)
            if result:
                self._app_matched += 1
                if hasattr(result, "name"):
                    return result.name
                return str(result)
        except Exception as e:
            logger.debug("App resolve error for SNI %s: %s", sni, e)
        return None

    # ─── TLS 解析 ──────────────────────────────────────────

    @staticmethod
    def _is_tls_client_hello(payload: bytes) -> bool:
        """检查是否为 TLS Client Hello 首包

        TLS 记录头结构 (5 bytes):
          - ContentType (1): 0x16 = Handshake
          - ProtocolVersion (2): 0x0301 (TLS1.0) ~ 0x0304 (TLS1.3)
          - Length (2): 记录长度
        """
        if len(payload) < 50:
            return False
        # ContentType: 0x16 (Handshake)
        if payload[0] != 0x16:
            return False
        # ProtocolVersion: 0x03xx
        if payload[1] != 0x03:
            return False
        # Handshake Type (1 byte after record header)
        # 跳过记录头(5) → Handshake Type = 0x01 (ClientHello)
        if len(payload) < 6:
            return False
        if payload[5] != 0x01:
            return False
        return True

    @staticmethod
    def _parse_sni(payload: bytes) -> Optional[str]:
        """从 TLS Client Hello 中解析 SNI 扩展

        TLS Record Header (5 bytes):
          - ContentType (1)
          - Version (2)
          - Length (2)

        Handshake Header (4 bytes):
          - HandshakeType (1) = 0x01
          - Length (3)

        ClientHello 结构:
          - Version (2)
          - Random (32)
          - Session ID Length (1) + Session ID (var)
          - Cipher Suites Length (2) + Cipher Suites (var)
          - Compression Methods Length (1) + Methods (var)
          - Extensions Length (2)
          - Extensions (var):
            - Extension Type (2) + Length (2) + Data (var)
            - SNI Extension Type = 0x0000

        SNI Extension Data:
          - Server Name List Length (2)
          - Server Name Type (1) = 0x00 (host_name)
          - Server Name Length (2)
          - Server Name (var)
        """
        try:
            pos = 5  # 跳过 TLS 记录头
            # 跳过 Handshake header (4 bytes)
            pos += 4
            # 跳过 Client Version (2 bytes)
            pos += 2
            # 跳过 Random (32 bytes)
            pos += 32
            # 跳过 Session ID
            if pos >= len(payload):
                return None
            session_id_len = payload[pos]
            pos += 1 + session_id_len
            # 跳过 Cipher Suites
            if pos + 2 > len(payload):
                return None
            cipher_len = struct.unpack("!H", payload[pos:pos+2])[0]
            pos += 2 + cipher_len
            # 跳过 Compression Methods
            if pos >= len(payload):
                return None
            comp_len = payload[pos]
            pos += 1 + comp_len
            # Extensions
            if pos + 2 > len(payload):
                return None
            ext_len = struct.unpack("!H", payload[pos:pos+2])[0]
            pos += 2

            while pos + 4 <= len(payload) and pos < pos + ext_len:
                ext_type = struct.unpack("!H", payload[pos:pos+2])[0]
                ext_data_len = struct.unpack("!H", payload[pos+2:pos+4])[0]
                pos += 4
                if ext_type == 0x0000:  # SNI Extension
                    # Server Name List Length (2)
                    if pos + 2 > len(payload):
                        return None
                    name_list_len = struct.unpack("!H", payload[pos:pos+2])[0]
                    pos += 2
                    # Server Name Type (1) = 0x00 (host_name)
                    if pos >= len(payload):
                        return None
                    name_type = payload[pos]
                    pos += 1
                    if name_type != 0x00:
                        return None
                    # Server Name Length (2)
                    if pos + 2 > len(payload):
                        return None
                    name_len = struct.unpack("!H", payload[pos:pos+2])[0]
                    pos += 2
                    # Server Name
                    if pos + name_len > len(payload):
                        return None
                    return payload[pos:pos+name_len].decode("utf-8", errors="ignore")
                else:
                    pos += ext_data_len

        except (struct.error, IndexError, UnicodeDecodeError) as e:
            logger.debug("SNI parse failed: %s", e)
        return None

    @property
    def stats(self) -> dict:
        return {
            "total_packets": self._total_packets,
            "sni_found": self._sni_found,
            "app_matched": self._app_matched,
        }
