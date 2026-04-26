# 安装与部署方案

> 版本: v1.0 | 日期: 2026-04-25 | 状态: 初稿

## 1. 安装模式总览

| 模式 | 适用场景 | 入口 | 产物 |
|------|----------|------|------|
| 裸机 ISO | 全新 x86/ARM 物理机 | USB/光盘引导 | 完整系统 |
| apt 部署 | 已有 Ubuntu 系统 | `apt install` | 叠加安装 |
| 虚拟机镜像 | Proxmox/ESXi/KVM | 导入 qcow2/vmdk/ova | 预装 VM |
| ARM 镜像 | RK3568/RPi5/NanoPi | dd 写入 eMMC/SD | 预装系统 |
| 云镜像 | 阿里云/AWS | cloud-init | 云端实例 |

## 2. 裸机 ISO 安装

### 2.1 ISO 构建流程

```
Ubuntu Server 24.04 LTS (minimal) 作为 base
    │
    ├── 使用 Cubic (Custom Ubuntu ISO Creator) 定制
    │   - 预添加 UbuntuRouter apt 源
    │   - 预配置 Subiquity 自动安装参数
    │   - 集成 UbuntuRouter 安装向导（安装模式选择）
    │
    ├── 输出: ubunturouter-{version}-amd64.iso
    │
    └── ARM 镜像: 使用 ubuntu-image + 自定义 rootfs
        输出: ubunturouter-{version}-arm64.img
```

### 2.2 自动安装配置 (autoinstall)

```yaml
# embedded in ISO: /autoinstall.yaml
version: 1
locale: zh_CN
keyboard:
  layout: cn
network:
  version: 2
  ethernets:
    # 安装阶段：第一个网口 DHCP，确保能联网
    id0:
      match:
        name: "en*"
      dhcp4: true
storage:
  version: 2
  layout:
    name: lvm          # LVM 方便后续扩容
identity:
  hostname: router
  username: uradmin
  password: "$6$..."   # 默认密码，首次登录强制修改
late-commands:
  - curtin in-target -- apt-add-repository -y ppa:ubunturouter/stable
  - curtin in-target -- apt-get update
  - curtin in-target -- apt-get install -y ubunturouter-core ubunturouter-web
  # 安装模式选择由 UbuntuRouter 安装向导处理
```

### 2.3 用户操作步骤

1. 下载 ISO，`dd` 写入 U 盘
2. 插入目标机器，BIOS 选择 U 盘启动
3. 进入安装器 → 选择语言 → 自动分区（或手动）
4. 选择安装模式：最小 / 标准 / 完整
5. 等待安装完成 → 自动重启
6. 首次启动 → 自动初始化网络 → 进入 Web 向导

## 3. 已有系统部署

### 3.1 一键安装脚本

```bash
# curl -fsSL https://get.ubunturouter.org | sudo bash
#
# 或分步操作：

# 1. 添加 apt 源
sudo add-apt-repository -y ppa:ubunturouter/stable
sudo apt-get update

# 2. 选择安装模式
# 最小安装（纯路由）
sudo apt-get install -y ubunturouter-core ubunturouter-web

# 标准安装（路由+容器+应用市场）
sudo apt-get install -y ubunturouter-core ubunturouter-web ubunturouter-container ubunturouter-appstore

# 完整安装（路由+容器+VM+应用市场）
sudo apt-get install -y ubunturouter-core ubunturouter-web ubunturouter-container ubunturouter-vm ubunturouter-appstore

# 3. 初始化
sudo urctl init
```

### 3.2 初始化命令

```bash
# urctl init — 交互式初始化
# 自动检测网口 → 确认分配 → 生成配置 → 启动服务 → 打开向导

sudo urctl init           # 交互模式
sudo urctl init --auto    # 全自动模式（信任自动检测结果）
sudo urctl init --wan=enp1s0 --lan=enp2s0  # 手动指定
```

### 3.3 注意事项

- 安装前检查当前网络配置，不破坏已有连通性
- 如果已有 dnsmasq/nftables 运行，提示用户确认接管
- 安装后防火墙默认策略为 drop，确保安全

## 4. 虚拟机镜像

### 4.1 镜像格式

| 格式 | 平台 | 说明 |
|------|------|------|
| qcow2 | Proxmox/libvirt | 推荐，支持快照 |
| vmdk | VMware ESXi/Workstation | VMware 原生 |
| ova | ESXi/VirtualBox | 通用导入 |
| raw | 通用 | 无压缩，最大 |

### 4.2 镜像构建

```bash
# 使用 Packer 构建预装镜像
# packer-template.pkr.hcl

# 镜像内容：
# - Ubuntu Server 24.04 minimal
# - UbuntuRouter 完整安装
# - 预配置 cloud-init
# - 默认 rootfs: 8GB (可在线扩容)
```

### 4.3 使用方式

**Proxmox**：
1. 下载 qcow2 镜像
2. 创建 VM → Import disk → 选择 qcow2
3. 配置网口（virtio 或 VFIO 直通）
4. 启动 → 进入 Web 向导

**ESXi**：
1. 下载 OVA
2. Deploy OVF template → 选择 OVA
3. 配置网口
4. 启动 → 进入 Web 向导

### 4.4 cloud-init 支持

```yaml
# cloud-init 网络配置注入（可选）
# 用户数据 (user-data):
#cloud-config
password: uradmin
chpasswd:
  expire: true
runcmd:
  - urctl init --auto

# 网络配置 (network-config):
version: 2
ethernets:
  id0:
    match:
      name: "en*"
    dhcp4: true
```

## 5. ARM 镜像

### 5.1 支持平台

