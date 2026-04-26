"""VFIO 直通检测 — 检查 IOMMU 支持，列出 PCI 设备，检测 VFIO 驱动绑定

使用 lspci、dmesg 等命令行工具，不依赖 python 库。
"""

import os
import re
import subprocess
from typing import List, Optional


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run_cmd(cmd: list, timeout: int = 10) -> subprocess.CompletedProcess:
    """运行命令，失败不抛异常。"""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return subprocess.CompletedProcess(args=cmd, returncode=-1, stdout="", stderr="")


# ── VFIODetector ──────────────────────────────────────────────────────────────

class VFIODetector:
    """VFIO 直通功能检测器。"""

    @staticmethod
    def check_iommu_support() -> bool:
        """检查系统是否支持 IOMMU（Intel VT-d / AMD-Vi）。

        检查方法：
        1. dmesg 中查找 "IOMMU enabled" 或 "DMAR: IOMMU enabled"
        2. /sys/kernel/iommu_groups 目录是否存在且非空
        """
        try:
            # 方法1: 检查 /sys/kernel/iommu_groups
            if os.path.isdir("/sys/kernel/iommu_groups"):
                groups = os.listdir("/sys/kernel/iommu_groups")
                if groups:
                    return True

            # 方法2: dmesg 检查
            result = _run_cmd(["dmesg"])
            if result.returncode == 0:
                output = result.stdout.lower()
                if "iommu: dmar" in output or "iommu enabled" in output or "amd-vi" in output:
                    return True
                if "iommu" in output and ("intel" in output or "amd" in output):
                    return True

            # 方法3: 检查内核参数
            try:
                with open("/proc/cmdline") as f:
                    cmdline = f.read()
                if "intel_iommu=on" in cmdline or "amd_iommu=on" in cmdline or "iommu=pt" in cmdline:
                    return True
            except Exception:
                pass

        except Exception:
            pass
        return False

    @staticmethod
    def list_pci_devices() -> List[dict]:
        """列出所有 PCI 设备，返回设备信息列表。

        使用 lspci 获取详细信息。
        """
        devices = []
        try:
            result = _run_cmd(["lspci", "-vvnn"])
            if result.returncode != 0:
                return devices

            # 按空白行分割
            blocks = re.split(r"\n\n+", result.stdout.strip())
            for block in blocks:
                if not block.strip():
                    continue
                lines = block.strip().splitlines()
                if not lines:
                    continue

                # 第一行: "00:02.0 VGA compatible controller [0300]: Intel Corporation ..."
                first = lines[0]
                pci_addr = first.split()[0].rstrip(":")

                # 解析 IOMMU 组
                iommu_group = VFIODetector._get_iommu_group(pci_addr)

                # 检查 VFIO 驱动
                vfio_bound = VFIODetector.check_vfio_driver(pci_addr)

                device_info = {
                    "address": pci_addr,
                    "description": first,
                    "iommu_group": iommu_group,
                    "vfio_bound": vfio_bound,
                    "driver": VFIODetector._get_driver(pci_addr),
                }

                # 补充详细信息
                for line in lines[1:]:
                    line_stripped = line.strip()
                    if line_stripped.lower().startswith("kernel driver in use:"):
                        driver = line_stripped.split(":", 1)[-1].strip()
                        device_info["driver"] = driver
                    elif "Subsystem:" in line_stripped:
                        device_info["subsystem"] = line_stripped

                devices.append(device_info)

        except Exception:
            pass
        return devices

    @staticmethod
    def check_vfio_driver(pci_addr: str) -> bool:
        """检查指定 PCI 设备是否已绑定到 vfio-pci 驱动。"""
        try:
            driver_path = f"/sys/bus/pci/devices/0000:{pci_addr}/driver"
            if os.path.exists(driver_path):
                driver = os.path.basename(os.readlink(driver_path))
                return driver == "vfio-pci"

            # 备选：检查 /sys/kernel/iommu_groups 下的 vfio 设备
            if os.path.isdir("/sys/kernel/iommu_groups"):
                for group in os.listdir("/sys/kernel/iommu_groups"):
                    group_path = f"/sys/kernel/iommu_groups/{group}"
                    if not os.path.isdir(group_path):
                        continue
                    for dev in os.listdir(group_path):
                        if pci_addr.replace(":", ".") in dev or pci_addr in dev:
                            driver_link = os.path.join(group_path, dev, "driver")
                            if os.path.exists(driver_link):
                                driver = os.path.basename(os.readlink(driver_link))
                                return driver == "vfio-pci"
        except Exception:
            pass
        return False

    # ── Internal helpers ──────────────────────────────────────────────────

    @staticmethod
    def _get_iommu_group(pci_addr: str) -> Optional[int]:
        """获取 PCI 设备的 IOMMU 组编号。"""
        try:
            # /sys/bus/pci/devices/0000:00:02.0/iommu_group -> ../../../../../kernel/iommu_groups/1
            pci_sysfs = f"/sys/bus/pci/devices/0000:{pci_addr}"
            if os.path.isdir(pci_sysfs):
                group_link = os.path.join(pci_sysfs, "iommu_group")
                if os.path.exists(group_link):
                    target = os.readlink(group_link)
                    group_num = os.path.basename(target)
                    try:
                        return int(group_num)
                    except ValueError:
                        return group_num
        except Exception:
            pass
        return None

    @staticmethod
    def _get_driver(pci_addr: str) -> Optional[str]:
        """获取 PCI 设备当前使用的驱动。"""
        try:
            driver_path = f"/sys/bus/pci/devices/0000:{pci_addr}/driver"
            if os.path.exists(driver_path):
                return os.path.basename(os.readlink(driver_path))
        except Exception:
            pass
        return None
