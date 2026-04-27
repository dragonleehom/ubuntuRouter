"""App Store 引擎 — Manifest 解析 + 应用目录树扫描"""

import os
import re
import yaml
from pathlib import Path
from typing import List, Optional, Dict
from dataclasses import dataclass, field


# ─── 默认仓库路径 ─────────────────────────────────────────────────────────────
APPS_BASE = Path("/opt/ubunturouter/apps")
REPOS_DIR = APPS_BASE / "repos"
INSTALLED_DIR = APPS_BASE / "installed"
DATA_DIR = APPS_BASE / "data"
OFFICIAL_REPO = "https://github.com/ubuntu-router/apps-official"

# ─── 支持的仓库格式 ────────────────────────────────────────────────────────────
# 每种格式对应一组解析器和目录探测器
REPO_FORMATS = {
    "self": {
        "label": "自建格式 (app.yaml)",
        "manifest_file": "app.yaml",
    },
    "1panel": {
        "label": "1Panel 格式 (data.yml)",
        "manifest_file": "data.yml",
    },
}


@dataclass
class AppManifest:
    """应用 Manifest (app.yaml)"""
    id: str                        # 应用唯一 ID，如 "adguard-home"
    name: str                      # 显示名称
    version: str                   # 当前版本
    description: str = ""
    category: str = "其他"         # 分类
    author: str = ""
    icon: str = ""                 # 图标 URL 或路径
    screenshots: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    homepage: str = ""
    min_router_version: str = "0.1.0"

    # 配置参数
    env_vars: List[Dict] = field(default_factory=list)
    ports: List[Dict] = field(default_factory=list)
    volumes: List[Dict] = field(default_factory=list)
    requires: List[str] = field(default_factory=list)  # 依赖的应用

    # Compose 相关
    compose_file: str = "docker-compose.yml"
    pre_install: str = ""          # 预安装脚本（可选）
    post_install: str = ""         # 安装后脚本（可选）

    repo: str = ""                 # 来源仓库
    path: str = ""                 # 文件系统路径
    installed: bool = False        # 是否已安装
    installed_version: str = ""    # 已安装版本

    @property
    def format(self) -> str:
        """推断来源格式"""
        return ""


def parse_manifest(manifest_path: Path) -> Optional[AppManifest]:
    """解析 app.yaml 文件（自建格式）"""
    if not manifest_path.exists():
        return None

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError):
        return None

    if not data or not isinstance(data, dict):
        return None

    app_id = data.get("id", manifest_path.parent.name)

    # 解析 env_vars
    env_vars = []
    for ev in data.get("env_vars", []):
        if isinstance(ev, dict):
            env_vars.append({
                "name": ev.get("name", ""),
                "label": ev.get("label", ev.get("name", "")),
                "description": ev.get("description", ""),
                "default": ev.get("default", ""),
                "required": ev.get("required", False),
                "type": ev.get("type", "string"),
            })

    # 解析 ports
    ports = []
    for p in data.get("ports", []):
        if isinstance(p, dict):
            ports.append({
                "container_port": p.get("container_port", 0),
                "host_port": p.get("host_port", 0),
                "protocol": p.get("protocol", "tcp"),
                "label": p.get("label", ""),
            })

    # 解析 volumes
    volumes = []
    for v in data.get("volumes", []):
        if isinstance(v, dict):
            volumes.append({
                "container_path": v.get("container_path", ""),
                "host_path": v.get("host_path", ""),
                "label": v.get("label", ""),
            })

    return AppManifest(
        id=app_id,
        name=data.get("name", app_id),
        version=data.get("version", "0.0.0"),
        description=data.get("description", ""),
        category=data.get("category", "其他"),
        author=data.get("author", ""),
        icon=data.get("icon", ""),
        screenshots=data.get("screenshots", []),
        tags=data.get("tags", []),
        homepage=data.get("homepage", ""),
        min_router_version=data.get("min_router_version", "0.1.0"),
        env_vars=env_vars,
        ports=ports,
        volumes=volumes,
        requires=data.get("requires", []),
        compose_file=data.get("compose_file", "docker-compose.yml"),
        pre_install=data.get("pre_install", ""),
        post_install=data.get("post_install", ""),
    )