| 平台 | 镜像 | 写入方式 |
|------|------|----------|
| RK3568 (NanoPi R5S/R5C) | ubunturouter-rk3568.img | dd → eMMC |
| RK3588 (NanoPi R6S/R6C) | ubunturouter-rk3588.img | dd → eMMC |
| Raspberry Pi 5 | ubunturouter-rpi5.img | dd → SD |
| 通用 ARM64 | ubunturouter-aarch64.img | dd → 任意存储 |

### 5.2 镜像构建

```
使用 ubuntu-image + 自定义 rootfs:
1. 基于 Ubuntu arm64 rootfs
2. 安装平台特定内核 (linux-rockchip / linux-rpi)
3. 安装 UbuntuRouter 包
4. 配置 u-boot / extlinux
5. 优化：减少写入（log2ram, fstrim定时器）
```

### 5.3 写入与启动

```bash
# 写入 SD 卡
xzcat ubunturouter-rpi5.img.xz | sudo dd of=/dev/sdX bs=4M status=progress

# 写入 eMMC (通过 USB 烧录模式)
xzcat ubunturouter-rk3568.img.xz | sudo dd of=/dev/sdX bs=4M status=progress

# 启动后自动初始化
```

## 6. 网络自动初始化

### 6.1 初始化规则

```
首次启动检测流程：

1. 检测 /etc/ubunturouter/config.yaml 是否存在
   - 存在 → 正常启动
   - 不存在 → 进入初始化

2. 网口探测
   - 枚举 /sys/class/net/ 下所有接口
   - 排除: lo, docker*, br-*, veth*, virbr*
   - 仅保留物理以太网口
   - ethtool 获取每个口的 Speed 和 Link detected

3. 自动分配
   ┌────────────┬─────────────────────────────────────────┐
   │ 网口数     │ 分配策略                                │
   ├────────────┼─────────────────────────────────────────┤
   │ 1          │ WANLAN 模式:                             │
   │            │   该口 = LAN (192.168.21.1/24)          │
   │            │   WAN上行 = DHCP (同口)                  │
   ├────────────┼─────────────────────────────────────────┤
   │ 2          │ 速率低 = WAN (DHCP)                     │
   │            │ 速率高 = LAN (192.168.21.1/24)          │
   ├────────────┼─────────────────────────────────────────┤
   │ 3+         │ 速率最低 = WAN (DHCP)                   │
   │            │ 其余桥接 = br-lan (192.168.21.1/24)     │
   └────────────┴─────────────────────────────────────────┘
   
   速率相同时: 按接口名排序 (enp1s0 < enp2s0 < ...)
   enp1s0 = WAN, 其余 = LAN

4. 生成初始配置
   - LAN: 192.168.21.1/24
   - DHCP: 192.168.21.50 - 192.168.21.200
   - WAN: DHCP (默认)
   - 防火墙: input=drop, forward=drop, output=accept
   - NAT: masquerade on WAN
   - DNS: 223.5.5.5, 119.29.29.29

5. Apply 并启动 Web 向导
```

### 6.2 单网口 WANLAN 模式

单网口是常见场景（如虚拟机、单口小主机），需要特殊处理：

**方案选择**：
- **默认方案**：单口 NAT 模式 — 该口配 192.168.21.1，上行 DHCP 获取辅助 IP
- **可选方案**：VLAN 模式 — 需配合 VLAN 交换机

**单口 NAT 模式网络拓扑**：
```
[光猫] ──── [UbuntuRouter 单口] ──── [交换机/AP] ──── [设备]
                enp1s0
            192.168.21.1/24 (LAN)
            + DHCP获取WAN IP (辅助地址)
```

**向导提示**：
- "检测到您的设备仅有 1 个网口，已自动启用单口模式"
- "单口模式下，该网口同时承载 WAN 和 LAN 流量"
- "建议：如需更好的性能和隔离，请添加额外网口"

### 6.3 速率检测细节

```python
# 伪代码
def detect_nic_speed(iface: str) -> int:
    """通过 ethtool 获取网口速率 (Mbps)"""
    # ethtool enp1s0 | grep Speed
    # Speed: 1000Mb/s
    # 无链路时: Speed: Unknown!
    # 返回: 10, 100, 1000, 2500, 10000, -1(未知)
    
def auto_assign_roles(interfaces: list) -> dict:
    speeds = {iface: detect_nic_speed(iface) for iface in interfaces}
    
    if len(interfaces) == 1:
        return {"role": "wanlan", "device": interfaces[0]}
    
    # 速率最低 → WAN, 速率 -1 (未知) 排最前
    sorted_ifaces = sorted(interfaces, key=lambda x: speeds[x] if speeds[x] > 0 else 0)
    wan = sorted_ifaces[0]
    lans = sorted_ifaces[1:]
    return {"wan": wan, "lans": lans}
```

## 7. 发布制品清单

| 制品 | 架构 | 格式 | 大小(估) | 更新频率 |
|------|------|------|----------|----------|
| ubunturouter-{ver}-amd64.iso | x86_64 | ISO | ~800MB | 版本发布 |
| ubunturouter-{ver}-arm64.img | ARM64 | raw img | ~600MB | 版本发布 |
| ubunturouter-{ver}-amd64.qcow2 | x86_64 | qcow2 | ~500MB | 版本发布 |
| ubunturouter-{ver}-amd64.ova | x86_64 | OVA | ~500MB | 版本发布 |
| ubunturouter-rk3568-{ver}.img | RK3568 | raw img | ~400MB | 版本发布 |
| ubunturouter-rpi5-{ver}.img | RPi5 | raw img | ~400MB | 版本发布 |
| ubunturouter-core_{ver}_amd64.deb | x86_64 | deb | ~5MB | 版本发布 |
| ubunturouter-core_{ver}_arm64.deb | ARM64 | deb | ~5MB | 版本发布 |
