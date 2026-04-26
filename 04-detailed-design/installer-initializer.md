# 安装器与初始化器详细设计 — Installer & Initializer

> 版本: v1.0 | 日期: 2026-04-25 | 状态: 初稿
> 对应 HLD 模块: 3.10 Installer & Initializer
> 依赖模块: 无（最先运行的模块）
> 后端技术: Subiquity (ISO), deb (apt), cloud-init, ubuntu-image (ARM)

---

## 1. 模块定位

Installer & Initializer 是用户接触 UbuntuRouter 的第一个模块，负责从零到可用的完整路径。它包含两大子系统：

1. **Installer** — 多模式安装入口（ISO/apt/镜像/ARM），将系统部署到目标硬件
2. **Initializer** — 首次启动配置引擎，自动检测网口、分配角色、生成初始配置、启动 Web 向导

**设计原则**：
- **无头启动**：安装完成后首次启动，无需显示器/键盘，自动初始化网络，用户连 LAN 口即可 Web 配置
- **幂等**：Initializer 只在 `/etc/ubunturouter/config.yaml` 不存在时运行，运行后标记已完成
- **可重入**：`urctl init` 命令可手动触发初始化

---

## 2. 安装模式详解

### 2.1 裸机 ISO 安装

**ISO 构建**：

```
使用 Cubic (Custom Ubuntu ISO Creator) + Ubuntu Server 24.04 minimal ISO

定制内容:
1. 预置 autoinstall.yaml（自动分区、安装 Ubuntu 最小化系统）
2. 添加 UbuntuRouter apt 源
3. 安装后的 late-commands 阶段自动安装 UbuntuRouter 包
4. 配置 grub 启动参数（console=tty0 console=ttyS0 等）

ISO 构建脚本（伪代码）:
  #!/bin/bash
  # 下载 Ubuntu Server ISO
  wget https://releases.ubuntu.com/24.04/ubuntu-24.04-live-server-amd64.iso
  
  # 使用 Cubic 或 livefs-edit 定制
  cubic-cli \
    --input ubuntu-24.04-live-server-amd64.iso \
    --output ubunturouter-1.0.0-amd64.iso \
    --add-repo "deb https://ppa.ubunturouter.org/stable noble main" \
    --preseed preseed.cfg
  
  # 或使用 autoinstall:
  xorriso -as mkisofs ... -append-partition ... \
    --embedded-content autoinstall.yaml
```

**autoinstall.yaml**：
```yaml
# 嵌入 ISO 的自动安装配置
version: 1
locale: zh_CN
keyboard:
  layout: cn
network:
  version: 2
  ethernets:
    id0:
      match:
        name: "en*"
      dhcp4: true
storage:
  version: 2
  layout:
    name: lvm
identity:
  hostname: router
  username: uradmin
  password: "$6$..."        # 安装时临时密码，首次引导强制修改
ssh:
  allow-pw: true
  authorized-keys: []
late-commands:
  # 自动安装 UbuntuRouter
  - curtin in-target -- apt-get update
  - curtin in-target -- apt-get install -y ubunturouter-core ubunturouter-web
  # 标记为首次启动
  - curtin in-target -- touch /etc/ubunturouter/.fresh-install
  # 清理临时密码
  - curtin in-target -- passwd -l uradmin
```

### 2.2 apt 安装（已有系统）

```bash
# 一键安装脚本: curl -fsSL https://get.ubunturouter.org | bash

# 安装脚本流程:
#!/bin/bash
set -e

echo "=== UbuntuRouter Installer ==="

# 1. 检测系统
if ! grep -q "Ubuntu" /etc/os-release; then
    echo "错误: 仅支持 Ubuntu 系统"
    exit 1
fi

UBUNTU_VERSION=$(grep VERSION_ID /etc/os-release | cut -d= -f2 | tr -d '"')
if [[ "$UBUNTU_VERSION" != "22.04" && "$UBUNTU_VERSION" != "24.04" && "$UBUNTU_VERSION" != "26.04" ]]; then
    echo "警告: 未在 Ubuntu $UBUNTU_VERSION 上验证"
fi

# 2. 添加 apt 源
echo "deb [signed-by=/usr/share/keyrings/ubunturouter.gpg] \
    https://ppa.ubunturouter.org/stable $(lsb_release -cs) main" \
    | sudo tee /etc/apt/sources.list.d/ubunturouter.list

curl -fsSL https://ppa.ubunturouter.org/key.gpg | \
    sudo gpg --dearmor -o /usr/share/keyrings/ubunturouter.gpg

sudo apt-get update

# 3. 选择安装模式
echo "请选择安装模式:"
echo "  1) 最小安装 (纯路由)"
echo "  2) 标准安装 (路由 + 容器 + 应用市场)"
echo "  3) 完整安装 (路由 + 容器 + VM + 应用市场)"
read -p "选择 [1-3]: " mode

case $mode in
    1) PACKAGES="ubunturouter-core ubunturouter-web" ;;
    2) PACKAGES="ubunturouter-core ubunturouter-web ubunturouter-container ubunturouter-appstore" ;;
    3) PACKAGES="ubunturouter-core ubunturouter-web ubunturouter-container ubunturouter-vm ubunturouter-appstore" ;;
esac

# 4. 安装
sudo apt-get install -y $PACKAGES

# 5. 初始化
echo "正在初始化系统..."
sudo mkdir -p /etc/ubunturouter
sudo touch /etc/ubunturouter/.fresh-install
sudo systemctl enable --now ubunturouter-init

echo "安装完成！请使用浏览器访问路由器地址开始配置。"
```

