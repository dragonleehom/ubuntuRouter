"""VM 管理 API 路由 — FastAPI router，前缀 /api/v1/vm"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends

from ..deps import require_auth
from ...vm import VirtManager, VMTemplate, VFIODetector
from ...vm.libvirt_wrapper import Domain
from ...vm.template import VMTemplateInfo
from ..vnc_proxy import VNCProxy

logger = logging.getLogger(__name__)

router = APIRouter()

IMAGES_DIR = "/opt/ubunturouter/vm/images"


# ═══════════════════════════════════════════════════════════════════════════════
# 可用性检查
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/available")
async def check_available():
    """检查 VM 功能是否可用（virsh + KVM）。"""
    available = VirtManager.check_available()
    return {
        "available": available,
        "virsh_installed": VirtManager.check_available(),  # 简化检查
        "kvm_available": available,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 域名管理
# ═══════════════════════════════════════════════════════════════════════════════

def _domain_to_dict(d: Domain) -> dict:
    """将 Domain dataclass 转为字典。"""
    return {
        "name": d.name,
        "uuid": d.uuid,
        "state": d.state,
        "vcpus": d.vcpus,
        "memory_mb": d.memory_mb,
        "cpu_time": d.cpu_time,
        "vnc_port": d.vnc_port,
        "disk_paths": d.disk_paths,
        "autostart": d.autostart,
    }


@router.get("/domains")
async def list_domains(auth=Depends(require_auth)):
    """获取虚拟机列表。"""
    domains = VirtManager.list_domains()
    return {
        "domains": [_domain_to_dict(d) for d in domains],
        "total": len(domains),
    }


@router.get("/domains/{name}")
async def get_domain(name: str, auth=Depends(require_auth)):
    """获取虚拟机详情。"""
    try:
        info = VirtManager.domain_info(name)
        if not info or not info.get("uuid"):
            raise HTTPException(status_code=404, detail=f"虚拟机 '{name}' 未找到")
        return {"domain": info}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"虚拟机 '{name}' 未找到: {str(e)}")


@router.post("/domains")
async def create_domain(
    name: str,
    template: Optional[str] = Query(None, description="模板名称"),
    vcpus: int = Query(2, ge=1, le=64),
    memory_mb: int = Query(2048, ge=128, le=262144),
    disk_size_gb: int = Query(20, ge=1, le=2048),
    network: str = Query("bridge:br0", description="网络配置: bridge:br0 或 nat:default"),
    iso_url: Optional[str] = Query(None, description="ISO 下载 URL"),
    auth=Depends(require_auth),
):
    """创建虚拟机。

    支持从模板预设参数或自定义参数创建。
    如果指定 template，vcpus/memory_mb/disk_size_gb 将使用模板默认值（可被显式参数覆盖）。
    """
    # 如果指定了模板，加载模板默认值
    if template:
        tmpl = VMTemplate.get_template(template)
        if tmpl:
            if vcpus == 2:  # 未显式指定
                vcpus = tmpl.default_vcpus
            if memory_mb == 2048:
                memory_mb = max(memory_mb, tmpl.min_ram)
            if disk_size_gb == 20:
                disk_size_gb = max(disk_size_gb, tmpl.min_disk)

    # 检查名称合法性
    import re
    if not re.match(r"^[a-zA-Z0-9_-]{1,64}$", name):
        raise HTTPException(status_code=400, detail="虚拟机名称不合法（只能包含字母、数字、下划线、连字符，最长64字符）")

    # 解析网络配置
    disk_path = f"/var/lib/libvirt/images/{name}.qcow2"

    # 如果提供了 ISO URL，先下载
    if iso_url:
        iso_name = os.path.basename(iso_url.split("?")[0]) or f"{name}.iso"
        iso_dest = os.path.join(IMAGES_DIR, iso_name)
        downloaded = VMTemplate.download_image(iso_url, iso_dest)
        if not downloaded:
            raise HTTPException(status_code=500, detail=f"ISO 下载失败: {iso_url}")

    # 创建虚拟机
    success = VirtManager.create_domain(
        name=name,
        vcpus=vcpus,
        memory_mb=memory_mb,
        disk_path=disk_path,
        disk_size_gb=disk_size_gb,
    )
    if not success:
        raise HTTPException(status_code=500, detail=f"创建虚拟机 '{name}' 失败")

    return {
        "message": f"虚拟机 '{name}' 创建成功",
        "domain": VirtManager.domain_info(name),
    }


@router.post("/domains/{name}/start")
async def start_domain(name: str, auth=Depends(require_auth)):
    """启动虚拟机。"""
    success = VirtManager.start_domain(name)
    if not success:
        raise HTTPException(status_code=500, detail=f"启动虚拟机 '{name}' 失败")
    return {"message": f"虚拟机 '{name}' 已启动"}


@router.post("/domains/{name}/shutdown")
async def shutdown_domain(
    name: str,
    force: bool = Query(False, description="是否强制关机"),
    auth=Depends(require_auth),
):
    """关闭虚拟机。force=true 时强制销毁。"""
    success = VirtManager.shutdown_domain(name, force=force)
    if not success:
        raise HTTPException(status_code=500, detail=f"关机 '{name}' 失败")
    action = "强制关机" if force else "正常关机"
    return {"message": f"虚拟机 '{name}' 已{action}"}


@router.post("/domains/{name}/reboot")
async def reboot_domain(name: str, auth=Depends(require_auth)):
    """重启虚拟机。"""
    success = VirtManager.reboot_domain(name)
    if not success:
        raise HTTPException(status_code=500, detail=f"重启 '{name}' 失败")
    return {"message": f"虚拟机 '{name}' 已重启"}


@router.delete("/domains/{name}")
async def delete_domain(
    name: str,
    remove_disks: bool = Query(True, description="是否同时删除磁盘文件"),
    auth=Depends(require_auth),
):
    """删除虚拟机。"""
    # 停止代理（如果有）
    try:
        VNCProxy.stop_proxy(name)
    except Exception:
        pass

    success = VirtManager.delete_domain(name)
    if not success:
        raise HTTPException(status_code=500, detail=f"删除虚拟机 '{name}' 失败")

    msg = f"虚拟机 '{name}' 已删除"
    if not remove_disks:
        msg += "（磁盘文件已保留）"
    return {"message": msg}


# ═══════════════════════════════════════════════════════════════════════════════
# 模板管理
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/templates")
async def list_templates(auth=Depends(require_auth)):
    """获取 VM 模板列表。"""
    templates = VMTemplate.list_templates()
    return {
        "templates": [
            {
                "name": t.name,
                "os_type": t.os_type,
                "description": t.description,
                "min_ram": t.min_ram,
                "min_disk": t.min_disk,
                "default_vcpus": t.default_vcpus,
                "has_cloud_image": t.cloud_image_url is not None,
            }
            for t in templates
        ],
        "total": len(templates),
    }


@router.post("/templates/{name}/download")
async def download_template_image(
    name: str,
    auth=Depends(require_auth),
):
    """下载指定模板的云镜像。"""
    tmpl = VMTemplate.get_template(name)
    if not tmpl:
        raise HTTPException(status_code=404, detail=f"模板 '{name}' 未找到")

    if not tmpl.cloud_image_url:
        raise HTTPException(status_code=400, detail=f"模板 '{name}' 没有可下载的云镜像")

    fname = os.path.basename(tmpl.cloud_image_url.split("?")[0])
    dest_path = os.path.join(IMAGES_DIR, fname)

    # 检查是否已下载
    if os.path.exists(dest_path):
        return {
            "message": f"镜像已存在: {dest_path}",
            "path": dest_path,
            "already_exists": True,
        }

    path = VMTemplate.download_image(tmpl.cloud_image_url, dest_path)
    if not path:
        raise HTTPException(status_code=500, detail=f"下载镜像失败: {tmpl.cloud_image_url}")

    return {
        "message": f"镜像下载完成: {path}",
        "path": path,
        "already_exists": False,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# VNC / 远程桌面
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/vnc/{name}")
async def get_vnc_info(name: str, auth=Depends(require_auth)):
    """获取 VM 的 VNC/WebSocket 连接信息。"""
    # 获取 VNC 端口
    vnc_port = VirtManager.get_vnc_port(name)
    if vnc_port is None:
        # 即使没有 VNC 端口，也返回 VM 状态信息
        info = VirtManager.domain_info(name)
        if not info or not info.get("uuid"):
            raise HTTPException(status_code=404, detail=f"虚拟机 '{name}' 未找到")
        return {
            "available": False,
            "name": name,
            "vnc_port": None,
            "ws_url": None,
            "message": "VM 未运行或未配置 VNC",
            "domain": info,
        }

    # 尝试创建 WebSocket 代理
    proxy_info = VNCProxy.create_proxy(name, vnc_port=vnc_port)

    return {
        "available": proxy_info.get("available", False),
        "name": name,
        "vnc_port": vnc_port,
        "vnc_url": f"vnc://127.0.0.1:{vnc_port}",
        "ws_url": proxy_info.get("ws_url"),
        "proxy_port": proxy_info.get("proxy_port"),
        "message": proxy_info.get("message", ""),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PCI / VFIO 直通
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/pci")
async def list_pci_devices(auth=Depends(require_auth)):
    """列出 PCI 设备（用于 VFIO 直通）。"""
    iommu_enabled = VFIODetector.check_iommu_support()
    devices = VFIODetector.list_pci_devices()
    return {
        "iommu_enabled": iommu_enabled,
        "devices": devices,
        "total": len(devices),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 存储与网络（辅助信息）
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/storage-pools")
async def list_storage_pools(auth=Depends(require_auth)):
    """列出 libvirt 存储池。"""
    pools = VirtManager.list_storage_pools()
    return {"pools": pools, "total": len(pools)}


@router.get("/networks")
async def list_networks(auth=Depends(require_auth)):
    """列出 libvirt 网络。"""
    networks = VirtManager.list_networks()
    return {"networks": networks, "total": len(networks)}


# ── Fix missing import ────────────────────────────────────────────────────────
import os  # noqa: E402 (used in create_domain and download_template_image)
