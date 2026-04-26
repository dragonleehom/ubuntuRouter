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


def parse_manifest(manifest_path: Path) -> Optional[AppManifest]:
    """解析 app.yaml 文件"""
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
                "type": ev.get("type", "string"),  # string / password / number / boolean
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


def scan_apps(repo_path: Path) -> Dict[str, AppManifest]:
    """扫描仓库目录, 返回 {app_id: AppManifest}"""
    apps = {}
    if not repo_path.exists():
        return apps

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
                # 同名冲突: 按仓库优先级覆盖
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
        # 读取 manifest 获取版本
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