### 2.3 虚拟机镜像 (qcow2/ova)

**镜像构建**（使用 Packer）：

```hcl
# packer.pkr.hcl
source "qemu" "ubunturouter" {
  iso_url           = "ubuntu-24.04-live-server-amd64.iso"
  iso_checksum      = "sha256:xxx"
  output_directory  = "output"
  disk_size         = "8G"
  format            = "qcow2"
  memory            = 2048
  net_device        = "virtio-net"
  disk_interface     = "virtio"
  ssh_username      = "uradmin"
  ssh_password      = "ubunturouter"
  ssh_timeout       = "20m"
  boot_wait         = "10s"
  http_directory    = "http"
  boot_command      = [
    "<esc><wait>",
    "install autoinstall ds=nocloud-net;s=http://{{ .HTTPIP }}:{{ .HTTPPort }}/",
    "<enter>"
  ]
}

build {
  sources = ["source.qemu.ubunturouter"]

  provisioner "shell" {
    inline = [
      "sudo apt-get update",
      "sudo apt-get install -y ubunturouter-core ubunturouter-web ubunturouter-container ubunturouter-appstore",
      "sudo touch /etc/ubunturouter/.fresh-install",
      "sudo systemctl enable ubunturouter-init",
      "sudo rm -f /etc/ssh/ssh_host_*",  # 首次启动重新生成
    ]
  }

  post-processor "manifest" {
    output = "manifest.json"
    custom_data = {
      version = "1.0.0"
      build_date = timestamp()
    }
  }
}
```

**镜像产物**：
```
ubunturouter-1.0.0-amd64.qcow2   # ~500MB xz 压缩
ubunturouter-1.0.0-amd64.ova     # ~500MB xz 压缩
ubunturouter-1.0.0-amd64.vmdk    # VMware 格式
```

### 2.4 ARM 镜像

**构建流程**：

```bash
#!/bin/bash
# ARM 镜像构建

PLATFORM=${1:-rk3568}   # rk3568, rk3588, rpi5

# 1. 使用 ubuntu-image 创建基础 rootfs
ubuntu-image --image-size 4G \
  --snaps ubunturouter-core,ubunturouter-web \
  --deb http://ports.ubuntu.com/ubuntu-ports \
  --extra-snaps ubunturouter-container,ubunturouter-appstore \
  --pre-install-hook pre-install.sh \
  --post-install-hook post-install.sh

# 2. 安装平台特定内核
case $PLATFORM in
  rk3568)
    # linux-rockchip 内核 + rk3568 dtb
    mkdir -p rootfs/boot/dtbs
    cp rk3568.dtb rootfs/boot/dtbs/
    chroot rootfs apt-get install -y linux-image-rockchip-rk3568
    ;;
  rpi5)
    # 树莓派内核 + 固件
    chroot rootfs apt-get install -y linux-image-rpi-v8 raspberrypi-firmware
    ;;
esac

# 3. 写入镜像文件
dd if=/dev/zero of=ubunturouter-$PLATFORM.img bs=1M count=4000
# 分区: boot (512MB) + rootfs (剩余)
# 写入 rootfs + u-boot
```

---

## 3. Initializer 实现