def _extract_ports_from_compose(compose_path: Path) -> List[Dict]:
    """从 docker-compose.yml 提取端口映射"""
    ports = []
    if not compose_path.exists():
        return ports
    try:
        with open(compose_path, "r", encoding="utf-8") as cf:
            compose_data = yaml.safe_load(cf)
        services = compose_data.get("services", {})
        for svc_name, svc_cfg in services.items():
            svc_ports = svc_cfg.get("ports", [])
            for p in svc_ports:
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
    except Exception:
        pass
    return ports


def _extract_volumes_from_compose(compose_path: Path) -> List[Dict]:
    """从 docker-compose.yml 提取数据卷"""
    volumes = []
    if not compose_path.exists():
        return volumes
    try:
        with open(compose_path, "r", encoding="utf-8") as cf:
            compose_data = yaml.safe_load(cf)
        services = compose_data.get("services", {})
        for svc_name, svc_cfg in services.items():
            svc_volumes = svc_cfg.get("volumes", [])
            for vol in svc_volumes:
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
    except Exception:
        pass
    return volumes


_CATEGORY_I18N = {
    "database": "数据库", "tool": "工具", "runtime": "运行环境",
    "middleware": "中间件", "storage": "存储", "network": "网络",
    "business": "商业软件", "website": "网站",
    "monitor": "系统监控", "download": "下载工具", "nas": "NAS",
    "service": "服务", "messaging": "消息通讯", "server": "服务器",
    "multimedia": "多媒体", "ai": "人工智能", "networking": "网络工具",
    "security": "安全", "development": "开发工具",
}


def parse_onepanel_manifest(manifest_path: Path) -> Optional[AppManifest]:
    """解析 1Panel 应用 data.yml 格式"""
    if not manifest_path.exists():
        return None

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError):
        return None

    if not data or not isinstance(data, dict):
        return None

    # 路径: .../apps/{app_name}/{version}/data.yml
    parent_name = manifest_path.parent.name      # version 目录
    grandparent = manifest_path.parent.parent     # app 目录
    app_id = grandparent.name if grandparent.exists() else parent_name

    name = data.get("title", data.get("name", app_id))
    description = data.get("description", "")
    version = data.get("version", parent_name)

    # 分类
    additional_props = data.get("additionalProperties", data.get("additional_properties", {}))
    category = "其他"
    if isinstance(additional_props, dict):
        category = additional_props.get("type", data.get("type", "其他"))
    category = _CATEGORY_I18N.get(category, category)

    icon = data.get("icon", "")
    if icon and not icon.startswith("http"):
        icon = ""
    homepage = data.get("website", "")
    author = data.get("author", "")
    tags = data.get("tags", [])

    compose_path = manifest_path.parent / "docker-compose.yml"
    ports = _extract_ports_from_compose(compose_path)

    # 环境变量
    env_vars = []
    if isinstance(additional_props, dict):
        for field in additional_props.get("formFields", []):
            if isinstance(field, dict):
                field_type = field.get("type", "input")
                env_vars.append({
                    "name": field.get("envKey", field.get("key", "")),
                    "label": field.get("labelZh", field.get("label", "")),
                    "description": field.get("placeholder", field.get("description", "")),
                    "default": field.get("default", ""),
                    "required": field.get("required", False),
                    "type": {
                        "password": "password", "number": "number",
                        "checkbox": "boolean", "switch": "boolean", "select": "select",
                    }.get(field_type, "string"),
                    "options": field.get("options", field.get("children", [])),
                })

    volumes = _extract_volumes_from_compose(compose_path)

    return AppManifest(
        id=app_id,
        name=name,
        version=version or "0.0.0",
        description=description,
        category=category,
        author=author,
        icon=icon,
        tags=tags,
        homepage=homepage,
        env_vars=env_vars,
        ports=ports,
        volumes=volumes,
        compose_file="docker-compose.yml",
    )


# ═══════════════════════════════════════════════════════════════════════════
# 格式探测器：检测仓库使用的是哪种格式
# ═══════════════════════════════════════════════════════════════════════════

