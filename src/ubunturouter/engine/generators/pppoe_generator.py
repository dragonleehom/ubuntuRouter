"""PPPoE 配置生成器 — 生成 /etc/ppp/peers/ubunturouter

将 UbunturouterConfig.pppoe 配置节转写为 PPPoE peers 文件。
响应 "pppoe" 配置节变更。
"""

import logging
from pathlib import Path
from typing import List

from ubunturouter.config.models import UbunturouterConfig, PPPoEConfig, InterfaceRole
from ubunturouter.engine.events import GeneratorResult
from ubunturouter.engine.generators.base import BaseGenerator, register_generator

logger = logging.getLogger(__name__)

PPP_PEERS_DIR = Path("/etc/ppp/peers")
PROVIDER_NAME = "ubunturouter"
PPP_CONFIG_PATH = PPP_PEERS_DIR / PROVIDER_NAME


@register_generator
class PPPoEGenerator(BaseGenerator):
    """生成 /etc/ppp/peers/ubunturouter"""
    SECTION = "pppoe"

    def generate(self, config: UbunturouterConfig) -> GeneratorResult:
        files_modified = []

        pppoe = config.pppoe
        if not pppoe or not pppoe.enabled:
            # 如果 PPPoE 被禁用，确保 peers 文件被移除
            if PPP_CONFIG_PATH.exists():
                PPP_CONFIG_PATH.unlink(missing_ok=True)
                # 断开 PPPoE 连接
                self.run_cmd(["poff", PROVIDER_NAME], timeout=10)
                files_modified.append(str(PPP_CONFIG_PATH))
                return self.ok("PPPoE disabled, config removed", files_modified)
            return self.ok("PPPoE not configured, skipped")

        if not pppoe.username or not pppoe.password:
            return self.fail("PPPoE username and password are required")

        # 查找 PPPoE 接口对应的设备名
        device = self._find_wan_device(config, pppoe.interface)
        if not device:
            logger.warning("PPPoE interface '%s' not found in config, using eth1", pppoe.interface)
            device = "eth1"

        content = f"""# UbuntuRouter PPPoE configuration - auto-generated
plugin rp-pppoe.so
nic {device}
name "{pppoe.username}"
password "{pppoe.password}"
mtu {pppoe.mtu}
mru {pppoe.mtu}
persist
maxfail 0
holdoff 10
lcp-echo-interval 10
lcp-echo-failure 5
usepeerdns
defaultroute
noauth
noipdefault
"""

        if not self.write_file(PPP_CONFIG_PATH, content):
            return self.fail(f"Failed to write {PPP_CONFIG_PATH}")

        # chmod 600
        try:
            PPP_CONFIG_PATH.chmod(0o600)
        except Exception:
            pass

        files_modified.append(str(PPP_CONFIG_PATH))

        # 如果配置变更，重新拨号
        connect_result = self.run_cmd(["pon", PROVIDER_NAME], timeout=15)
        if connect_result["success"]:
            return self.ok(f"PPPoE configuration applied, dialing {device}", files_modified)
        else:
            stderr = connect_result.get("stderr", "")
            # 可能已连接
            if "already running" in stderr or "File exists" in stderr:
                return self.ok(f"PPPoE already connected on {device}", files_modified)
            return self.fail(f"PPPoE dial failed: {stderr}")

    def _find_wan_device(self, config: UbunturouterConfig, interface_name: str) -> str:
        """从配置中查找 WAN 接口对应的设备名"""
        for iface in config.interfaces:
            if iface.name == interface_name or iface.device == interface_name:
                if iface.device:
                    return iface.device
            # 查找 WAN 角色中的第一个设备
            if iface.role == InterfaceRole.WAN and iface.device:
                return iface.device
            if iface.role == InterfaceRole.WANLAN and iface.device:
                return iface.device
        return "eth1"
