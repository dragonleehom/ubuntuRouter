"""系统配置生成器 — hostname / 时区 / /etc/hosts 等

响应 "system" 配置节变更。
"""

import logging
from pathlib import Path
from typing import List

from ubunturouter.config.models import UbunturouterConfig
from ubunturouter.engine.events import GeneratorResult
from ubunturouter.engine.generators.base import BaseGenerator, register_generator

logger = logging.getLogger(__name__)

HOSTNAME_PATH = Path("/etc/hostname")
HOSTS_PATH = Path("/etc/hosts")
TIMEZONE_LINK = Path("/etc/localtime")


@register_generator
class SystemGenerator(BaseGenerator):
    """系统级配置 — hostname、时区"""
    SECTION = "system"

    def generate(self, config: UbunturouterConfig) -> GeneratorResult:
        files_modified = []
        system = config.system

        if not system:
            return self.ok("No system config, skipped")

        # 1. 设置 hostname
        if system.hostname:
            current_hostname = ""
            try:
                current_hostname = HOSTNAME_PATH.read_text(encoding="utf-8").strip()
            except Exception:
                pass

            if current_hostname != system.hostname:
                if self.write_file(HOSTNAME_PATH, system.hostname + "\n"):
                    self.run_cmd(["hostname", system.hostname], timeout=5)
                    files_modified.append(str(HOSTNAME_PATH))
                else:
                    return self.fail(f"Failed to write hostname: {system.hostname}")

        # 2. 设置时区
        if system.timezone:
            zoneinfo = Path(f"/usr/share/zoneinfo/{system.timezone}")
            if zoneinfo.exists():
                try:
                    # 使用 timedatectl
                    result = self.run_cmd(
                        ["timedatectl", "set-timezone", system.timezone],
                        timeout=10,
                    )
                    if not result["success"]:
                        logger.warning("timedatectl failed: %s, falling back to symlink", result['stderr'])
                        # Fallback: symlink
                        TIMEZONE_LINK.unlink(missing_ok=True)
                        TIMEZONE_LINK.symlink_to(zoneinfo)
                except Exception:
                    pass
            else:
                logger.warning("Timezone zoneinfo not found: %s", system.timezone)

        return self.ok(
            f"System config applied (hostname={system.hostname}, tz={system.timezone})",
            files_modified,
        )
