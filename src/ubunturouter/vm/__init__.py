"""VM 管理模块 — libvirt、模板、VFIO 直通检测"""
from .libvirt_wrapper import VirtManager, Domain
from .template import VMTemplate, VMTemplateInfo
from .vfio import VFIODetector

__all__ = ["VirtManager", "Domain", "VMTemplate", "VMTemplateInfo", "VFIODetector"]
