"""应用特征库 — YAML 格式的应用特征定义与匹配"""
import logging
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

import yaml

logger = logging.getLogger("ubunturouter.orchestrator.appdb")

APP_DB_PATH = Path("/opt/ubunturouter/data/app_db.yaml")

# ─── 应用分类 ──────────────────────────────────────────────
CATEGORIES = {
    "video": "视频/直播",
    "game": "游戏",
    "chat": "即时通讯",
    "cdn": "内容分发网络",
    "stream": "流媒体/直播",
    "storage": "云存储",
    "ai": "人工智能",
    "dev": "开发工具",
    "other": "其他",
}

# ─── 内置应用特征定义 ──────────────────────────────────────
BUILTIN_APPS = [
    {
        "name": "Netflix",
        "category": "video",
        "domains": [
            "netflix.com", "*.netflix.com", "nflxext.com", "*.nflxext.com",
            "nflximg.com", "*.nflximg.com", "nflxvideo.net", "*.nflxvideo.net",
        ],
        "ips": [],
        "protocols": ["tcp/443", "tcp/80"],
    },
    {
        "name": "YouTube",
        "category": "video",
        "domains": [
            "youtube.com", "*.youtube.com", "youtu.be", "ytimg.com",
            "*.ytimg.com", "googlevideo.com", "*.googlevideo.com",
            "ggpht.com", "*.ggpht.com", "youtube-nocookie.com",
        ],
        "ips": [],
        "protocols": ["tcp/443", "udp/443"],
    },
    {
        "name": "Bilibili",
        "category": "video",
        "domains": [
            "bilibili.com", "*.bilibili.com", "b23.tv", "hdslb.com",
            "*.hdslb.com", "biligame.com", "bilibili.tv",
        ],
        "ips": [],
        "protocols": ["tcp/443"],
    },
    {
        "name": "Douyin",
        "category": "video",
        "domains": [
            "douyin.com", "*.douyin.com", "douyincdn.com", "*.douyincdn.com",
            "douyinpic.com", "douyinvod.com", "snssdk.com",
        ],
        "ips": [],
        "protocols": ["tcp/443"],
    },
    {
        "name": "TikTok",
        "category": "video",
        "domains": [
            "tiktok.com", "*.tiktok.com", "tiktokcdn.com", "*.tiktokcdn.com",
            "tiktokv.com", "*.tiktokv.com", "musical.ly", "*.musical.ly",
        ],
        "ips": [],
        "protocols": ["tcp/443"],
    },
    {
        "name": "Steam",
        "category": "game",
        "domains": [
            "steampowered.com", "*.steampowered.com", "steamcdn-a.com",
            "steamcommunity.com", "*.steamcommunity.com",
            "steamstore-a.com", "steamusercontent.com",
            "steamstatic.com", "*.steamstatic.com",
        ],
        "ips": [],
        "protocols": ["tcp/443", "tcp/27015-27050", "udp/27015-27050"],
    },
    {
        "name": "Epic Games",
        "category": "game",
        "domains": [
            "epicgames.com", "*.epicgames.com", "epicgames.dev",
            "unrealengine.com", "*.unrealengine.com",
            "eos.com", "fortnite.com",
        ],
        "ips": [],
        "protocols": ["tcp/443"],
    },
    {
        "name": "Discord",
        "category": "chat",
        "domains": [
            "discord.com", "*.discord.com", "discordapp.com",
            "*.discordapp.com", "discord.gg", "discordmedia.com",
            "discordcdn.com",
        ],
        "ips": [],
        "protocols": ["tcp/443", "udp/443"],
    },
    {
        "name": "Telegram",
        "category": "chat",
        "domains": [
            "telegram.org", "*.telegram.org", "t.me",
            "telegram.me", "tdesktop.com", "telegram-cdn.org",
        ],
        "ips": [
            "91.108.56.0/22", "91.108.4.0/22",
            "149.154.160.0/20", "95.161.64.0/20",
        ],
        "protocols": ["tcp/443"],
    },
    {
        "name": "WhatsApp",
        "category": "chat",
        "domains": [
            "whatsapp.com", "*.whatsapp.com", "whatsapp.net",
            "*.whatsapp.net", "wa.me",
        ],
        "ips": [],
        "protocols": ["tcp/443", "tcp/5222"],
    },
    {
        "name": "WeChat",
        "category": "chat",
        "domains": [
            "weixin.qq.com", "wx.qq.com", "weixinbridge.com",
            "wechat.com", "*.wechat.com",
        ],
        "ips": [],
        "protocols": ["tcp/443", "tcp/8080"],
    },
    {
        "name": "QQ",
        "category": "chat",
        "domains": [
            "qq.com", "*.qq.com", "qzone.qq.com",
            "tencent.com", "*.tencent.com", "im.qq.com",
            "id.qq.com", "qpic.cn", "gtimg.cn",
        ],
        "ips": [],
        "protocols": ["tcp/443", "udp/8000", "udp/4000-4010"],
    },
    {
        "name": "iCloud",
        "category": "storage",
        "domains": [
            "icloud.com", "*.icloud.com", "icloud-content.com",
            "*.icloud-content.com", "apple.com", "*.apple.com",
            "appldnld.apple.com", "cdn-apple.com",
        ],
        "ips": [],
        "protocols": ["tcp/443"],
    },
    {
        "name": "Google Drive",
        "category": "storage",
        "domains": [
            "drive.google.com", "docs.google.com", "sheets.google.com",
            "slides.google.com", "googleapis.com",
            "googleusercontent.com", "*.googleusercontent.com",
            "googledrive.com", "*.googledrive.com",
        ],
        "ips": [],
        "protocols": ["tcp/443"],
    },
    {
        "name": "OneDrive",
        "category": "storage",
        "domains": [
            "onedrive.com", "*.onedrive.com", "onedrive.live.com",
            "sharepoint.com", "*.sharepoint.com",
            "live.net", "*.live.net",
        ],
        "ips": [],
        "protocols": ["tcp/443"],
    },
    {
        "name": "ChatGPT",
        "category": "ai",
        "domains": [
            "chatgpt.com", "*.chatgpt.com", "openai.com", "*.openai.com",
            "oaistatic.com", "*.oaistatic.com", "oaiusercontent.com",
            "*.oaiusercontent.com", "api.openai.com",
        ],
        "ips": [],
        "protocols": ["tcp/443"],
    },
    {
        "name": "GitHub",
        "category": "dev",
        "domains": [
            "github.com", "*.github.com", "githubusercontent.com",
            "*.githubusercontent.com", "github.io", "*.github.io",
            "githubassets.com", "*.githubassets.com",
        ],
        "ips": [],
        "protocols": ["tcp/443", "tcp/22", "tcp/9418"],
    },
    {
        "name": "DockerHub",
        "category": "dev",
        "domains": [
            "docker.com", "*.docker.com", "docker.io", "*.docker.io",
            "dockerhub.com", "*.dockerhub.com",
            "registry-1.docker.io", "cdn-registry-1.docker.io",
            "production.cloudflare.docker.com",
        ],
        "ips": [],
        "protocols": ["tcp/443"],
    },
    {
        "name": "CloudFlare",
        "category": "cdn",
        "domains": [
            "cloudflare.com", "*.cloudflare.com", "cloudflare.net",
            "*.cloudflare.net", "cloudflarecdn.com",
            "cloudflare-dns.com",
        ],
        "ips": [
            "103.21.244.0/22", "103.22.200.0/22",
            "103.31.4.0/22", "104.16.0.0/12",
            "108.162.192.0/18", "131.0.72.0/22",
            "141.101.64.0/18", "162.158.0.0/15",
            "172.64.0.0/13", "173.245.48.0/20",
            "188.114.96.0/20", "190.93.240.0/20",
            "197.234.240.0/22", "198.41.128.0/17",
        ],
        "protocols": ["tcp/443", "tcp/80"],
    },
    {
        "name": "Akamai",
        "category": "cdn",
        "domains": [
            "akamai.net", "*.akamai.net", "akamaiedge.net",
            "*.akamaiedge.net", "akamaihd.net", "*.akamaihd.net",
            "akamaitechnologies.com",
        ],
        "ips": [
            "23.0.0.0/12", "23.32.0.0/11", "23.64.0.0/14",
            "23.192.0.0/11", "23.224.0.0/14", "23.236.0.0/14",
            "69.20.0.0/14", "69.24.0.0/13", "92.122.0.0/15",
            "95.100.0.0/15", "96.6.0.0/15", "104.64.0.0/10",
        ],
        "protocols": ["tcp/443", "tcp/80"],
    },
    {
        "name": "Google CDN",
        "category": "cdn",
        "domains": [
            "googleapis.com", "*.googleapis.com", "gstatic.com",
            "*.gstatic.com", "googleusercontent.com",
            "google.com", "*.google.com",
        ],
        "ips": [],
        "protocols": ["tcp/443", "tcp/80"],
    },
]


