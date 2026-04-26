"""Samba 配置生成器 — 生成 /etc/samba/smb.conf

将 UbunturouterConfig.samba 配置节转写为 smb.conf。
响应 "samba" 配置节变更。
"""

import logging
from pathlib import Path
from typing import List

from ubunturouter.config.models import UbunturouterConfig, SambaConfig, SambaShareConfig
from ubunturouter.engine.events import GeneratorResult
from ubunturouter.engine.generators.base import BaseGenerator, register_generator

logger = logging.getLogger(__name__)

SMBCONF_PATH = Path("/etc/samba/smb.conf")


@register_generator
class SambaGenerator(BaseGenerator):
    """生成 /etc/samba/smb.conf"""
    SECTION = "samba"

    def generate(self, config: UbunturouterConfig) -> GeneratorResult:
        files_modified = []

        samba = config.samba
        if not samba or not samba.enabled:
            # 禁用 Samba：停止服务
            if self.file_exists(SMBCONF_PATH):
                # 不要删除配置，只停止服务
                self.reload_service("smbd")
                self.run_cmd(["systemctl", "stop", "smbd"], timeout=10)
                self.run_cmd(["systemctl", "stop", "nmbd"], timeout=10)
                return self.ok("Samba disabled, services stopped")
            return self.ok("Samba not configured, skipped")

        lines = [
            "# UbuntuRouter Samba configuration - auto-generated",
            "# Do not edit manually - changes will be overwritten",
            "",
            "[global]",
            f"    workgroup = {samba.workgroup}",
            f"    server string = {samba.server_string}",
            "    security = user",
            "    map to guest = Bad User",
            "    server role = standalone server",
            "    netbios name = router",
            "    disable netbios = no",
            "    dns proxy = no",
            "    guest account = nobody",
            "    log file = /var/log/samba/log.%m",
            "    max log size = 1000",
            "    load printers = no",
            "    printing = bsd",
            "    printcap name = /dev/null",
            "    disable spoolss = yes",
            "    socket options = TCP_NODELAY",
            f"    interfaces = lo 192.168.0.0/16",
            "    bind interfaces only = yes",
            "",
        ]

        for share in samba.shares:
            if not share.enabled:
                continue
            lines.append(f"[{share.name}]")
            lines.append(f"    path = {share.path}")
            lines.append(f"    browseable = {'yes' if share.browsable else 'no'}")
            lines.append(f"    writable = {'yes' if share.writable else 'no'}")
            lines.append(f"    guest ok = {'yes' if share.guest_ok else 'no'}")
            if share.valid_users:
                lines.append(f"    valid users = {share.valid_users}")
            lines.append(f"    create mask = 0755")
            lines.append(f"    directory mask = 0755")
            lines.append("")

        content = "\n".join(lines)

        if not self.write_file(SMBCONF_PATH, content):
            return self.fail(f"Failed to write {SMBCONF_PATH}")

        files_modified.append(str(SMBCONF_PATH))

        # 验证配置
        testparm = self.run_cmd(["testparm", "-s"], timeout=15)
        if not testparm["success"]:
            return self.fail(f"smb.conf validation failed: {testparm.get('stderr', '')}")

        # 重启 Samba 服务
        self.run_cmd(["systemctl", "restart", "smbd"], timeout=15)
        self.run_cmd(["systemctl", "restart", "nmbd"], timeout=15)

        return self.ok(
            f"Samba configuration applied ({len(samba.shares)} shares)",
            files_modified,
        )
