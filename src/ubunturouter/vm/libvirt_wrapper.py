"""libvirt 封装 — 通过 subprocess 调用 virsh，不依赖 python-libvirt"""

import os
import re
import subprocess
import tempfile
import shutil
from dataclasses import dataclass, field
from typing import List, Optional

# ── Domain dataclass ──────────────────────────────────────────────────────────

@dataclass
class Domain:
    name: str
    uuid: str = ""
    state: str = "unknown"  # running / shutdown / paused
    vcpus: int = 0
    memory_mb: int = 0
    cpu_time: str = ""
    vnc_port: Optional[int] = None
    disk_paths: List[str] = field(default_factory=list)
    autostart: bool = False


# ── Constants ─────────────────────────────────────────────────────────────────

VIRSH_CMD = "virsh"
DEFAULT_STORAGE_PATH = "/var/lib/libvirt/images"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run_virsh(args: list, check: bool = False) -> subprocess.CompletedProcess:
    """运行 virsh 命令，失败不抛异常（除非 check=True）。"""
    try:
        return subprocess.run(
            [VIRSH_CMD] + args,
            capture_output=True,
            text=True,
            timeout=30,
            check=check,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
        # 返回一个假的 CompletedProcess，调用方检查 returncode
        return subprocess.CompletedProcess(
            args=[VIRSH_CMD] + args,
            returncode=-1,
            stdout="",
            stderr=str(e),
        )


def _virsh_available() -> bool:
    """快速检查 virsh 是否可执行。"""
    return shutil.which(VIRSH_CMD) is not None


# ── VirtManager ───────────────────────────────────────────────────────────────

class VirtManager:
    """通过 virsh 命令行的 libvirt 管理。所有调用 try/except 包裹。"""

    @staticmethod
    def check_available() -> bool:
        """检查 virsh 命令和 /dev/kvm 是否可用。"""
        if not _virsh_available():
            return False
        if not os.path.exists("/dev/kvm"):
            return False
        # 快速执行一次 virsh list 验证可用性
        result = _run_virsh(["list", "--all"])
        return result.returncode == 0

    # ── Domain listing ────────────────────────────────────────────────────

    @staticmethod
    def list_domains() -> List[Domain]:
        """virsh list --all 解析输出，返回 Domain 列表。"""
        domains: List[Domain] = []
        try:
            result = _run_virsh(["list", "--all"])
            if result.returncode != 0:
                return domains

            lines = result.stdout.strip().splitlines()
            # 跳过标题行和分隔线
            # 输出格式:
            #  Id   Name          State
            # ----------------------------------
            #  -    ubuntu-vm     shut off
            #   5   running-vm    running
            for line in lines:
                line = line.strip()
                if not line or line.startswith("---") or "Id" in line:
                    continue
                parts = line.split(None, 2)
                if len(parts) < 3:
                    continue
                dom_id = parts[0]
                name = parts[1]
                state_raw = parts[2] if len(parts) > 2 else "unknown"

                # 标准化状态
                state = state_raw.lower()
                if state in ("running",):
                    state = "running"
                elif state in ("shut off", "shutdown", "shut_off", "off"):
                    state = "shutdown"
                elif state in ("paused", "suspended"):
                    state = "paused"
                else:
                    state = "unknown"

                domain = Domain(
                    name=name,
                    state=state,
                    vcpus=0,
                    memory_mb=0,
                )
                # 如果有 ID（非 '-'）则设置 id 字段（我们会复用 name 字段）
                # 对于后端，我们用 name 做标识, id 是 libvirt 内部 ID
                if dom_id != "-" and dom_id.isdigit():
                    domain.vcpus = int(dom_id)  # 暂存，后续 dominfo 会覆盖

                domains.append(domain)

            # 获取每个域名的详细信息
            for domain in domains:
                try:
                    info = VirtManager.domain_info(domain.name)
                    domain.uuid = info.get("uuid", "")
                    domain.vcpus = info.get("vcpus", 0)
                    domain.memory_mb = info.get("memory_mb", 0)
                    domain.cpu_time = info.get("cpu_time", "")
                    domain.autostart = info.get("autostart", False)
                    domain.disk_paths = info.get("disk_paths", [])
                    domain.vnc_port = info.get("vnc_port")
                except Exception:
                    pass

        except Exception:
            pass

        return domains

    @staticmethod
    def domain_info(name: str) -> dict:
        """返回虚拟机详细信息字典（virsh dominfo + domstats）。"""
        info: dict = {
            "name": name,
            "uuid": "",
            "state": "unknown",
            "vcpus": 0,
            "memory_mb": 0,
            "cpu_time": "",
            "autostart": False,
            "disk_paths": [],
            "vnc_port": None,
        }
        try:
            # dominfo
            result = _run_virsh(["dominfo", name])
            if result.returncode == 0:
                for line in result.stdout.strip().splitlines():
                    line = line.strip()
                    if ":" not in line:
                        continue
                    key, _, val = line.partition(":")
                    key = key.strip().lower()
                    val = val.strip()
                    if key == "uuid":
                        info["uuid"] = val
                    elif key == "state":
                        info["state"] = val.lower()
                        if "shut" in val.lower() or "off" in val.lower():
                            info["state"] = "shutdown"
                        elif "running" in val.lower():
                            info["state"] = "running"
                        elif "paused" in val.lower() or "suspended" in val.lower():
                            info["state"] = "paused"
                    elif key == "cpu(s)":
                        try:
                            info["vcpus"] = int(val)
                        except ValueError:
                            pass
                    elif key == "max memory":
                        # 格式: "2097152 KiB"
                        m = re.search(r"(\d+)", val)
                        if m:
                            info["memory_mb"] = int(m.group(1)) // 1024
                    elif key == "autostart":
                        info["autostart"] = val.lower() == "enable"

            # domstats (补充 CPU time 等信息)
            stats_result = _run_virsh(["domstats", name])
            if stats_result.returncode == 0:
                for line in stats_result.stdout.strip().splitlines():
                    line = line.strip()
                    if "cpu.time=" in line:
                        val = line.split("=", 1)[-1].strip()
                        try:
                            ns = int(val)
                            seconds = ns / 1_000_000_000
                            info["cpu_time"] = f"{seconds:.2f}s"
                        except ValueError:
                            info["cpu_time"] = val
                    elif "balloon.current=" in line:
                        val = line.split("=", 1)[-1].strip()
                        try:
                            info["memory_mb"] = int(val) // 1024
                        except ValueError:
                            pass
                    elif "vcpu.current=" in line:
                        val = line.split("=", 1)[-1].strip()
                        try:
                            info["vcpus"] = int(val)
                        except ValueError:
                            pass

            # 获取磁盘路径
            try:
                disk_result = _run_virsh(["domblklist", name])
                if disk_result.returncode == 0:
                    disk_lines = disk_result.stdout.strip().splitlines()
                    for line in disk_lines:
                        line = line.strip()
                        if not line or line.startswith("---") or "Target" in line or "Source" in line:
                            continue
                        parts = line.split()
                        if len(parts) >= 2:
                            path = parts[-1]
                            if path and path != "-":
                                info["disk_paths"].append(path)
            except Exception:
                pass

            # 获取 VNC 端口
            info["vnc_port"] = VirtManager.get_vnc_port(name)

        except Exception:
            pass

        return info

    # ── Create ────────────────────────────────────────────────────────────

    @staticmethod
    def create_domain(
        name: str,
        vcpus: int = 2,
        memory_mb: int = 2048,
        disk_path: Optional[str] = None,
        disk_size_gb: int = 20,
    ) -> bool:
        """创建虚拟机：生成 XML，virsh define。"""
        try:
            if not name or not re.match(r"^[a-zA-Z0-9_-]+$", name):
                return False

            # 默认磁盘路径
            if not disk_path:
                disk_path = f"{DEFAULT_STORAGE_PATH}/{name}.qcow2"

            # 确保目录存在
            disk_dir = os.path.dirname(disk_path)
            if disk_dir and not os.path.exists(disk_dir):
                os.makedirs(disk_dir, exist_ok=True)

            # 创建 qcow2 磁盘
            if not os.path.exists(disk_path):
                qemu_result = subprocess.run(
                    ["qemu-img", "create", "-f", "qcow2", disk_path, f"{disk_size_gb}G"],
                    capture_output=True, text=True, timeout=60,
                )
                if qemu_result.returncode != 0:
                    return False

            # 生成 XML
            xml = VirtManager._generate_domain_xml(
                name=name,
                vcpus=vcpus,
                memory_mb=memory_mb,
                disk_path=disk_path,
            )

            # virsh define
            with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
                f.write(xml)
                xml_path = f.name

            try:
                result = _run_virsh(["define", xml_path])
                return result.returncode == 0
            finally:
                try:
                    os.unlink(xml_path)
                except Exception:
                    pass

        except Exception:
            return False

    @staticmethod
    def _generate_domain_xml(
        name: str,
        vcpus: int = 2,
        memory_mb: int = 2048,
        disk_path: str = "",
    ) -> str:
        """生成默认的 KVM 域 XML。"""
        memory_kib = memory_mb * 1024
        uuid = ""  # libvirt 会自动生成
        return f"""<domain type='kvm'>
  <name>{name}</name>
  <memory unit='KiB'>{memory_kib}</memory>
  <currentMemory unit='KiB'>{memory_kib}</currentMemory>
  <vcpu placement='static'>{vcpus}</vcpu>
  <os>
    <type arch='x86_64' machine='q35'>hvm</type>
    <boot dev='hd'/>
    <boot dev='cdrom'/>
  </os>
  <features>
    <acpi/>
    <apic/>
  </features>
  <cpu mode='host-passthrough' check='none'/>
  <clock offset='utc'>
    <timer name='rtc' tickpolicy='catchup'/>
    <timer name='pit' tickpolicy='delay'/>
    <timer name='hpet' present='no'/>
  </clock>
  <on_poweroff>destroy</on_poweroff>
  <on_reboot>restart</on_reboot>
  <on_crash>destroy</on_crash>
  <devices>
    <disk type='file' device='disk'>
      <driver name='qemu' type='qcow2'/>
      <source file='{disk_path}'/>
      <target dev='vda' bus='virtio'/>
    </disk>
    <interface type='bridge'>
      <source bridge='br0'/>
      <model type='virtio'/>
    </interface>
    <graphics type='vnc' port='-1' autoport='yes' listen='127.0.0.1' keymap='en-us'/>
    <video>
      <model type='virtio' heads='1' vram='16384'/>
    </video>
    <console type='pty'/>
    <serial type='pty'>
      <target port='0'/>
    </serial>
    <input type='tablet' bus='usb'/>
    <input type='mouse' bus='ps2'/>
    <memballoon model='virtio'/>
  </devices>
</domain>"""

    # ── Lifecycle ─────────────────────────────────────────────────────────

    @staticmethod
    def start_domain(name: str) -> bool:
        """启动虚拟机。"""
        try:
            result = _run_virsh(["start", name])
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def shutdown_domain(name: str, force: bool = False) -> bool:
        """关闭虚拟机。force=True 时强制销毁。"""
        try:
            if force:
                result = _run_virsh(["destroy", name])
            else:
                result = _run_virsh(["shutdown", name])
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def reboot_domain(name: str) -> bool:
        """重启虚拟机。"""
        try:
            result = _run_virsh(["reboot", name])
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def delete_domain(name: str) -> bool:
        """删除虚拟机（undefine + 删除磁盘文件）。"""
        try:
            # 先获取磁盘路径
            disk_paths = []
            try:
                info = VirtManager.domain_info(name)
                disk_paths = info.get("disk_paths", [])
            except Exception:
                pass

            # undefine
            result = _run_virsh(["undefine", name])
            if result.returncode != 0:
                # 尝试带 --nvram 重试
                result = _run_virsh(["undefine", "--nvram", name])

            # 删除磁盘文件
            for path in disk_paths:
                if path and os.path.exists(path):
                    try:
                        os.unlink(path)
                    except Exception:
                        pass

            return result.returncode == 0
        except Exception:
            return False

    # ── VNC ───────────────────────────────────────────────────────────────

    @staticmethod
    def get_vnc_port(name: str) -> Optional[int]:
        """获取 VM 的 VNC 端口 (5900+N)。"""
        try:
            # 方法1: 使用 virsh vncdisplay
            result = _run_virsh(["vncdisplay", name])
            if result.returncode == 0:
                vnc_out = result.stdout.strip()
                if vnc_out:
                    # 输出格式: ":1" 或 "127.0.0.1:1"
                    m = re.search(r":(\d+)", vnc_out)
                    if m:
                        display_num = int(m.group(1))
                        return 5900 + display_num

            # 方法2: 从 XML 中解析
            dump_result = _run_virsh(["dumpxml", name])
            if dump_result.returncode == 0:
                xml = dump_result.stdout
                # <graphics type='vnc' port='5901' .../>
                m = re.search(r"<graphics\s+type=['\"]vnc['\"][^>]*port=['\"](\d+)['\"]", xml)
                if m:
                    return int(m.group(1))
        except Exception:
            pass
        return None

    # ── Console ───────────────────────────────────────────────────────────

    @staticmethod
    def get_console_output(name: str, lines: int = 100) -> str:
        """获取 VM 的 console 日志输出。"""
        try:
            # 使用 virsh console 需要交互，改用 domdisplay 或直接读 log
            # 实际上 virsh console 是交互式的，这里改用 journal 方式
            # 尝试通过 virsh qemu-monitor-command 获取
            # 更好的方式：使用 `virsh qemu-monitor-command domain --hmp 'info chardev'`
            # 但简单起见，读取 /var/log/libvirt/qemu/ 下的日志
            log_path = f"/var/log/libvirt/qemu/{name}.log"
            if os.path.exists(log_path):
                with open(log_path, "r") as f:
                    content = f.read()
                log_lines = content.strip().splitlines()
                return "\n".join(log_lines[-lines:])

            # 尝试用 journalctl 获取
            try:
                j_result = subprocess.run(
                    ["journalctl", "-u", f"libvirt-qemu-{name}", "--no-pager", "-n", str(lines)],
                    capture_output=True, text=True, timeout=10,
                )
                if j_result.returncode == 0 and j_result.stdout.strip():
                    return j_result.stdout.strip()
            except Exception:
                pass

            return ""
        except Exception:
            return ""

    # ── Storage ───────────────────────────────────────────────────────────

    @staticmethod
    def list_storage_pools() -> list:
        """virsh pool-list 列出存储池。"""
        pools = []
        try:
            result = _run_virsh(["pool-list", "--all"])
            if result.returncode != 0:
                return pools
            lines = result.stdout.strip().splitlines()
            for line in lines:
                line = line.strip()
                if not line or line.startswith("---") or "Name" in line:
                    continue
                parts = line.split(None, 2)
                if len(parts) >= 2:
                    pools.append({
                        "name": parts[0],
                        "state": parts[1].lower() if len(parts) > 1 else "unknown",
                        "autostart": parts[2].lower() if len(parts) > 2 else "no",
                    })
        except Exception:
            pass
        return pools

    @staticmethod
    def list_networks() -> list:
        """virsh net-list 列出网络。"""
        networks = []
        try:
            result = _run_virsh(["net-list", "--all"])
            if result.returncode != 0:
                return networks
            lines = result.stdout.strip().splitlines()
            for line in lines:
                line = line.strip()
                if not line or line.startswith("---") or "Name" in line:
                    continue
                parts = line.split(None, 2)
                if len(parts) >= 2:
                    networks.append({
                        "name": parts[0],
                        "state": parts[1].lower() if len(parts) > 1 else "unknown",
                        "autostart": parts[2].lower() if len(parts) > 2 else "no",
                    })
        except Exception:
            pass
        return networks
