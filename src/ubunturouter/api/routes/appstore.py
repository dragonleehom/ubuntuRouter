"""应用市场 API — 浏览/安装/更新/卸载/仓库管理"""

from fastapi import APIRouter, HTTPException, Query, Body, Depends
from typing import Optional

from ..deps import require_auth
from ...appstore import (
    scan_all_repos, get_installed_apps, get_categories,
    search_apps, install, uninstall, update, precheck,
    list_repos, sync_all_repos, sync_repo, add_repo, remove_repo,
    ensure_official_repo,
)

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════════
# 应用浏览
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/apps")
async def list_apps(
    category: str = Query("", description="分类筛选"),
    search: str = Query("", description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(60, ge=1, le=200, description="每页数量"),
    auth=Depends(require_auth),
):
    """获取应用列表（支持分页、分类筛选、搜索）"""
    # 确保官方仓库已拉取
    ensure_official_repo()

    apps = scan_all_repos()
    installed = get_installed_apps()

    # 标记已安装
    for app_id, manifest in apps.items():
        if app_id in installed:
            manifest.installed = True
            manifest.installed_version = installed[app_id]

    # 分类筛选
    if category:
        apps = {k: v for k, v in apps.items() if v.category == category}

    # 搜索
    if search:
        apps = search_apps(apps, search)

    categories = get_categories(apps)

    # 分页
    sorted_items = sorted(apps.items())
    total = len(sorted_items)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = sorted_items[start:end]

    return {
        "apps": [
            {
                "id": app_id,
                "name": m.name,
                "version": m.version,
                "description": m.description[:200] if m.description else "",
                "category": m.category,
                "author": m.author,
                "icon": m.icon,
                "tags": m.tags,
                "homepage": m.homepage,
                "installed": m.installed,
                "installed_version": m.installed_version,
            }
            for app_id, m in page_items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "categories": categories,
    }


@router.get("/apps/{app_id}")
async def get_app_detail(app_id: str, auth=Depends(require_auth)):
    """获取应用详情"""
    apps = scan_all_repos()
    installed = get_installed_apps()

    if app_id not in apps:
        raise HTTPException(status_code=404, detail=f"应用 '{app_id}' 未找到")

    manifest = apps[app_id]
    manifest.installed = app_id in installed
    manifest.installed_version = installed.get(app_id, "")

    return {
        "app": {
            "id": manifest.id,
            "name": manifest.name,
            "version": manifest.version,
            "description": manifest.description,
            "category": manifest.category,
            "author": manifest.author,
            "icon": manifest.icon,
            "screenshots": manifest.screenshots,
            "tags": manifest.tags,
            "homepage": manifest.homepage,
            "env_vars": manifest.env_vars,
            "ports": manifest.ports,
            "volumes": manifest.volumes,
            "requires": manifest.requires,
            "installed": manifest.installed,
            "installed_version": manifest.installed_version,
            "repo": manifest.repo,
        }
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 应用生命周期
# ═══════════════════════════════════════════════════════════════════════════════

def _check_container_running(app_id: str) -> str:
    """通过 docker ps 检查容器运行状态"""
    import subprocess
    try:
        r = subprocess.run(
            ["docker", "ps", "--filter", f"name=ubunturouter-{app_id}",
             "--format", "{{.Status}}"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            status = r.stdout.strip().lower()
            if "up" in status or "running" in status:
                return "running"
            return "stopped"
    except Exception:
        pass
    return "unknown"


@router.get("/installed")
async def list_installed_apps(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页数量"),
    auth=Depends(require_auth),
):
    """获取已安装应用列表（支持分页）"""
    apps = scan_all_repos()
    installed_ids = get_installed_apps()

    result = []
    for app_id, version in installed_ids.items():
        if app_id in apps:
            manifest = apps[app_id]
            result.append({
                "id": app_id,
                "name": manifest.name,
                "version": version,
                "available_version": manifest.version,
                "has_update": version != manifest.version,
                "category": manifest.category,
                "icon": manifest.icon,
                "description": manifest.description[:200],
                "status": _check_container_running(app_id),
            })
        else:
            result.append({
                "id": app_id,
                "name": app_id,
                "version": version,
                "available_version": "",
                "has_update": False,
                "category": "未知",
                "icon": "",
                "description": "",
            })

    # 分页
    total = len(result)
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "apps": result[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/apps/{app_id}/install")
async def install_app(app_id: str,
                      body: dict = Body({}, description="安装配置"),
                      auth=Depends(require_auth)):
    """安装应用

    支持自定义参数:
    - env: dict — 环境变量
    - custom_volumes: list — 额外卷挂载 [{hostPath, containerPath, mode}]
    - custom_ports: list — 额外端口映射 [{hostPort, containerPort, protocol}]
    """
    apps = scan_all_repos()

    if app_id not in apps:
        raise HTTPException(status_code=404, detail=f"应用 '{app_id}' 未找到")

    manifest = apps[app_id]

    # 预检
    check = precheck(manifest)
    if not check["passed"]:
        raise HTTPException(
            status_code=400,
            detail=f"安装预检未通过: {'; '.join(check['issues'])}",
        )

    env = body.get("env", {})
    custom_volumes = body.get("custom_volumes", [])
    custom_ports = body.get("custom_ports", [])

    # 安装
    result = install(manifest, env_override=env,
                     custom_volumes=custom_volumes,
                     custom_ports=custom_ports)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "安装失败"))

    return result


@router.post("/apps/{app_id}/update")
async def update_app(app_id: str, auth=Depends(require_auth)):
    """更新应用"""
    result = update(app_id)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "更新失败"))
    return result


@router.post("/apps/{app_id}/uninstall")
async def uninstall_app(app_id: str,
                        keep_data: bool = Query(True, description="保留数据"),
                        auth=Depends(require_auth)):
    """卸载应用"""
    result = uninstall(app_id, keep_data=keep_data)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "卸载失败"))
    return result