def _detect_repo_format(repo_path: Path) -> Optional[str]:
    """自动检测仓库格式
    
    返回值: 'self', '1panel', 或 None（未识别）
    """
    if not repo_path.exists():
        return None

    # 自建格式: 根目录有子目录含 app.yaml
    for item in repo_path.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            if (item / "app.yaml").exists():
                return "self"

    # 1Panel 格式: apps/{app_name}/{version}/data.yml
    apps_dir = repo_path / "apps" if repo_path.name != "apps" else repo_path
    if apps_dir.exists() and apps_dir.is_dir():
        for app in apps_dir.iterdir():
            if app.is_dir() and not app.name.startswith("."):
                for item in app.iterdir():
                    if item.is_dir() and (item / "data.yml").exists():
                        return "1panel"
                    if item.name == "data.yml":
                        return "1panel"

    return None


# ═══════════════════════════════════════════════════════════════════════════
# 扫描器：根据格式选择解析策略
# ═══════════════════════════════════════════════════════════════════════════

def _scan_self_format(repo_path: Path) -> Dict[str, AppManifest]:
    """扫描自建格式仓库 (app.yaml)"""
    apps = {}
    for item in sorted(repo_path.iterdir()):
        if not item.is_dir() or item.name.startswith("."):
            continue
        manifest_file = item / "app.yaml"
        if not manifest_file.exists():
            continue
        manifest = parse_manifest(manifest_file)
        if manifest:
            manifest.repo = repo_path.name
            manifest.path = str(item)
            apps[manifest.id] = manifest
    return apps


def _scan_onepanel_format(repo_path: Path) -> Dict[str, AppManifest]:
    """扫描 1Panel 格式仓库 (data.yml)"""
    apps = {}
    apps_dir = repo_path / "apps" if repo_path.name != "apps" else repo_path
    for app_dir in sorted(apps_dir.iterdir()):
        if not app_dir.is_dir() or app_dir.name.startswith("."):
            continue
        # 取最新版本目录
        versions = sorted([
            d for d in app_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ], reverse=True)
        if versions:
            manifest_file = versions[0] / "data.yml"
        else:
            manifest_file = app_dir / "data.yml"
        if manifest_file.exists():
            manifest = parse_onepanel_manifest(manifest_file)
            if manifest:
                manifest.repo = repo_path.name
                manifest.path = str(manifest_file.parent)
                apps[manifest.id] = manifest
    return apps


_FORMAT_SCANNERS = {
    "self": _scan_self_format,
    "1panel": _scan_onepanel_format,
}


def scan_apps(repo_path: Path) -> Dict[str, AppManifest]:
    """扫描仓库目录, 自动检测格式并返回应用字典"""
    apps = {}
    if not repo_path.exists():
        return apps

    fmt = _detect_repo_format(repo_path)
    scanner = _FORMAT_SCANNERS.get(fmt) if fmt else None
    if scanner:
        apps = scanner(repo_path)
    # fmt 为 None 时返回空字典

    return apps


def scan_all_repos() -> Dict[str, AppManifest]:
    """扫描所有仓库, 返回合并的应用字典"""
    all_apps = {}
    if not REPOS_DIR.exists():
        return all_apps

    for repo_dir in REPOS_DIR.iterdir():
        if not repo_dir.is_dir() or repo_dir.name.startswith("."):
            continue
        apps = scan_apps(repo_dir)
        for app_id, manifest in apps.items():
            if app_id in all_apps:
                continue
            all_apps[app_id] = manifest

    return all_apps


def get_installed_apps() -> Dict[str, str]:
    """获取已安装的应用列表 {app_id: version}"""
    installed = {}
    if not INSTALLED_DIR.exists():
        return installed

    for item in INSTALLED_DIR.iterdir():
        if not item.is_symlink() and not item.is_dir():
            continue
        manifest_file = item / "app.yaml"
        if manifest_file.exists():
            manifest = parse_manifest(manifest_file)
            if manifest:
                installed[manifest.id] = manifest.version
        else:
            installed[item.name] = "unknown"

    return installed


def get_categories(apps: Dict[str, AppManifest]) -> List[str]:
    """获取所有分类"""
    cats = set()
    for app in apps.values():
        cats.add(app.category)
    return sorted(cats)


def search_apps(apps: Dict[str, AppManifest], query: str) -> Dict[str, AppManifest]:
    """搜索应用（按名称、描述、标签）"""
    if not query:
        return apps

    query = query.lower()
    result = {}
    for app_id, manifest in apps.items():
        if (query in app_id.lower() or
                query in manifest.name.lower() or
                query in manifest.description.lower() or
                any(query in tag.lower() for tag in manifest.tags)):
            result[app_id] = manifest
    return result
