"""App 适配层 — 将外部应用格式转换为 1Panel 兼容标准

支持适配器:
- self: 自建 app.yaml 格式 (UbuntuRouter 原生)
- 1panel: 1Panel data.yml 格式 (原生，直接使用)
- dockerhub: Docker Hub 镜像自动转换
- portainer: Portainer 模板格式
- composify: 任意 docker-compose.yml 自动推断

使用方式:
    adapter = AppAdapter.create("dockerhub")
    manifest = adapter.convert({"image": "nginx:latest", ...})
"""
import os
import re
import uuid
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any, Type
from dataclasses import dataclass, field

from .engine import AppManifest, _infer_category

logger = logging.getLogger("ubunturouter.appstore.adapter")


# ═══════════════════════════════════════════════════════════════
# 适配器接口
# ═══════════════════════════════════════════════════════════════

class BaseAdapter:
    """适配器基类 — 所有适配器继承此接口"""

    FORMAT_NAME = "base"

    @classmethod
    def detect(cls, source: Any) -> bool:
        """检测是否能够适配该来源"""
        raise NotImplementedError

    def convert(self, source: Any) -> AppManifest:
        """转换为标准 AppManifest"""
        raise NotImplementedError


# ═══════════════════════════════════════════════════════════════
# Docker Hub 适配器
# ═══════════════════════════════════════════════════════════════

class DockerHubAdapter(BaseAdapter):
    """Docker Hub 镜像转换适配器

    输入: {"image": "nginx:latest", "ports": ["80:80"], ...}
    输出: 1Panel 兼容 AppManifest
    """

    FORMAT_NAME = "dockerhub"

    # Docker Hub → 分类/标签 关键词映射
    IMAGE_CATEGORY_MAP = {
        "nginx": ("Web 服务器", ["web", "proxy"]),
        "caddy": ("Web 服务器", ["web", "proxy"]),
        "apache": ("Web 服务器", ["web"]),
        "traefik": ("网络工具", ["proxy", "reverse-proxy"]),
        "haproxy": ("网络工具", ["proxy", "load-balancer"]),
        "mysql": ("数据库", ["database", "sql"]),
        "mariadb": ("数据库", ["database", "sql"]),
        "postgres": ("数据库", ["database", "sql"]),
        "redis": ("缓存", ["cache", "kv"]),
        "mongodb": ("数据库", ["database", "nosql"]),
        "rabbitmq": ("中间件", ["queue", "messaging"]),
        "jenkins": ("开发工具", ["ci/cd", "devops"]),
        "gitlab": ("开发工具", ["git", "ci/cd"]),
        "gitea": ("开发工具", ["git"]),
        "nextcloud": ("NAS", ["cloud", "storage", "file"]),
        "wordpress": ("网站", ["cms", "blog"]),
        "jellyfin": ("多媒体", ["media", "video"]),
        "plex": ("多媒体", ["media", "video"]),
        "prometheus": ("系统监控", ["monitoring", "metrics"]),
        "grafana": ("系统监控", ["monitoring", "dashboard"]),
        "netdata": ("系统监控", ["monitoring"]),
        "portainer": ("网络工具", ["docker", "management"]),
        "adguard": ("网络工具", ["dns", "ad-block"]),
        "pi-hole": ("网络工具", ["dns", "ad-block"]),
        "vaultwarden": ("安全", ["password", "vault"]),
        "bitwarden": ("安全", ["password", "vault"]),
        "syncthing": ("NAS", ["sync", "file"]),
    }

    @classmethod
    def detect(cls, source: Any) -> bool:
        if not isinstance(source, dict):
            return False
        return bool(source.get("image"))

    def convert(self, source: dict) -> AppManifest:
        image = source.get("image", "")
        image_name = image.split(":")[0].split("/")[-1] if "/" in image else image.split(":")[0]

        # 生成 app ID
        app_id = re.sub(r"[^a-zA-Z0-9-]", "-", image_name).strip("-").lower()
        if not app_id:
            app_id = f"docker-{uuid.uuid4().hex[:8]}"

        # 版本
        version = image.split(":")[1] if ":" in image else "latest"

        # 分类和标签
        category, tags = self.IMAGE_CATEGORY_MAP.get(
            image_name, ("其他", ["docker"])
        )

        # 端口映射
        ports = []
        for p in source.get("ports", []):
            if isinstance(p, str):
                m = re.match(r"(\d+):(\d+)(?:/(\w+))?", p)
                if m:
                    ports.append({
                        "container_port": int(m.group(2)),
                        "host_port": int(m.group(1)),
                        "protocol": m.group(3) or "tcp",
                        "label": m.group(2),
                    })
            elif isinstance(p, dict):
                ports.append({
                    "container_port": p.get("target", 0),
                    "host_port": p.get("published", 0),
                    "protocol": p.get("protocol", "tcp"),
                    "label": str(p.get("target", 0)),
                })

        # 环境变量
        env_vars = []
        for ev in source.get("environment", []):
            if isinstance(ev, str):
                if "=" in ev:
                    k, v = ev.split("=", 1)
                    env_vars.append({
                        "name": k, "label": k, "default": v,
                        "type": "text", "required": False,
                    })
            elif isinstance(ev, dict):
                env_vars.append({
                    "name": ev.get("name", ""), "label": ev.get("name", ""),
                    "default": ev.get("value", ""),
                    "type": "text", "required": ev.get("required", False),
                })

        # 数据卷
        volumes = []
        for v in source.get("volumes", []):
            if isinstance(v, str):
                parts = v.split(":")
                if len(parts) >= 2:
                    volumes.append({
                        "container_path": parts[1],
                        "host_path": parts[0],
                        "label": parts[1],
                    })
            elif isinstance(v, dict):
                volumes.append({
                    "container_path": v.get("target", ""),
                    "host_path": v.get("source", ""),
                    "label": v.get("target", ""),
                })

        return AppManifest(
            id=app_id,
            name=source.get("name", image_name),
            version=version,
            versions=[version],
            description=source.get("description", f"来自 Docker Hub 的 {image_name} 镜像"),
            category=category,
            author=source.get("author", ""),
            icon=source.get("icon", ""),
            tags=tags if not source.get("tags") else source["tags"],
            homepage=source.get("homepage", f"https://hub.docker.com/_/{image_name}"),
            env_vars=env_vars,
            ports=ports,
            volumes=volumes,
            compose_file="docker-compose.yml",
        )


