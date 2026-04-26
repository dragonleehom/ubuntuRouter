"""容器管理 API — 容器 CRUD + Compose 项目管理"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional

from ..deps import require_auth
from ...container import ContainerManager, ComposeManager

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════════
# 镜像管理（必须在 /{container_id} 之前注册）
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/images/list")
async def list_images(auth=Depends(require_auth)):
    """列出本地镜像"""
    images = ContainerManager.list_images()
    return {
        "images": [
            {
                "id": img.id,
                "repo_tags": img.repo_tags,
                "size": img.size,
                "size_human": _format_size(img.size),
                "created": img.created,
            }
            for img in images
        ],
        "total": len(images),
    }


@router.post("/images/pull")
async def pull_image(image: str, auth=Depends(require_auth)):
    """拉取镜像"""
    success = ContainerManager.pull_image(image)
    if not success:
        raise HTTPException(status_code=500, detail=f"拉取镜像 '{image}' 失败")
    return {"message": f"镜像 '{image}' 拉取完成"}


# ═══════════════════════════════════════════════════════════════════════════════
# 容器管理
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/")
async def list_containers(all: bool = Query(True, description="包含已停止的容器"),
                          auth=Depends(require_auth)):
    """获取容器列表"""
    containers = ContainerManager.list_containers(all=all)
    return {
        "containers": [
            {
                "id": c.id,
                "name": c.name,
                "image": c.image,
                "status": c.status,
                "state": c.state,
                "created": c.created,
                "ports": c.ports,
                "mounts": c.mounts,
                "networks": c.networks,
                "compose_project": c.compose_project,
            }
            for c in containers
        ],
        "total": len(containers),
    }


@router.get("/{container_id}")
async def get_container(container_id: str, auth=Depends(require_auth)):
    """获取容器详情"""
    container = ContainerManager.get_container(container_id)
    if not container:
        # 尝试 inspect
        inspect_data = ContainerManager.inspect_container(container_id)
        if not inspect_data:
            raise HTTPException(status_code=404, detail="容器未找到")
        return {"container": inspect_data}

    return {
        "container": {
            "id": container.id,
            "name": container.name,
            "image": container.image,
            "status": container.status,
            "state": container.state,
            "created": container.created,
            "ports": container.ports,
            "mounts": container.mounts,
            "networks": container.networks,
            "compose_project": container.compose_project,
        }
    }


@router.post("/{container_id}/start")
async def start_container(container_id: str, auth=Depends(require_auth)):
    """启动容器"""
    success = ContainerManager.start(container_id)
    if not success:
        raise HTTPException(status_code=500, detail="启动失败")
    return {"message": "容器已启动", "container_id": container_id}


@router.post("/{container_id}/stop")
async def stop_container(container_id: str, auth=Depends(require_auth)):
    """停止容器"""
    success = ContainerManager.stop(container_id)
    if not success:
        raise HTTPException(status_code=500, detail="停止失败")
    return {"message": "容器已停止", "container_id": container_id}


@router.post("/{container_id}/restart")
async def restart_container(container_id: str, auth=Depends(require_auth)):
    """重启容器"""
    success = ContainerManager.restart(container_id)
    if not success:
        raise HTTPException(status_code=500, detail="重启失败")
    return {"message": "容器已重启", "container_id": container_id}


@router.delete("/{container_id}")
async def remove_container(container_id: str, force: bool = False,
                           volumes: bool = False, auth=Depends(require_auth)):
    """删除容器"""
    success = ContainerManager.remove(container_id, force=force, volumes=volumes)
    if not success:
        raise HTTPException(status_code=500, detail="删除失败")
    return {"message": "容器已删除", "container_id": container_id}


@router.get("/{container_id}/logs")
async def get_container_logs(container_id: str,
                             tail: int = Query(100, ge=1, le=5000),
                             auth=Depends(require_auth)):
    """获取容器日志"""
    logs = ContainerManager.logs(container_id, tail=tail)
    return {"container_id": container_id, "logs": logs}


@router.get("/{container_id}/stats")
async def get_container_stats(container_id: str, auth=Depends(require_auth)):
    """获取容器资源统计"""
    # 如果没有指定容器，返回所有
    if container_id == "all":
        stats = ContainerManager.stats()
    else:
        stats = [s for s in ContainerManager.stats() if s["container_id"].startswith(container_id)]
    return {"stats": stats}


# ═══════════════════════════════════════════════════════════════════════════════
# Compose 项目管理
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/compose/projects")
async def list_compose_projects(auth=Depends(require_auth)):
    """获取 Compose 项目列表"""
    projects = ComposeManager.get_projects()
    return {
        "projects": [
            {
                "name": p.name,
                "status": p.status,
                "services": p.services,
                "config_files": p.config_files,
            }
            for p in projects
        ],
        "total": len(projects),
    }


@router.get("/compose/{project_name}/logs")
async def get_compose_logs(project_name: str,
                           tail: int = Query(100, ge=1, le=5000),
                           service: str = "",
                           auth=Depends(require_auth)):
    """获取 Compose 项目日志"""
    project_dir = f"/opt/ubunturouter/apps/installed/{project_name}"
    logs = ComposeManager.logs(project_dir, tail=tail, service=service)
    return {"project": project_name, "logs": logs}


@router.post("/compose/{project_name}/restart")
async def restart_compose_project(project_name: str, service: str = "",
                                  auth=Depends(require_auth)):
    """重启 Compose 项目"""
    project_dir = f"/opt/ubunturouter/apps/installed/{project_name}"
    success = ComposeManager.restart(project_dir, service=service)
    if not success:
        raise HTTPException(status_code=500, detail="重启失败")
    return {"message": f"项目 '{project_name}' 已重启"}


@router.post("/compose/{project_name}/pull")
async def pull_compose_images(project_name: str, auth=Depends(require_auth)):
    """拉取 Compose 项目的新镜像"""
    project_dir = f"/opt/ubunturouter/apps/installed/{project_name}"
    result = ComposeManager.pull(project_dir)
    return result


def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size}B"
    elif size < 1024 ** 2:
        return f"{size/1024:.1f}KB"
    elif size < 1024 ** 3:
        return f"{size/1024**2:.1f}MB"
    else:
        return f"{size/1024**3:.1f}GB"
