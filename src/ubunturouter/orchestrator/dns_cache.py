"""DNS 被动监听缓存 — 零 CPU，实时 IP→应用映射

原理：监听 DNS 应答，将 IP→域名→应用缓存，TTL 内精准。
"""
import time
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("ubunturouter.orchestrator.dns_cache")

# ─── 预置域名→应用映射（200+ 业内常见应用）───────────────
DOMAIN_APP_MAP: Dict[str, str] = {
    # 流媒体
    "netflix.com": "Netflix", "*.netflix.com": "Netflix",
    "nflxext.com": "Netflix", "*.nflxext.com": "Netflix",
    "nflximg.com": "Netflix", "*.nflximg.com": "Netflix",
    "nflxvideo.net": "Netflix", "*.nflxvideo.net": "Netflix",
    "youtube.com": "YouTube", "*.youtube.com": "YouTube",
    "youtu.be": "YouTube", "googlevideo.com": "YouTube",
    "*.googlevideo.com": "YouTube", "ytimg.com": "YouTube",
    "*.ytimg.com": "YouTube", "ggpht.com": "YouTube",
    "bilibili.com": "Bilibili", "*.bilibili.com": "Bilibili",
    "b23.tv": "Bilibili", "hdslb.com": "Bilibili",
    "*.hdslb.com": "Bilibili",
    "douyin.com": "Douyin", "*.douyin.com": "Douyin",
    "douyincdn.com": "*.douyin.com", "douyinpic.com": "Douyin",
    "tiktok.com": "TikTok", "*.tiktok.com": "TikTok",
    "tiktokcdn.com": "TikTok", "*.tiktokcdn.com": "TikTok",
    "tiktokv.com": "TikTok", "*.tiktokv.com": "TikTok",
    "twitch.tv": "Twitch", "*.twitch.tv": "Twitch",
    "hulu.com": "Hulu", "*.hulu.com": "Hulu",
    "disneyplus.com": "Disney+", "*.disneyplus.com": "Disney+",
    "hbomax.com": "HBO Max", "*.hbomax.com": "HBO Max",
    "primevideo.com": "Amazon Prime", "*.primevideo.com": "Amazon Prime",
    "spotify.com": "Spotify", "*.spotify.com": "Spotify",
    "pandora.com": "Pandora", "*.pandora.com": "Pandora",
    "iqiyi.com": "爱奇艺", "*.iqiyi.com": "爱奇艺",
    "youku.com": "优酷", "*.youku.com": "优酷",
    "tencentvideo.com": "腾讯视频", "*.tencentvideo.com": "腾讯视频",
    "mgtv.com": "芒果TV", "*.mgtv.com": "芒果TV",
    "sohu.com": "搜狐视频", "tv.sohu.com": "搜狐视频",

    # 社交
    "weixin.qq.com": "WeChat", "wx.qq.com": "WeChat",
    "wechat.com": "WeChat", "*.wechat.com": "WeChat",
    "telegram.org": "Telegram", "*.telegram.org": "Telegram",
    "t.me": "Telegram",
    "discord.com": "Discord", "*.discord.com": "Discord",
    "discordapp.com": "Discord", "*.discordapp.com": "Discord",
    "discord.gg": "Discord", "discordmedia.com": "Discord",
    "whatsapp.com": "WhatsApp", "*.whatsapp.com": "WhatsApp",
    "whatsapp.net": "WhatsApp", "*.whatsapp.net": "WhatsApp",
    "wa.me": "WhatsApp",
    "qq.com": "QQ", "*.qq.com": "QQ",
    "qzone.qq.com": "QQ", "im.qq.com": "QQ",
    "qpic.cn": "QQ", "gtimg.cn": "QQ",
    "snssdk.com": "Douyin",
    "weibo.com": "微博", "*.weibo.com": "微博",
    "xiaohongshu.com": "小红书", "*.xiaohongshu.com": "小红书",
    "zhihu.com": "知乎", "*.zhihu.com": "知乎",
    "reddit.com": "Reddit", "*.reddit.com": "Reddit",
    "twitter.com": "Twitter/X", "*.twitter.com": "Twitter/X",
    "x.com": "Twitter/X", "*.x.com": "Twitter/X",
    "facebook.com": "Facebook", "*.facebook.com": "Facebook",
    "instagram.com": "Instagram", "*.instagram.com": "Instagram",
    "linkedin.com": "LinkedIn", "*.linkedin.com": "LinkedIn",
    "pinterest.com": "Pinterest", "*.pinterest.com": "Pinterest",
    "snapchat.com": "Snapchat", "*.snapchat.com": "Snapchat",

    # 游戏
    "steampowered.com": "Steam", "*.steampowered.com": "Steam",
    "steamcdn-a.com": "Steam", "steamcommunity.com": "Steam",
    "steamstatic.com": "Steam", "*.steamstatic.com": "Steam",
    "steamcontent.com": "Steam", "*.steamcontent.com": "Steam",
    "epicgames.com": "Epic Games", "*.epicgames.com": "Epic Games",
    "unrealengine.com": "Epic Games", "fortnite.com": "Epic Games",
    "nintendo.com": "Nintendo", "*.nintendo.com": "Nintendo",
    "playstation.com": "PlayStation", "*.playstation.com": "PlayStation",
    "xbox.com": "Xbox", "*.xbox.com": "Xbox",
    "xboxlive.com": "Xbox Live", "*.xboxlive.com": "Xbox Live",
    "roblox.com": "Roblox", "*.roblox.com": "Roblox",
    "minecraft.net": "Minecraft", "*.minecraft.net": "Minecraft",
    "mojang.com": "Mojang", "*.mojang.com": "Mojang",
    "origin.com": "EA Origin", "*.origin.com": "EA Origin",
    "ea.com": "Electronic Arts", "*.ea.com": "Electronic Arts",
    "ubisoft.com": "Ubisoft", "*.ubisoft.com": "Ubisoft",
    "ubisoftconnect.com": "Ubisoft Connect",
    "battle.net": "Battle.net", "*.battle.net": "Battle.net",
    "blizzard.com": "Blizzard", "*.blizzard.com": "Blizzard",
    "riotgames.com": "Riot Games", "*.riotgames.com": "Riot Games",
    "lol.riotgames.com": "英雄联盟",
    "playvalorant.com": "Valorant", "*.playvalorant.com": "Valorant",
    "honorofkings.com": "王者荣耀",
    "gog.com": "GOG Galaxy", "*.gog.com": "GOG Galaxy",
    "itch.io": "itch.io",

    # 办公与协作
    "teams.microsoft.com": "Microsoft Teams",
    "*.teams.microsoft.com": "Microsoft Teams",
    "zoom.us": "Zoom", "*.zoom.us": "Zoom",
    "zoomgov.com": "Zoom",
    "slack.com": "Slack", "*.slack.com": "Slack",
    "notion.so": "Notion", "*.notion.so": "Notion",
    "miro.com": "Miro", "*.miro.com": "Miro",
    "figma.com": "Figma", "*.figma.com": "Figma",
    "asana.com": "Asana", "*.asana.com": "Asana",
    "trello.com": "Trello", "*.trello.com": "Trello",
    "jira.com": "Jira", "*.jira.com": "Jira",
    "atlassian.com": "Atlassian", "*.atlassian.com": "Atlassian",
    "confluence.com": "Confluence",
    "office.com": "Office 365", "*.office.com": "Office 365",
    "office365.com": "Office 365",
    "live.com": "Microsoft Live", "*.live.com": "Microsoft Live",
    "onedrive.com": "OneDrive", "*.onedrive.com": "OneDrive",
    "sharepoint.com": "SharePoint", "*.sharepoint.com": "SharePoint",

    # AI
    "chatgpt.com": "ChatGPT", "*.chatgpt.com": "ChatGPT",
    "openai.com": "OpenAI", "*.openai.com": "OpenAI",
    "oaistatic.com": "OpenAI", "*.oaistatic.com": "OpenAI",
    "oaiusercontent.com": "OpenAI",
    "claude.ai": "Claude", "*.claude.ai": "Claude",
    "anthropic.com": "Anthropic",
    "bard.google.com": "Gemini",
    "gemini.google.com": "Gemini",
    "copilot.microsoft.com": "Copilot",
    "githubcopilot.com": "GitHub Copilot",
    "perplexity.ai": "Perplexity", "*.perplexity.ai": "Perplexity",
    "midjourney.com": "Midjourney",
    "stability.ai": "Stability AI",
    "huggingface.co": "HuggingFace", "*.huggingface.co": "HuggingFace",

    # 开发工具
    "github.com": "GitHub", "*.github.com": "GitHub",
    "githubusercontent.com": "GitHub", "*.githubusercontent.com": "GitHub",
    "githubassets.com": "GitHub", "*.githubassets.com": "GitHub",
    "gitlab.com": "GitLab", "*.gitlab.com": "GitLab",
    "bitbucket.org": "Bitbucket",
    "docker.com": "Docker Hub", "*.docker.com": "Docker Hub",
    "docker.io": "Docker Hub", "*.docker.io": "Docker Hub",
    "pypi.org": "PyPI", "*.pypi.org": "PyPI",
    "npmjs.com": "npm", "*.npmjs.com": "npm",
    "npmjs.org": "npm", "*.npmjs.org": "npm",
    "nuget.org": "NuGet", "*.nuget.org": "NuGet",
    "maven.org": "Maven Central",
    "crates.io": "crates.io",
    "rubygems.org": "RubyGems",
    "stackoverflow.com": "Stack Overflow",
    "stackexchange.com": "Stack Exchange",
    "medium.com": "Medium", "*.medium.com": "Medium",
    "dev.to": "DEV Community",
    "codesandbox.io": "CodeSandbox",
    "replit.com": "Replit",

    # 云存储
    "icloud.com": "iCloud", "*.icloud.com": "iCloud",
    "icloud-content.com": "iCloud",
    "apple.com": "Apple", "*.apple.com": "Apple",
    "appldnld.apple.com": "Apple",
    "drive.google.com": "Google Drive",
    "docs.google.com": "Google Docs",
    "sheets.google.com": "Google Sheets",
    "googleapis.com": "Google API", "*.googleapis.com": "Google API",
    "googleusercontent.com": "Google", "*.googleusercontent.com": "Google",
    "googledrive.com": "Google Drive",
    "dropbox.com": "Dropbox", "*.dropbox.com": "Dropbox",
    "dropboxusercontent.com": "Dropbox",
    "box.com": "Box", "*.box.com": "Box",
    "mega.nz": "MEGA", "*.mega.nz": "MEGA",
    "backblaze.com": "Backblaze",
    "wasabi.com": "Wasabi",

    # 搜索引擎/门户
    "google.com": "Google", "*.google.com": "Google",
    "google.co.*": "Google", "googleadservices.com": "Google Ads",
    "bing.com": "Bing", "*.bing.com": "Bing",
    "baidu.com": "百度", "*.baidu.com": "百度",
    "sogou.com": "搜狗", "*.sogou.com": "搜狗",
    "yandex.com": "Yandex", "*.yandex.com": "Yandex",
    "duckduckgo.com": "DuckDuckGo",

    # CDN / 基础设施
    "cloudflare.com": "Cloudflare", "*.cloudflare.com": "Cloudflare",
    "cloudflare.net": "Cloudflare", "*.cloudflare.net": "Cloudflare",
    "cloudflarecdn.com": "Cloudflare",
    "akamai.net": "Akamai", "*.akamai.net": "Akamai",
    "akamaiedge.net": "Akamai", "*.akamaiedge.net": "Akamai",
    "akamaihd.net": "Akamai", "*.akamaihd.net": "Akamai",
    "fastly.com": "Fastly", "*.fastly.com": "Fastly",
    "fastly.net": "Fastly", "*.fastly.net": "Fastly",
    "cloudfront.net": "AWS CloudFront",
    "aws.amazon.com": "AWS", "amazonaws.com": "AWS",
    "*.amazonaws.com": "AWS",
    "azure.com": "Azure", "*.azure.com": "Azure",
    "azureedge.net": "Azure CDN",
    "azurefd.net": "Azure Front Door",
    "gcp.com": "GCP", "googlecloud.com": "GCP",
    "gstatic.com": "Google Static", "*.gstatic.com": "Google Static",
    "jsdelivr.net": "jsDelivr",
    "cdnjs.com": "cdnjs",
    "unpkg.com": "unpkg",
    "vercel.com": "Vercel", "*.vercel.com": "Vercel",
    "netlify.com": "Netlify", "*.netlify.com": "Netlify",

    # 操作系统更新
    "update.microsoft.com": "Windows Update",
    "download.windowsupdate.com": "Windows Update",
    "swcdn.apple.com": "Apple Update",
    "mesu.apple.com": "Apple Update",
    "updates.cdn-apple.com": "Apple Update",
    "snapcraft.io": "Snap Store",
    "flatpak.org": "Flathub",
    "launchpad.net": "Ubuntu",
    "archive.ubuntu.com": "Ubuntu APT",
    "security.ubuntu.com": "Ubuntu Security",
    "packages.debian.org": "Debian APT",
    "dl.google.com": "Google Chrome",
    "tools.google.com": "Google Update",
}