# ═══════════════════════════════════════════════════════════════
# Docker Compose 文件适配器
# ═══════════════════════════════════════════════════════════════

class ComposeAdapter(BaseAdapter):
    """docker-compose.yml 文件适配器 — 自动推断为 1Panel 应用"""

    FORMAT_NAME = "compose"

    @classmethod
    def detect(cls, source: Any) -> bool:
        if isinstance(source, Path):
            return source.name in ("docker-compose.yml", "docker-compose.yaml")
        if isinstance(source, str):
            return "services" in source
        if isinstance(source, dict):
            return "services" in source
        return False

    def convert(self, source: Any) -> AppManifest:
        import yaml

        if isinstance(source, Path):
            compose_data = yaml.safe_load(source.read_text())
        elif isinstance(source, str):
            compose_data = yaml.safe_load(source)
        elif isinstance(source, dict):
            compose_data = source
        else:
            raise ValueError(f"Unsupported source type: {type(source)}")

        if not compose_data or "services" not in compose_data:
            raise ValueError("无效的 docker-compose.yml：缺少 services 字段")

        # 从 services 推断应用名
        services = compose_data["services"]
        service_names = list(services.keys())
        main_service = service_names[0] if service_names else "app"

        # 取第一个服务的镜像
        first_svc = services[main_service]
        image = first_svc.get("image", "")
        image_name = image.split("/")[-1].split(":")[0] if image else main_service

        app_id = re.sub(r"[^a-zA-Z0-9-]", "-", image_name).strip("-").lower()
        if not app_id:
            app_id = f"compose-{uuid.uuid4().hex[:8]}"

        version = image.split(":")[1] if ":" in image else "latest"

        # 收集所有端口
        ports = []
        for svc_name, svc_cfg in services.items():
            for p in svc_cfg.get("ports", []):
                if isinstance(p, str):
                    m = re.match(r"(\d+):(\d+)(?:/(\w+))?", p)
                    if m:
                        ports.append({
                            "container_port": int(m.group(2)),
                            "host_port": int(m.group(1)),
                            "protocol": m.group(3) or "tcp",
                            "label": f"{svc_name}:{m.group(2)}",
                        })
                elif isinstance(p, dict):
                    ports.append({
                        "container_port": p.get("target", 0),
                        "host_port": p.get("published", 0),
                        "protocol": p.get("protocol", "tcp"),
                        "label": f"{svc_name}:{p.get('target', 0)}",
                    })

        # 收集环境变量
        env_vars = []
        for svc_name, svc_cfg in services.items():
            for ev in svc_cfg.get("environment", []):
                if isinstance(ev, str) and "=" in ev:
                    k, v = ev.split("=", 1)
                    env_vars.append({
                        "name": k, "label": f"{svc_name}_{k}",
                        "default": v, "type": "text", "required": False,
                    })
                elif isinstance(ev, dict):
                    env_vars.append({
                        "name": ev.get("name", ""),
                        "label": f"{svc_name}_{ev.get('name', '')}",
                        "default": ev.get("value", ""),
                        "type": "text",
                        "required": ev.get("required", False),
                    })

        # 收集数据卷
        volumes = []
        for svc_name, svc_cfg in services.items():
            for vol in svc_cfg.get("volumes", []):
                if isinstance(vol, str):
                    parts = vol.split(":")
                    if len(parts) >= 2:
                        volumes.append({
                            "container_path": parts[1],
                            "host_path": parts[0],
                            "label": f"{svc_name}:{parts[1]}",
                        })
                elif isinstance(vol, dict):
                    volumes.append({
                        "container_path": vol.get("target", ""),
                        "host_path": vol.get("source", ""),
                        "label": f"{svc_name}:{vol.get('target', '')}",
                    })

        # 自动推断分类
        category = _infer_category(image_name)
        description = f"来自 docker-compose.yml 的应用，包含 {len(services)} 个服务: {', '.join(service_names)}"

        return AppManifest(
            id=app_id,
            name=source.get("name", image_name),
            version=version,
            versions=[version],
            description=description,
            category=category,
            icon=source.get("icon", ""),
            tags=["docker-compose"],
            homepage=source.get("homepage", ""),
            env_vars=env_vars,
            ports=ports,
            volumes=volumes,
            compose_file="docker-compose.yml",
            pre_install=source.get("pre_install", ""),
            post_install=source.get("post_install", ""),
        )


