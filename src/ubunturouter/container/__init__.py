"""Docker Engine API 封装 — 通过 docker-py 或 subprocess 调 Docker socket"""

import json
import subprocess
import re
import time
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from pathlib import Path


DOCKER_BIN = "/usr/bin/docker"
COMPOSE_BIN = "/usr/bin/docker"

# ─── 数据类型 ────────────────────────────────────────────────────────────────

@dataclass
class ContainerInfo:
    id: str
    name: str
    image: str
    status: str          # running / exited / paused
    state: str           # 完整状态字符串
    created: str
    ports: List[Dict] = field(default_factory=list)
    mounts: List[Dict] = field(default_factory=list)
    networks: List[str] = field(default_factory=list)
    compose_project: Optional[str] = None


@dataclass
class ImageInfo:
    id: str
    repo_tags: List[str]
    size: int
    created: str


@dataclass
class ComposeProjectInfo:
    name: str
    status: str          # running / stopped / partial
    services: List[Dict] = field(default_factory=list)
    config_files: List[str] = field(default_factory=list)


# ─── 辅助 ────────────────────────────────────────────────────────────────────

def _run(cmd: List[str], timeout: int = 60) -> subprocess.CompletedProcess:
    """运行 docker 命令并返回结果"""
    full_cmd = [DOCKER_BIN] + cmd
    r = subprocess.run(
        full_cmd,
        capture_output=True, text=True, timeout=timeout
    )
    return r


def _run_compose(cmd: List[str], project_dir: str = "",
                 timeout: int = 120) -> subprocess.CompletedProcess:
    """运行 docker compose 命令"""
    full_cmd = [COMPOSE_BIN, "compose"]
    if project_dir:
        full_cmd += ["--project-directory", project_dir]
    full_cmd += cmd
    r = subprocess.run(
        full_cmd,
        capture_output=True, text=True, timeout=timeout
    )
    return r


def _now_ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())


# ═══════════════════════════════════════════════════════════════════════════════
# 容器管理
# ═══════════════════════════════════════════════════════════════════════════════