```python
# ubunturouter/engine/initializer.py

import os, subprocess, json, re, time, yaml
from pathlib import Path
from typing import List, Optional

class NicInfo:
    """网口信息"""
    name: str
    speed: Optional[int]
    link: bool
    driver: Optional[str]
    mac: str

class RoleAssignment:
    """角色分配结果"""
    mode: str       # "single" / "multi" / "none"
    wan: Optional[str]
    lans: List[str]
    wan_uplink: Optional[str] = None  # 单口模式


class Initializer:
    """
    首次启动初始化器
    触发: systemd oneshot service (ubunturouter-init.service)
    
    执行条件:
    - /etc/ubunturouter/config.yaml 不存在
    - /etc/ubunturouter/.fresh-install 存在（安装标记）
    """

    CONFIG_PATH = Path("/etc/ubunturouter/config.yaml")
    FRESH_FLAG = Path("/etc/ubunturouter/.fresh-install")
    INIT_DONE = Path("/etc/ubunturouter/.initialized")

    # ─── 入口 ───────────────────────────────────────

    def run(self):
        """
        执行初始化
        
        完整流程:
        1. 检查是否应该初始化
        2. 检测物理网口
        3. 自动分配角色
        4. 生成初始配置
        5. Apply 配置（netplan + nftables + dnsmasq）
        6. 启动 API Server 和 Web 向导
        7. 创建 .initialized 标记
        """
        if not self.should_init():
            return
        
        print("[Initializer] 开始首次初始化...")
        
        nics = self.detect_physical_nics()
        if not nics:
            print("[Initializer] 错误: 未检测到物理网口")
            self.fallback_console_wizard()
            return
        
        assignment = self.auto_assign_roles(nics)
        config = self.generate_initial_config(assignment)
        
        self.apply_initial_config(config)
        self.start_web_wizard()
        
        # 标记完成
        self.INIT_DONE.touch()

    def should_init(self) -> bool:
        """是否需要初始化"""
        # config.yaml 已存在 → 已完成初始化
        if self.CONFIG_PATH.exists():
            return False
        # 没有安装标记 → 不是首次启动
        if not self.FRESH_FLAG.exists():
            return False
        # .initialized 标记存在 → 已完成
        if self.INIT_DONE.exists():
            return False
        return True

    # ─── 网口检测 ───────────────────────────────────

    def detect_physical_nics(self) -> List[NicInfo]:
        """
        检测物理网口
        
        实现:
        1. 遍历 /sys/class/net/
        2. 排除: lo, docker*, br-*, veth*, virbr*, tun*, bond*
        3. 检查是否物理口: /sys/class/net/{iface}/device/driver 存在
        4. 获取速率: ethtool
        5. 获取链路状态: /sys/class/net/{iface}/carrier
        """
        import glob
        
        nics = []
        sys_net = Path('/sys/class/net')
        
        for iface_path in sorted(sys_net.iterdir()):
            name = iface_path.name
            
            # 排除虚拟接口
            if name == 'lo':
                continue
            if any(name.startswith(p) for p in ['docker', 'br-', 'veth', 'virbr', 'tun', 'bond', 'vlan']):
                continue
            
            device_driver = iface_path / 'device' / 'driver'
            if not device_driver.exists():
                continue  # 非物理口
            
            # 链路状态
            carrier = iface_path / 'carrier'
            link = carrier.read_text().strip() == '1' if carrier.exists() else False
            
            # MAC
            addr_file = iface_path / 'address'
            mac = addr_file.read_text().strip() if addr_file.exists() else ''
            
            # 速率 (ethtool)
            speed = None
            if link:
                try:
                    result = subprocess.run(
                        ['ethtool', name], capture_output=True, text=True, timeout=5
                    )
                    match = re.search(r'Speed:\s+(\d+)Mb/s', result.stdout)
                    if match:
                        speed = int(match.group(1))
                except:
                    pass
            
            # 驱动
            driver = None
            if device_driver.exists():
                driver = device_driver.resolve().name
            
            nics.append(NicInfo(
                name=name, speed=speed, link=link,
                driver=driver, mac=mac
            ))
        
        return nics

    # ─── 角色自动分配 ──────────────────────────────

    def auto_assign_roles(self, nics: List[NicInfo]) -> RoleAssignment:
        """
        自动分配 WAN/LAN / WANLAN
        
        规则:
        1 个网口 → WANLAN
        2 个网口 → 低速率=WAN, 高速率=LAN
        3+ 网口 → 最低速率=WAN, 其余桥接=br-lan
        同速率 → 按接口名字母序，第一个=WAN
        """
        
        if len(nics) == 1:
            nic = nics[0]
            return RoleAssignment(
                mode="single",
                wan=None,
                lans=[nic.name],
                wan_uplink=nic.name
            )
        
        # 按速率排序（升序），同速率按名称排序
        sorted_nics = sorted(nics, key=lambda n: (
            0 if n.speed else -1,      # 未知速率优先作为 WAN
            n.speed if n.speed else 0,  # 低速率优先作为 WAN
            n.name                       # 字母序
        ))
        
        wan = sorted_nics[0]
        lans = sorted_nics[1:]
        
        return RoleAssignment(
            mode="multi",
            wan=wan.name,
            lans=[l.name for l in lans]
        )

    # ─── 生成初始配置 ─────────────────────────────

    def generate_initial_config(self, assignment: RoleAssignment) -> dict:
        """
        生成初始 config.yaml
        
        固定默认值:
        - LAN 网关: 192.168.21.1/24
        - DHCP 池: 192.168.21.50 - 192.168.21.200
        - WAN: DHCP
        - 防火墙: 默认 drop
        - DNS: 223.5.5.5, 119.29.29.29
        """
        
        config = {
            "format_version": "1.0",
            "system": {
                "hostname": "router",
                "timezone": "Asia/Shanghai"
            },
            "interfaces": [],
            "routing": {
                "multi_wan": {
                    "enabled": False,
                    "strategy": "failover",
                    "wans": []
                }
            },
            "firewall": {
                "default_policy": {
                    "input": "drop",
                    "forward": "drop",
                    "output": "accept"
                },
                "zones": {}
            },
            "dhcp": {
                "interface": "br-lan",
                "range_start": "192.168.21.50",
                "range_end": "192.168.21.200",
                "gateway": "192.168.21.1",
                "dns": ["192.168.21.1"],
                "lease_time": 86400
            },
            "dns": {
                "upstream": ["223.5.5.5", "119.29.29.29"],
                "blocking": False
            }
        }
        
        if assignment.mode == "single":
            # 单网口 WANLAN 模式
            config["interfaces"] = [{
                "name": "wanlan0",
                "type": "ethernet",
                "device": assignment.wan_uplink,
                "role": "wanlan",
                "ipv4": {
                    "method": "static",
                    "address": "192.168.21.1/24"
                },
                "wan_uplink": {
                    "method": "dhcp"
                },
                "firewall": {"zone": "wanlan"}
            }]
            config["firewall"]["zones"] = {
                "wanlan": {
                    "name": "wanlan",
                    "masquerade": True,
                    "forward_to": [],
                    "input": "drop",
                    "forward": "drop",
                    "output": "accept"
                }
            }
        else:
            # 多网口模式
            config["interfaces"] = [{
                "name": "wan0",
                "type": "ethernet",
                "device": assignment.wan,
                "role": "wan",
                "ipv4": {"method": "dhcp"},
                "firewall": {"zone": "wan"}
            }, {
                "name": "br-lan",
                "type": "bridge",
                "device": "br-lan",
                "ports": assignment.lans,
                "role": "lan",
                "ipv4": {
                    "method": "static",
                    "address": "192.168.21.1/24"
                },
                "firewall": {"zone": "lan"}
            }]
            config["firewall"]["zones"] = {
                "wan": {
                    "name": "wan",
                    "masquerade": True,
                    "forward_to": [],
                    "input": "drop",
                    "forward": "drop",
                    "output": "accept"
                },
                "lan": {
                    "name": "lan",
                    "masquerade": False,
                    "forward_to": ["wan"],
                    "input": "accept",
                    "forward": "accept",
                    "output": "accept"
                }
            }
        
        return config

    # ─── Apply 初始配置 ────────────────────────────

    def apply_initial_config(self, config: dict) -> None:
        """
        应用初始配置
        
        1. 写入 /etc/ubunturouter/config.yaml
        2. 生成 netplan 配置 → netplan apply
        3. 生成 nftables 配置 → nft -f
        4. 生成 dnsmasq 配置 → systemctl start dnsmasq
        """
        
        import yaml
        
        # 1. 写配置
        self.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(self.CONFIG_PATH, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        # 2. 生成 netplan
        self._write_netplan(config)
        
        # 3. 应用网络
        subprocess.run(['netplan', 'apply'], timeout=30)
        time.sleep(3)  # 等待网络就绪
        
        # 4. 生成 nftables
        self._write_nftables(config)
        subprocess.run(['nft', '-f', '/etc/nftables.d/ubunturouter.conf'], timeout=10)
        
        # 5. 启动 dnsmasq
        self._write_dnsmasq(config)
        subprocess.run(['systemctl', 'enable', '--now', 'dnsmasq'], timeout=15)
        
        # 6. 启动 API Server
        subprocess.run(['systemctl', 'enable', '--now', 'ubunturouter-api'], timeout=15)

    # ─── 启动 Web 向导 ─────────────────────────────

    def start_web_wizard(self):
        """
        启动 Web 初始化向导
        
        向导入口: http://192.168.21.1
        功能:
        1. 展示检测到的网口和角色分配
        2. 用户可手动调整
        3. 设置管理员密码
        4. 设置 WiFi (如有无线网卡)
        5. 确认后完成初始化
        """
        print(f"[Initializer] 初始化完成！")
        print(f"[Initializer] 请用浏览器访问 http://192.168.21.1")
        print(f"[Initializer] 完成初始化向导")

    # ─── 备用交互初始化 ────────────────────────────

    def fallback_console_wizard(self):
        """
        控制台交互初始化（无网口时的备用方案）
        
        当检测不到物理网口时，提示用户在控制台完成配置
        """
        print("\n" + "=" * 50)
        print("  未检测到物理网口！")
        print("  请连接网口后重试，或手动创建 /etc/ubunturouter/config.yaml")
        print("=" * 50)
```

