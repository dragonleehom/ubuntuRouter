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
OFFICIAL_REPO = "https://github.com/1Panel-dev/appstore"
# 1Panel 兼容模式: 使用 data.yml 替代 app.yaml
ONEPANEL_MODE = True


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


def parse_onepanel_manifest(manifest_path: Path) -> Optional[AppManifest]:
    """解析 1Panel 应用 data.yml 格式"""
    if not manifest_path.exists():
        return None

    # 1Panel 目录结构: apps/{category}/{app_name}/{version}/data.yml
    # data.yml 包含: additionalProperties, docker-compose 等
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError):
        return None

    if not data or not isinstance(data, dict):
        return None

    # 应用 ID 从目录名推导: app_relative_path 的最后一个部分
    app_relative = manifest_path.relative_to(manifest_path.parent.parent.parent) if len(manifest_path.parent.parent.parents) > 1 else manifest_path.parent.name
    app_id = manifest_path.parent.name

    # 1Panel data.yml 结构与 AppManifest 互转
    name = data.get("name", app_id)
    description = data.get("description", "")
    version = data.get("version", "0.0.0")
    # 分类从目录结构中推断 (apps/{category}/...)
    category = "其他"
    try:
        category_dir = manifest_path.parent.parent.parent.name
        CATEGORY_MAP = {
            "database": "数据库", "tool": "工具", "runtime": "运行环境",
            "middleware": "中间件", "storage": "存储", "network": "网络",
        }
        category = CATEGORY_MAP.get(category_dir, category_dir)
    except (IndexError, AttributeError):
        pass

    # 图标: 1Panel 的 icon 字段或默认路径
    icon = data.get("icon", "")
    if icon and not icon.startswith("http"):
        icon = ""

    # 主页
    homepage = data.get("website", "")
    author = data.get("author", "")
    tags = data.get("tags", [])

    # 其他自定义属性
    additional_props = data.get("additionalProperties", data.get("additional_properties", {}))

    # 端口探查 (从 docker-compose 提取)
    ports = []
    compose_path = manifest_path.parent / "docker-compose.yml"
    if compose_path.exists():
        try:
            with open(compose_path, "r", encoding="utf-8") as cf:
                compose_data = yaml.safe_load(cf)
            services = compose_data.get("services", {})
            for svc_name, svc_cfg in services.items():
                svc_ports = svc_cfg.get("ports", [])
                for p in svc_ports:
                    if isinstance(p, str):
                        # "8080:80/tcp" 格式
                        import re as _re
                        m = _re.match(r"(\d+):(\d+)(?:/(\w+))?", p)
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

    # 环境变量 (从 additionalProperties 的 form 中提取)
    env_vars = []
    if isinstance(additional_props, dict):
        form_fields = additional_props.get("formFields", [])
        for field in form_fields:
            if isinstance(field, dict):
                field_type = field.get("type", "input")
                env_vars.append({
                    "name": field.get("envKey", field.get("key", "")),
                    "label": field.get("labelZh", field.get("label", "")),
                    "description": field.get("placeholder", field.get("description", "")),
                    "default": field.get("default", ""),
                    "required": field.get("required", False),
                    "type": {
                        "password": "password",
                        "number": "number",
                        "checkbox": "boolean",
                        "switch": "boolean",
                        "select": "select",
                    }.get(field_type, "string"),
                    "options": field.get("options", field.get("children", [])),
                })

    # 数据卷 (从 docker-compose volumes 提取)
    volumes = []
    if compose_path.exists():
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


def scan_apps(repo_path: Path) -> Dict[str, AppManifest]:
    """扫描仓库目录, 返回 {app_id: AppManifest}
    
    支持两种格式:
    - app.yaml (自建格式)
    - data.yml (1Panel 格式, 路径: {repo}/{category}/{app}/{version}/data.yml)
    """
    apps = {}
    if not repo_path.exists():
        return apps

    # 检测是否为 1Panel 仓库 (apps/{category}/{app}/{version}/data.yml 结构)
    is_onepanel = _detect_onepanel_repo(repo_path)

    if is_onepanel:
        # 1Panel 格式: apps/{app_name}/{version}/data.yml 或 apps/{app_name}/data.yml
        apps_dir = repo_path / "apps" if repo_path.name != "apps" else repo_path
        for app_dir in sorted(apps_dir.iterdir()):
            if not app_dir.is_dir() or app_dir.name.startswith("."):
                continue
            # 取最新版本: 有 version 子目录则取最后一个，否则取 data.yml
            versions = sorted([
                d for d in app_dir.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            ], reverse=True)
            if versions:
                latest = versions[0]
                manifest_file = latest / "data.yml"
            else:
                # 无版本子目录，直接在 app 目录下
                manifest_file = app_dir / "data.yml"
            if manifest_file.exists():
                manifest = parse_onepanel_manifest(manifest_file)
                if manifest:
                    manifest.repo = repo_path.name
                    manifest.path = str(manifest_file.parent)
                    apps[manifest.id] = manifest
    else:
        # 自建格式: {app_name}/app.yaml
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


def _detect_onepanel_repo(repo_path: Path) -> bool:
    """检测是否为 1Panel 格式仓库"""
    if not repo_path.exists():
        return False
    # 1Panel 仓库结构: apps/{app_name}/{version}/data.yml 或 apps/{app_name}/data.yml
    apps_dir = repo_path / "apps" if repo_path.name != "apps" else repo_path
    if not apps_dir.exists() or not apps_dir.is_dir():
        return False
    for app in apps_dir.iterdir():
        if app.is_dir() and not app.name.startswith("."):
            # 检查 {app}/{version}/data.yml 或 {app}/data.yml
            for item in app.iterdir():
                if item.is_dir():
                    if (item / "data.yml").exists():
                        return True
                elif item.name == "data.yml":
                    return True
    return False


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