# ═══════════════════════════════════════════════════════════════
# 适配器注册表
# ═══════════════════════════════════════════════════════════════

_ADAPTERS: Dict[str, Type[BaseAdapter]] = {}


def register_adapter(adapter_cls: Type[BaseAdapter]) -> Type[BaseAdapter]:
    """注册适配器到全局注册表"""
    name = getattr(adapter_cls, "FORMAT_NAME", adapter_cls.__name__)
    _ADAPTERS[name] = adapter_cls
    logger.info("Registered adapter: %s (%s)", name, adapter_cls.__name__)
    return adapter_cls


def get_adapter(format_name: str) -> Optional[Type[BaseAdapter]]:
    """按格式名获取适配器类"""
    return _ADAPTERS.get(format_name)


def detect_adapter(source: Any) -> Optional[Type[BaseAdapter]]:
    """自动检测可用适配器"""
    for name, adapter_cls in _ADAPTERS.items():
        try:
            if adapter_cls.detect(source):
                return adapter_cls
        except Exception:
            continue
    return None


def convert_app(source: Any, format_name: str = "") -> Optional[AppManifest]:
    """一键转换 — 指定格式或自动检测

    Args:
        source: 应用来源（dict, Path, str）
        format_name: 指定格式名，空则自动检测

    Returns:
        转换后的 AppManifest，失败返回 None
    """
    try:
        if format_name:
            adapter_cls = get_adapter(format_name)
            if not adapter_cls:
                logger.error("Unknown format: %s", format_name)
                return None
            adapter = adapter_cls()
            return adapter.convert(source)

        # 自动检测
        adapter_cls = detect_adapter(source)
        if not adapter_cls:
            logger.warning("No adapter found for source type: %s", type(source).__name__)
            return None
        adapter = adapter_cls()
        return adapter.convert(source)
    except Exception as e:
        logger.error("Conversion failed: %s", e)
        return None


# ── 内置注册 ──────────────────────────────────────────────
register_adapter(DockerHubAdapter)
register_adapter(ComposeAdapter)