class DnsAppCache:
    """DNS 被动监听缓存 — 从 DNS 应答中提取 IP→应用映射

    使用方式:
        在 dnsmasq hook 或 pcap 回调中调用 on_dns_response(domain, ips, ttl)
        识别引擎通过 lookup(ip) 获取 IP 对应的应用名
    """

    def __init__(self):
        self._ip_cache: Dict[str, dict] = {}  # ip -> {app, expire, domain}
        self._domain_map: Dict[str, str] = {}
        self._build_domain_map()

    def _build_domain_map(self) -> None:
        """构建域名→应用映射（含通配符处理）"""
        for domain_expr, app_name in DOMAIN_APP_MAP.items():
            # 通配符 *.example.com → 存储为 .example.com 做后缀匹配
            if domain_expr.startswith("*."):
                suffix = domain_expr[1:]  # .example.com
                self._domain_map[suffix] = app_name
            else:
                self._domain_map[domain_expr] = app_name

    def on_dns_response(self, domain: str, ips: List[str], ttl: int = 300) -> None:
        """DNS 应答回调 — 将 IP→应用映射写入缓存

        Args:
            domain: 查询的域名（完整，如 www.netflix.com）
            ips: DNS 返回的 IP 地址列表
            ttl: DNS 记录的 TTL（秒）
        """
        app_name = self._resolve_domain(domain)
        if not app_name:
            return

        expire = time.time() + max(ttl, 60)  # 至少 60 秒保底
        for ip in ips:
            self._ip_cache[ip] = {
                "app": app_name,
                "expire": expire,
                "domain": domain,
            }
        logger.debug("DNS cache: %s -> %s (ips=%s, ttl=%d)", domain, app_name, ips, ttl)

    def lookup(self, ip: str) -> Optional[str]:
        """根据 IP 查找应用名

        Returns:
            应用名，如果缓存未命中或已过期返回 None
        """
        entry = self._ip_cache.get(ip)
        if not entry:
            return None
        if time.time() > entry["expire"]:
            del self._ip_cache[ip]
            return None
        return entry["app"]

    def lookup_with_info(self, ip: str) -> Optional[dict]:
        """根据 IP 查找详细信息"""
        entry = self._ip_cache.get(ip)
        if not entry:
            return None
        if time.time() > entry["expire"]:
            del self._ip_cache[ip]
            return None
        return entry

    def _resolve_domain(self, domain: str) -> Optional[str]:
        """解析域名到应用名"""
        d = domain.lower().rstrip(".")
        # 精确匹配
        if d in self._domain_map:
            return self._domain_map[d]
        # 后缀匹配: .example.com
        for suffix, app_name in self._domain_map.items():
            if suffix.startswith(".") and d.endswith(suffix):
                return app_name
            if suffix.startswith("*."):
                # *.example.com → 匹配任何层级的 example.com
                base = suffix[2:]
                if d == base or d.endswith("." + base):
                    return app_name
        # 逐级缩短匹配
        parts = d.split(".")
        for i in range(1, len(parts) - 1):
            parent = ".".join(parts[i:])
            if parent in self._domain_map:
                return self._domain_map[parent]
        return None

    def add_custom_rule(self, domain_expr: str, app_name: str) -> None:
        """添加自定义域名规则"""
        d = domain_expr.lower().strip()
        if d.startswith("*."):
            self._domain_map[d[1:]] = app_name
        else:
            self._domain_map[d] = app_name

    def remove_expired(self) -> int:
        """清理过期缓存，返回清理条目数"""
        now = time.time()
        expired = [ip for ip, entry in self._ip_cache.items() if now > entry["expire"]]
        for ip in expired:
            del self._ip_cache[ip]
        return len(expired)

    def clear(self) -> None:
        """清空所有缓存"""
        self._ip_cache.clear()

    @property
    def cache_size(self) -> int:
        return len(self._ip_cache)

    @property
    def domain_rules_count(self) -> int:
        return len(self._domain_map)