@dataclass
class App:
    """应用特征定义"""
    name: str
    category: str = "other"
    domains: List[str] = field(default_factory=list)
    ips: List[str] = field(default_factory=list)
    protocols: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "category_label": CATEGORIES.get(self.category, self.category),
            "domains": self.domains,
            "ips": self.ips,
            "protocols": self.protocols,
        }


class AppDB:
    """应用特征库

    加载 YAML 格式的应用特征定义，提供搜索、分类过滤和 DNS/IP 匹配功能。
    """

    def __init__(self, db_path: str = str(APP_DB_PATH)):
        self._path = Path(db_path)
        self._apps: List[App] = []
        self._domain_index: Dict[str, App] = {}  # domain -> App
        self._ip_index: Dict[str, App] = {}  # cidr -> App
        self._loaded = False
        self._ensure_default_db()
        self.load()

    def load(self) -> None:
        """从 YAML 加载应用特征库"""
        try:
            if self._path.exists():
                with open(self._path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if isinstance(data, list):
                    self._apps = []
                    for item in data:
                        app = App(
                            name=item.get("name", ""),
                            category=item.get("category", "other"),
                            domains=item.get("domains", []),
                            ips=item.get("ips", []),
                            protocols=item.get("protocols", []),
                        )
                        if app.name:
                            self._apps.append(app)
                self._rebuild_index()
                self._loaded = True
                logger.info("Loaded %d apps from %s", len(self._apps), self._path)
            else:
                self._apps = []
                self._loaded = True
                logger.warning("App database not found at %s", self._path)
        except Exception as e:
            logger.error("Failed to load app database: %s", e)
            self._apps = []
            self._loaded = True

    def reload(self) -> None:
        """重新加载应用特征库"""
        self.load()

    def search(self, query: str) -> List[App]:
        """搜索应用（按名称模糊匹配）"""
        if not self._loaded:
            self.load()
        q = query.lower()
        return [a for a in self._apps if q in a.name.lower()]

    def get_by_category(self, cat: str) -> List[App]:
        """按分类获取应用列表"""
        if not self._loaded:
            self.load()
        return [a for a in self._apps if a.category == cat]

    def get_all(self) -> List[App]:
        """获取所有应用"""
        if not self._loaded:
            self.load()
        return list(self._apps)

    def get_by_name(self, name: str) -> Optional[App]:
        """按名称获取应用"""
        if not self._loaded:
            self.load()
        for a in self._apps:
            if a.name.lower() == name.lower():
                return a
        return None

    def match_by_domain(self, domain: str) -> Optional[App]:
        """通过域名匹配应用"""
        if not self._loaded:
            self.load()
        if not domain:
            return None
        d = domain.lower().rstrip(".")
        # 精确匹配
        if d in self._domain_index:
            return self._domain_index[d]
        # 通配符匹配: *.example.com
        for pattern, app in self._domain_index.items():
            if pattern.startswith("*."):
                if d.endswith(pattern[1:]) or d == pattern[2:]:
                    return app
        # 逐级缩短域名匹配
        parts = d.split(".")
        for i in range(1, len(parts) - 1):
            parent = ".".join(parts[i:])
            if parent in self._domain_index:
                return self._domain_index[parent]
        return None

    def match_by_ip(self, ip: str) -> Optional[App]:
        """通过 IP 地址匹配应用（CIDR 匹配）"""
        if not self._loaded:
            self.load()
        if not ip:
            return None
        import ipaddress
        try:
            addr = ipaddress.ip_address(ip)
            for cidr_str, app in self._ip_index.items():
                if addr in ipaddress.ip_network(cidr_str, strict=False):
                    return app
        except ValueError:
            pass
        return None

    def get_categories(self) -> Dict[str, str]:
        """获取所有分类"""
        return dict(CATEGORIES)

    # ─── 内部方法 ──────────────────────────────────────────────

    def _rebuild_index(self) -> None:
        """重建域名字典和 IP 字典索引"""
        self._domain_index.clear()
        self._ip_index.clear()
        for app in self._apps:
            for domain in app.domains:
                d = domain.lower().rstrip(".")
                self._domain_index[d] = app
            for cidr in app.ips:
                self._ip_index[cidr] = app

    def _ensure_default_db(self) -> None:
        """如果数据库文件不存在则用内置默认值创建"""
        if not self._path.exists():
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with open(self._path, "w", encoding="utf-8") as f:
                    yaml.dump(BUILTIN_APPS, f, default_flow_style=False,
                              allow_unicode=True, sort_keys=False)
                logger.info("Created default app database at %s", self._path)
            except OSError as e:
                logger.error("Failed to create default app database: %s", e)
