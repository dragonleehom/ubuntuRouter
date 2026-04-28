"""统一识别引擎 — 三层识别（DNS 缓存 → TLS SNI → nDPI 兜底）

将 DNS 缓存、TLS SNI 提取、nDPI 检测统一编排为识别管线。
识别结果写入 connmark 用于 nftables 数据路径。
"""
import logging
from typing import Optional, Dict, List
from .dns_cache import DnsAppCache
from .sni_extractor import SniExtractor
from .ndpi_detector import NdpiDetector

logger = logging.getLogger("ubunturouter.orchestrator.identification_engine")


class IdentificationEngine:
    """统一应用识别引擎

    三层识别策略:
      Layer 2: DNS 缓存查找 (零 CPU, 最快)
      Layer 1: TLS SNI 提取 (最准, 仅首包)
      Layer 3: nDPI 兜底 (非 TLS 流量)

    识别结果 → connmark (nftables)
    """

    def __init__(self, app_db=None):
        self.dns_cache = DnsAppCache()
        self.sni_extractor = SniExtractor(
            resolve_callback=lambda sni: self._resolve_app_from_db(sni, app_db)
        )
        self.ndpi_detector = NdpiDetector()
        self._app_db = app_db
        # 用户自定义应用识别规则
        self._custom_rules: List[dict] = []

    def identify_by_ip(self, ip: str) -> Optional[str]:
        """通过 IP 地址识别应用（DNS 缓存层）

        Args:
            ip: 目标 IP 地址

        Returns:
            应用名，未识别返回 None
        """
        return self.dns_cache.lookup(ip)

    def identify_by_sni(self, sni: str) -> Optional[str]:
        """通过 SNI 域名识别应用

        Args:
            sni: TLS SNI 域名

        Returns:
            应用名
        """
        # 先查自定义规则
        for rule in self._custom_rules:
            if self._match_custom_domain(sni, rule.get("domain", "")):
                return rule.get("app_name")
        # 再查 AppDB
        return self.sni_extractor.resolve_app(sni)

    def identify_by_flow(self, dst_ip: str, tls_payload: Optional[bytes] = None,
                         dport: int = 0, protocol: str = "tcp") -> Optional[str]:
        """通过完整流信息识别应用（三层管线）

        流程:
          1. 先查 DNS 缓存 (IP→应用)
          2. 如果 DNS 未命中且有 TLS 首包，提取 SNI→应用
          3. 如果 TLS 也未命中且非 HTTPS，走 nDPI 兜底

        Args:
            dst_ip: 目标 IP
            tls_payload: TLS Client Hello 首包 payload (可选)
            dport: 目标端口
            protocol: 传输协议

        Returns:
            应用名
        """
        # Layer 2: DNS 缓存
        app = self.dns_cache.lookup(dst_ip)
        if app:
            logger.debug("DNS cache hit: %s -> %s", dst_ip, app)
            return app

        # Layer 1: TLS SNI
        if tls_payload and dport == 443:
            sni = self.sni_extractor.extract_sni(tls_payload)
            if sni:
                app = self.identify_by_sni(sni)
                if app:
                    logger.debug("SNI hit: %s -> %s", sni, app)
                    return app
                logger.debug("SNI found but app not matched: %s", sni)

        # Layer 3: nDPI 兜底
        if dport != 443:
            app = self.ndpi_detector.detect("", dst_ip, 0, dport, protocol)
            if app:
                logger.debug("nDPI hit: port %d/%s -> %s", dport, protocol, app)
                return app

        return None

    def identify_connection(self, flow: dict) -> Optional[str]:
        """通过 flow 字典识别（适配 conntrack 事件结构）

        flow 结构:
        {
            "src_ip": "...",
            "dst_ip": "...",
            "sport": 12345,
            "dport": 443,
            "protocol": "tcp",
            "tls_payload": b"..."  # 可选，首包 payload
        }
        """
        return self.identify_by_flow(
            dst_ip=flow.get("dst_ip", ""),
            tls_payload=flow.get("tls_payload"),
            dport=flow.get("dport", 0),
            protocol=flow.get("protocol", "tcp"),
        )

    # ─── 预置应用识别数据库 ───────────────────────────────

    def get_app_list(self) -> List[dict]:
        """获取预置应用列表（开箱即用）"""
        import json
        seen = set()
        apps = []
        for domain_expr, app_name in self.dns_cache._domain_map.items():
            if app_name not in seen:
                seen.add(app_name)
                d = domain_expr
                if d.startswith("."):
                    d = "*" + d
                apps.append({
                    "name": app_name,
                    "domain_expr": d,
                    "category": self._guess_category(app_name),
                })
        return sorted(apps, key=lambda x: x["name"])

    def _guess_category(self, app_name: str) -> str:
        """猜测应用分类"""
        video_apps = {"Netflix", "YouTube", "Bilibili", "Douyin", "TikTok",
                      "Twitch", "Hulu", "Disney+", "HBO Max", "Amazon Prime",
                      "Spotify", "Pandora", "爱奇艺", "优酷", "腾讯视频",
                      "芒果TV", "搜狐视频"}
        social_apps = {"WeChat", "Telegram", "Discord", "WhatsApp", "QQ",
                       "微博", "小红书", "知乎", "微信", "Twitter/X",
                       "Facebook", "Instagram", "LinkedIn", "Pinterest",
                       "Snapchat", "Reddit"}
        game_apps = {"Steam", "Epic Games", "Nintendo", "PlayStation",
                     "Xbox", "Xbox Live", "Roblox", "Minecraft"}
        ai_apps = {"ChatGPT", "OpenAI", "Claude", "Gemini", "Copilot",
                   "GitHub Copilot", "Perplexity", "Midjourney", "HuggingFace"}
        storage_apps = {"iCloud", "Google Drive", "OneDrive", "Dropbox",
                        "Box", "MEGA", "Backblaze"}

        if app_name in video_apps:
            return "video"
        if app_name in social_apps:
            return "social"
        if app_name in game_apps:
            return "game"
        if app_name in ai_apps:
            return "ai"
        if app_name in storage_apps:
            return "storage"
        return "other"

    # ─── 用户自定义应用识别规则 ───────────────────────────

    def add_custom_rule(self, rule: dict) -> None:
        """添加用户自定义应用识别规则

        rule 结构:
        {
            "name": "我的私有云",
            "domain": ["*.my-private-cloud.com"],
            "sni": ["*.myapp.internal"],
            "port": ["tcp/8443", "tcp/9000"],
            "exclude_domain": ["cdn.my-private-cloud.com"]
        }
        """
        self._custom_rules.append(rule)
        # 同时更新 DNS 缓存
        for domain in rule.get("domain", []):
            self.dns_cache.add_custom_rule(domain, rule.get("name", rule["name"]))
        logger.info("Added custom app rule: %s", rule.get("name"))

    def remove_custom_rule(self, name: str) -> bool:
        """删除自定义规则"""
        before = len(self._custom_rules)
        self._custom_rules = [r for r in self._custom_rules if r.get("name") != name]
        return len(self._custom_rules) < before

    def get_custom_rules(self) -> List[dict]:
        """获取所有自定义规则"""
        return list(self._custom_rules)

    def _match_custom_domain(self, domain: str, pattern: str) -> bool:
        """检查域名是否匹配自定义规则"""
        if not pattern or not domain:
            return False
        d = domain.lower().rstrip(".")
        p = pattern.lower().strip()
        if p.startswith("*."):
            return d.endswith(p[1:]) or d == p[2:]
        return d == p

    # ─── connmark 写入 ─────────────────────────────────────

    def write_connmark(self, dst_ip: str, app_name: str,
                       app_id: int = 0) -> bool:
        """将识别结果写入 conntrack mark（占位）

        实际写入由 nftables 规则或 conntrack -U 完成
        """
        if not app_id:
            # 根据应用名生成稳定的 app_id
            app_id = hash(app_name) & 0xFFFF
        try:
            cmd = f"conntrack -U -p tcp -d {dst_ip} --mark {app_id}"
            import subprocess
            subprocess.run(cmd, shell=True, capture_output=True, timeout=3)
            return True
        except Exception as e:
            logger.debug("Write connmark failed: %s", e)
            return False

    @property
    def stats(self) -> dict:
        return {
            "dns_cache_size": self.dns_cache.cache_size,
            "domain_rules": self.dns_cache.domain_rules_count,
            "sni_extractor": self.sni_extractor.stats,
            "ndpi_detector": self.ndpi_detector.stats,
            "custom_rules": len(self._custom_rules),
        }