@router.get("/apps/{app_id}/precheck")
async def precheck_app(app_id: str, auth=Depends(require_auth)):
    """安装前预检"""
    apps = scan_all_repos()
    if app_id not in apps:
        raise HTTPException(status_code=404, detail=f"应用 '{app_id}' 未找到")
    check = precheck(apps[app_id])
    return check


# ═══════════════════════════════════════════════════════════════════════════════
# 仓库管理
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/repo/list")
async def list_repos_api(auth=Depends(require_auth)):
    """列出已配置的仓库"""
    repos = list_repos()
    return {
        "repos": [
            {
                "name": r.name,
                "url": r.url,
                "status": r.status,
                "local_path": str(r.local_path) if r.local_path else "",
            }
            for r in repos
        ],
    }


@router.post("/repo/sync")
async def sync_all_repos_api(auth=Depends(require_auth)):
    """同步所有仓库"""
    results = sync_all_repos()
    return {
        "results": results,
        "total": len(results),
    }


@router.post("/repo/sync/{repo_name}")
async def sync_repo_api(repo_name: str, auth=Depends(require_auth)):
    """同步单个仓库"""
    result = sync_repo(repo_name)
    return result


@router.post("/repo/add")
async def add_repo_api(name: str = Body(...), url: str = Body(...),
                       branch: str = Body("main"),
                       auth=Depends(require_auth)):
    """添加第三方仓库"""
    result = add_repo(name, url, branch)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "添加仓库失败"))
    return result


@router.delete("/repo/{repo_name}")
async def remove_repo_api(repo_name: str, auth=Depends(require_auth)):
    """删除仓库"""
    if repo_name == "official":
        raise HTTPException(status_code=400, detail="不能删除官方仓库")
    result = remove_repo(repo_name)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error", "删除失败"))
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 分类
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/icon/{app_id}")
async def get_app_icon(app_id: str):
    """获取应用图标 (logo.png) — 公开端点，无需认证"""
    import os
    from fastapi.responses import FileResponse

    # 在所有仓库中查找 logo.png
    logo_paths = [
        f"/opt/ubunturouter/apps/repos/official/apps/{app_id}/logo.png",
    ]

    # 也检查已安装目录
    installed_logo = f"/opt/ubunturouter/apps/installed/{app_id}/logo.png"

    for lp in [*logo_paths, installed_logo]:
        if os.path.exists(lp):
            return FileResponse(lp, media_type="image/png")

    raise HTTPException(status_code=404, detail="图标未找到")


@router.get("/categories")
async def list_categories(auth=Depends(require_auth)):
    """获取所有应用分类"""
    apps = scan_all_repos()
    categories = get_categories(apps)
    return {"categories": categories}
