"""容器管理 API — 容器 CRUD + Compose 项目管理"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from pydantic import BaseModel

from ..deps import require_auth
from ...container import ContainerManager, ComposeManager

router = APIRouter()


class ExecRequest(BaseModel):
    """容器内执行命令请求"""
    cmd: str
    shell: str = "/bin/sh"


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


@router.delete("/images/{image_id}")
async def remove_image(image_id: str, force: bool = False, auth=Depends(require_auth)):
    """删除镜像"""
    success = ContainerManager.remove_image(image_id, force=force)
    if not success:
        raise HTTPException(status_code=500, detail=f"删除镜像 '{image_id}' 失败")
    return {"message": f"镜像 '{image_id}' 已删除"}


@router.get("/images/{image_id}/inspect")
async def inspect_image(image_id: str, auth=Depends(require_auth)):
    """查看镜像详情"""
    data = ContainerManager.inspect_image(image_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"镜像 '{image_id}' 未找到")
    layers = data.get("RootFS", {}).get("Layers", [])
    exposed_ports = list(data.get("Config", {}).get("ExposedPorts", {}).keys()) or []
    env = data.get("Config", {}).get("Env", [])
    return {
        "image": {
            "id": data.get("Id", ""),
            "repo_tags": data.get("RepoTags", []),
            "size_str": _format_size(data.get("Size", 0)),
            "architecture": data.get("Architecture", ""),
            "os": data.get("Os", ""),
            "layers": len(layers),
            "exposed_ports": exposed_ports,
            "env": env,
        }
    }


@router.post("/images/prune")
async def prune_images(all: bool = False, auth=Depends(require_auth)):
    """清理未使用的镜像"""
    result = ContainerManager.prune_images(all=all)
    reclaimed = result.get("reclaimed", "")
    reclaimed_str = str(reclaimed) if reclaimed else "0 B"
    return {
        "message": "清理完成",
        "reclaimed": result.get("reclaimed", ""),
        "reclaimed_str": reclaimed_str,
        "success": result.get("success", False),
    }


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


@router.post("/{container_id}/exec")
async def exec_in_container(container_id: str, req: ExecRequest, auth=Depends(require_auth)):
    """在容器内执行命令"""
    result = ContainerManager.exec_run(container_id, req.cmd, req.shell)
    return {
        "container_id": container_id,
        "exit_code": result["exit_code"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
    }


@router.get("/{container_id}/inspect")
async def inspect_container(container_id: str, auth=Depends(require_auth)):
    """获取容器详细配置信息"""
    data = ContainerManager.inspect_container(container_id)
    if not data:
        raise HTTPException(status_code=404, detail="容器未找到")
    return {"inspect": data}


@router.get("/app-open")
async def list_app_open(auth=Depends(require_auth)):
    """扫描运行容器暴露的HTTP端口"""
    containers = ContainerManager.list_containers(all=False)
    apps = []
    for c in containers:
        if c.status != "running":
            continue
        if not c.ports:
            continue
        for p in c.ports:
            host_port = p.get("host_port")
            if host_port:
                apps.append({
                    "container_id": c.id,
                    "container_name": c.name,
                    "image": c.image,
                    "port": host_port,
                    "url": f"http://localhost:{host_port}",
                })
    return {"apps": apps}


@router.get("/app-open/{container_id}")
async def get_container_app_open(container_id: str, auth=Depends(require_auth)):
    """获取单个容器暴露的HTTP端口"""
    c = ContainerManager.get_container(container_id)
    if not c:
        raise HTTPException(status_code=404, detail="容器未找到")
    if c.status != "running":
        return {"url": None, "message": "容器未运行"}
    if not c.ports:
        return {"url": None, "message": "容器未暴露端口"}
    host_port = c.ports[0].get("host_port")
    if host_port:
        return {"url": f"http://localhost:{host_port}", "port": host_port}
    return {"url": None, "message": "未检测到HTTP端口"}


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