---

## 4. ubunturouter-init.service 设计

```ini
# /etc/systemd/system/ubunturouter-init.service

[Unit]
Description=UbuntuRouter First Boot Initializer
Documentation=https://docs.ubunturouter.org
ConditionPathExists=/etc/ubunturouter/.fresh-install
After=network.target systemd-udev-settle.service
Before=networking.service

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 -m ubunturouter.engine.initializer
RemainAfterExit=yes
StandardOutput=journal+console

[Install]
WantedBy=multi-user.target
```

---

## 5. urctl 命令行工具

```python
# /usr/bin/urctl — CLI 入口

class UrctlCLI:
    """命令行管理工具"""

    def init(self, args):
        """
        urctl init [--auto] [--wan=IFACE] [--lan=IFACE]
        
        --auto: 全自动模式，跳过确认
        --wan: 手动指定 WAN 口
        --lan: 手动指定 LAN 口（逗号分隔多个）
        """
    
    def status(self, args):
        """
        urctl status
        
        显示系统状态:
        - 运行时间
        - 网口状态
        - WAN/LAN 角色
        - 服务运行状态
        - 版本信息
        """
    
    def apply(self, args):
        """
        urctl apply [--config=PATH]
        
        应用配置变更
        """
    
    def doctor(self, args):
        """
        urctl doctor
        
        系统诊断:
        - 检查网口配置
        - 检查防火墙规则
        - 检查 DHCP 服务
        - 检查 DNS 解析
        - 检查 WAN 连通性
        - 报告发现的问题
        """
```