class ContainerManager:
    """Docker 容器 CRUD + 生命周期管理"""

    @staticmethod
    def list_containers(all: bool = True) -> List[ContainerInfo]:
        """获取容器列表"""
        cmd = ["ps", "--format", "{{json .}}"]
        if all:
            cmd.append("-a")
        r = _run(cmd)
        if r.returncode != 0:
            return []

        containers = []
        for line in r.stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                # 解析端口映射
                ports = []
                port_str = data.get("Ports", "")
                if port_str:
                    for part in port_str.split(", "):
                        part = part.strip()
                        if not part:
                            continue
                        # 格式: 0.0.0.0:8080->80/tcp 或 80/tcp
                        m = re.match(r"(?:[\d.]+:)?(\d+)->(\d+)/(\w+)", part)
                        if m:
                            ports.append({
                                "host_port": int(m.group(1)),
                                "container_port": int(m.group(2)),
                                "protocol": m.group(3),
                            })

                # 解析挂载
                mounts = []
                mount_str = data.get("Mounts", "")
                if mount_str:
                    for mnt in mount_str.split(", "):
                        mnt = mnt.strip()
                        if ":" in mnt:
                            parts = mnt.split(":")
                            mounts.append({
                                "source": parts[0],
                                "destination": parts[1] if len(parts) > 1 else "",
                            })

                # 提取 compose 项目
                labels = data.get("Labels", "")
                compose_project = None
                if "com.docker.compose.project=" in labels:
                    m = re.search(r"com\.docker\.compose\.project=([^\s,]+)", labels)
                    if m:
                        compose_project = m.group(1)

                containers.append(ContainerInfo(
                    id=data.get("ID", "")[:12],
                    name=data.get("Names", "").lstrip("/"),
                    image=data.get("Image", ""),
                    status=data.get("State", ""),
                    state=data.get("Status", ""),
                    created=data.get("CreatedAt", ""),
                    ports=ports,
                    mounts=mounts,
                    networks=[n.strip() for n in data.get("Networks", "").split(",") if n.strip()],
                    compose_project=compose_project,
                ))
            except (json.JSONDecodeError, KeyError):
                continue

        return containers

    @staticmethod
    def get_container(container_id: str) -> Optional[ContainerInfo]:
        """获取单个容器详情"""
        for c in ContainerManager.list_containers(all=True):
            if c.id == container_id or c.name == container_id:
                return c
        return None

    @staticmethod
    def inspect_container(container_id: str) -> Optional[Dict]:
        """获取容器详细配置"""
        r = _run(["inspect", container_id])
        if r.returncode != 0:
            return None
        try:
            data = json.loads(r.stdout)
            if data:
                return data[0]
        except (json.JSONDecodeError, IndexError):
            pass
        return None

    @staticmethod
    def start(container_id: str) -> bool:
        """启动容器"""
        r = _run(["start", container_id])
        return r.returncode == 0

    @staticmethod
    def stop(container_id: str, timeout: int = 10) -> bool:
        """停止容器"""
        r = _run(["stop", "-t", str(timeout), container_id])
        return r.returncode == 0

    @staticmethod
    def restart(container_id: str, timeout: int = 10) -> bool:
        """重启容器"""
        r = _run(["restart", "-t", str(timeout), container_id])
        return r.returncode == 0

    @staticmethod
    def remove(container_id: str, force: bool = False, volumes: bool = False) -> bool:
        """删除容器"""
        cmd = ["rm"]
        if force:
            cmd.append("-f")
        if volumes:
            cmd.append("-v")
        cmd.append(container_id)
        r = _run(cmd)
        return r.returncode == 0

    @staticmethod
    def logs(container_id: str, tail: int = 100, timestamps: bool = False) -> str:
        """获取容器日志"""
        cmd = ["logs", "--tail", str(tail)]
        if timestamps:
            cmd.append("-t")
        cmd.append(container_id)
        r = _run(cmd, timeout=30)
        if r.returncode != 0:
            return r.stderr
        return r.stdout

    @staticmethod
    def stats() -> List[Dict]:
        """获取容器资源统计"""
        r = _run(["stats", "--no-stream", "--format", "{{json .}}"], timeout=30)
        if r.returncode != 0:
            return []
        stats = []
        for line in r.stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                stats.append({
                    "container_id": data.get("ID", "")[:12],
                    "name": data.get("Name", ""),
                    "cpu_percent": data.get("CPUPerc", "0%"),
                    "mem_usage": data.get("MemUsage", "0B / 0B"),
                    "mem_percent": data.get("MemPerc", "0%"),
                    "net_io": data.get("NetIO", "0B / 0B"),
                    "block_io": data.get("BlockIO", "0B / 0B"),
                    "pid": data.get("PIDs", "0"),
                })
            except json.JSONDecodeError:
                continue
        return stats

    @staticmethod
    def pull_image(image: str) -> bool:
        """拉取镜像"""
        r = _run(["pull", image], timeout=300)
        return r.returncode == 0

    @staticmethod
    def list_images() -> List[ImageInfo]:
        """列出镜像"""
        r = _run(["images", "--format", "{{json .}}"])
        if r.returncode != 0:
            return []
        images = []
        for line in r.stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                images.append(ImageInfo(
                    id=data.get("ID", ""),
                    repo_tags=[f"{data.get('Repository', '')}:{data.get('Tag', 'latest')}"],
                    size=_parse_size(data.get("Size", "0")),
                    created=data.get("CreatedAt", ""),
                ))
            except json.JSONDecodeError:
                continue
        return images


# ═══════════════════════════════════════════════════════════════════════════════
# Docker Compose 项目管理
# ═══════════════════════════════════════════════════════════════════════════════

