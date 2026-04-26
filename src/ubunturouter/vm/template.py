"""VM 模板管理 — 内置模板，云镜像下载，磁盘创建"""

import os
import subprocess
import shutil
from dataclasses import dataclass, field
from typing import List, Optional


# ── Constants ─────────────────────────────────────────────────────────────────

IMAGES_DIR = "/opt/ubunturouter/vm/images"


# ── Template dataclass ────────────────────────────────────────────────────────

@dataclass
class VMTemplateInfo:
    name: str
    os_type: str
    description: str
    min_ram: int = 1024       # MB
    min_disk: int = 10        # GB
    default_vcpus: int = 2
    cloud_image_url: Optional[str] = None
    cloud_init_config: Optional[dict] = None


# ── Built-in templates ────────────────────────────────────────────────────────

_BUILTIN_TEMPLATES = [
    VMTemplateInfo(
        name="ubuntu-24.04",
        os_type="linux",
        description="Ubuntu 24.04 LTS (Noble Numbat) — 通用云镜像",
        min_ram=1024,
        min_disk=10,
        default_vcpus=2,
        cloud_image_url="https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img",
        cloud_init_config={
            "user": "ubuntu",
            "package_update": True,
        },
    ),
    VMTemplateInfo(
        name="debian-12",
        os_type="linux",
        description="Debian 12 (Bookworm) — 稳定版通用云镜像",
        min_ram=512,
        min_disk=10,
        default_vcpus=2,
        cloud_image_url="https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-generic-amd64.qcow2",
        cloud_init_config={
            "user": "debian",
            "package_update": True,
        },
    ),
    VMTemplateInfo(
        name="alpine-3.19",
        os_type="linux",
        description="Alpine Linux 3.19 — 轻量级云镜像",
        min_ram=256,
        min_disk=2,
        default_vcpus=1,
        cloud_image_url="https://dl-cdn.alpinelinux.org/alpine/v3.19/releases/cloud/alpine-virt-3.19.1-x86_64.qcow2",
        cloud_init_config={
            "user": "alpine",
            "package_update": False,
        },
    ),
    VMTemplateInfo(
        name="openwrt-23.05",
        os_type="linux",
        description="OpenWrt 23.05 — 路由器专用系统",
        min_ram=256,
        min_disk=0.5,
        default_vcpus=1,
        cloud_image_url="https://downloads.openwrt.org/releases/23.05.3/targets/x86/64/openwrt-23.05.3-x86-64-generic-ext4-combined.img.gz",
        cloud_init_config=None,
    ),
    VMTemplateInfo(
        name="pfsense-2.7",
        os_type="freebsd",
        description="pfSense 2.7 — 企业级防火墙/路由器 (需手动挂载 ISO)",
        min_ram=1024,
        min_disk=20,
        default_vcpus=2,
        cloud_image_url=None,  # pfSense 没有官方的云镜像，需要 ISO 安装
        cloud_init_config=None,
    ),
]


# ── VMTemplate ────────────────────────────────────────────────────────────────

class VMTemplate:
    """VM 模板管理 — 内置模板、下载、磁盘创建。"""

    @staticmethod
    def list_templates() -> List[VMTemplateInfo]:
        """返回所有内置模板。"""
        return _BUILTIN_TEMPLATES.copy()

    @staticmethod
    def get_template(name: str) -> Optional[VMTemplateInfo]:
        """按名称查找模板。"""
        for t in _BUILTIN_TEMPLATES:
            if t.name == name:
                return t
        return None

    @staticmethod
    def list_cloud_images() -> List[dict]:
        """列出已下载的云镜像文件。"""
        images = []
        try:
            if not os.path.isdir(IMAGES_DIR):
                return images
            for fname in os.listdir(IMAGES_DIR):
                fpath = os.path.join(IMAGES_DIR, fname)
                if os.path.isfile(fpath):
                    size_bytes = os.path.getsize(fpath)
                    images.append({
                        "name": fname,
                        "path": fpath,
                        "size_bytes": size_bytes,
                        "size_human": _format_size(size_bytes),
                    })
        except Exception:
            pass
        return images

    @staticmethod
    def download_image(url: str, dest_path: Optional[str] = None) -> Optional[str]:
        """下载云镜像到本地存储路径。返回下载后的文件路径，失败返回 None。"""
        try:
            # 确保目标目录存在
            os.makedirs(IMAGES_DIR, exist_ok=True)

            if not dest_path:
                # 从 URL 提取文件名
                fname = os.path.basename(url.split("?")[0])
                if not fname:
                    fname = "cloud-image.img"
                dest_path = os.path.join(IMAGES_DIR, fname)

            # 使用 wget 或 curl
            downloader = None
            if shutil.which("wget"):
                downloader = ["wget", "-O", dest_path, url]
            elif shutil.which("curl"):
                downloader = ["curl", "-L", "-o", dest_path, url]
            else:
                return None

            result = subprocess.run(
                downloader,
                capture_output=True,
                text=True,
                timeout=600,  # 10 分钟超时
            )

            if result.returncode == 0 and os.path.exists(dest_path):
                return dest_path
            return None

        except Exception:
            return None

    @staticmethod
    def create_disk(path: str, size_gb: int) -> bool:
        """使用 qemu-img 创建 qcow2 磁盘。"""
        try:
            if not shutil.which("qemu-img"):
                return False

            # 确保目录存在
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

            result = subprocess.run(
                ["qemu-img", "create", "-f", "qcow2", path, f"{size_gb}G"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result.returncode == 0
        except Exception:
            return False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size}B"
    elif size < 1024 ** 2:
        return f"{size/1024:.1f}KB"
    elif size < 1024 ** 3:
        return f"{size/1024**2:.1f}MB"
    else:
        return f"{size/1024**3:.1f}GB"