---

## 6. 安装后文件布局

```
/etc/
├── ubunturouter/
│   ├── config.yaml            # 统一配置（初始化后自动生成）
│   ├── .fresh-install         # 安装标记（初始化后删除）
│   ├── .initialized           # 初始化完成标记
│   └── blocked.hosts          # 广告拦截 hosts（可选）

/var/
├── lib/
│   └── ubunturouter/
│       ├── snapshots/         # 配置快照
│       ├── appstore/          # 应用市场数据
│       └── apps/              # 已安装应用（Docker Compose 项目）

/etc/
├── netplan/
│   └── 01-ubunturouter.yaml   # 网络配置（由 Config Engine 管理）
├── nftables.d/
│   └── ubunturouter.conf      # 防火墙规则
├── dnsmasq.d/
│   └── ubunturouter.conf      # DHCP/DNS
├── wireguard/
│   └── wg0.conf               # WireGuard
└── frr/
    └── frr.conf               # FRR 路由
```

---

## 7. 测试用例

| 测试场景 | 预期 |
|----------|------|
| ISO 安装: U 盘引导 | 进入 Ubuntu 安装器，自动分区 |
| ISO 安装: 安装完成重启 | 系统正常启动，SSH 可达 |
| apt 安装: ubunturouter-core | deb 包安装成功 |
| apt 安装: 已有系统上安装 | 不破坏现有网络配置 |
| 首次启动: 单网口 | 自动识别单口，WANLAN 模式 |
| 首次启动: 双网口 | enp1s0(1000M)=WAN, enp2s0(1000M)=br-lan |
| 首次启动: 四网口 | 最低速=WAN，其余桥接 |
| 首次启动后: Web 向导可达 | http://192.168.21.1 可访问 |
| urctl init | CLI 交互初始化 |
| urctl init --auto | 全自动初始化 |
| urctl doctor | 诊断报告输出 |
| .fresh-install 不存在 | 跳过初始化 |
| .initialized 存在 | 跳过初始化 |