class ComposeManager:
    """Docker Compose 项目管理"""

    @staticmethod
    def ps(project_dir: str) -> List[Dict]:
        """列出 Compose 项目的服务状态"""
        r = _run_compose(["ps", "--format", "json"], project_dir)
        if r.returncode != 0:
            return []
        services = []
        for line in r.stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                services.append({
                    "name": data.get("Name", ""),
                    "image": data.get("Image", ""),
                    "status": data.get("Status", ""),
                    "state": data.get("State", ""),
                    "ports": data.get("Ports", ""),
                })
            except json.JSONDecodeError:
                continue
        return services

    @staticmethod
    def up(project_dir: str, detach: bool = True, build: bool = False) -> Dict:
        """部署 Compose 项目"""
        cmd = ["up"]
        if detach:
            cmd.append("-d")
        if build:
            cmd.append("--build")
        r = _run_compose(cmd, project_dir, timeout=300)
        return {
            "success": r.returncode == 0,
            "output": r.stdout[-2000:] if r.stdout else "",
            "error": r.stderr[-2000:] if r.stderr else "",
        }

    @staticmethod
    def down(project_dir: str, volumes: bool = False) -> Dict:
        """停止并移除 Compose 项目"""
        cmd = ["down"]
        if volumes:
            cmd.append("-v")
        r = _run_compose(cmd, project_dir, timeout=120)
        return {
            "success": r.returncode == 0,
            "output": r.stdout[-1000:] if r.stdout else "",
            "error": r.stderr[-1000:] if r.stderr else "",
        }

    @staticmethod
    def logs(project_dir: str, tail: int = 100, service: str = "") -> str:
        """获取 Compose 项目日志"""
        cmd = ["logs", "--tail", str(tail)]
        if service:
            cmd.append(service)
        r = _run_compose(cmd, project_dir, timeout=30)
        if r.returncode != 0:
            return f"Error: {r.stderr}"
        return r.stdout

    @staticmethod
    def pull(project_dir: str) -> Dict:
        """拉取 Compose 定义的所有镜像"""
        r = _run_compose(["pull"], project_dir, timeout=600)
        return {
            "success": r.returncode == 0,
            "output": r.stdout[-2000:] if r.stdout else "",
            "error": r.stderr[-2000:] if r.stderr else "",
        }

    @staticmethod
    def restart(project_dir: str, service: str = "") -> bool:
        """重启 Compose 服务"""
        cmd = ["restart"]
        if service:
            cmd.append(service)
        r = _run_compose(cmd, project_dir, timeout=60)
        return r.returncode == 0

    @staticmethod
    def stop(project_dir: str) -> Dict:
        """停止 Compose 项目的所有服务但保留容器"""
        cmd = ["stop"]
        r = _run_compose(cmd, project_dir, timeout=60)
        return {
            "success": r.returncode == 0,
            "output": r.stdout[-1000:] if r.stdout else "",
            "error": r.stderr[-1000:] if r.stderr else "",
        }

    @staticmethod
    def get_projects(base_dir: str = "/opt/ubunturouter/apps/installed") -> List[ComposeProjectInfo]:
        """扫描已安装的 Compose 项目"""
        base = Path(base_dir)
        if not base.exists():
            return []

        projects = []
        for item in base.iterdir():
            if not item.is_dir() and not item.is_symlink():
                continue
            # 查找 docker-compose.yml
            compose_file = item / "docker-compose.yml"
            if not compose_file.exists():
                compose_file = item / "docker-compose.yaml"
            if not compose_file.exists():
                continue

            services = ComposeManager.ps(str(item))
            status = "running" if any(s.get("state") == "running" for s in services) else "stopped"
            if services and any(s.get("state") != "running" for s in services) and \
               any(s.get("state") == "running" for s in services):
                status = "partial"

            projects.append(ComposeProjectInfo(
                name=item.name,
                status=status,
                services=services,
                config_files=[str(compose_file)],
            ))

        return projects


def _parse_size(size_str: str) -> int:
    """解析 Docker size 字符串 (如 '93.5MB') 为字节数"""
    size_str = size_str.strip().upper()
    if not size_str:
        return 0
    try:
        if size_str.endswith("GB"):
            return int(float(size_str[:-2]) * 1024 ** 3)
        elif size_str.endswith("MB"):
            return int(float(size_str[:-2]) * 1024 ** 2)
        elif size_str.endswith("KB"):
            return int(float(size_str[:-2]) * 1024)
        elif size_str.endswith("B"):
            return int(size_str[:-1])
        return int(size_str)
    except (ValueError, IndexError):
        return 0
