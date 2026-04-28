# UbuntuRouter 下一阶段开发计划

> 本计划合并了：
> 1. iStoreOS 差距分析（108 项功能对比）
> 2. 1Panel AppStore 对标
> 3. 用户新增的 4 项需求
>
> 版本: v1.0 | 日期: 2026-04-28

---

## 目录

- [Roadmap 总览](#roadmap-总览)
- [New Feature 1: 自定义应用框架 + AppStore 重构](#new-feature-1-自定义应用框架--appstore-重构)
- [New Feature 2: VPN 配置（替代 Tailscale）+ 协议支持](#new-feature-2-vpn-配置替代-tailscale--协议支持)
- [New Feature 3: 应用流编排重构（n8n 风格）](#new-feature-3-应用流编排重构n8n-风格)
- [New Feature 4: 语音助手集成（Google/Amazon/Apple/Home Assistant）](#new-feature-4-语音助手集成googleamazonapplehome-assistant)
- [Sprint 1: iStoreOS P1 补齐](#sprint-1-istoreos-p1-补齐)
- [Sprint 2: iStoreOS P2 补齐](#sprint-2-istoreos-p2-补齐)
- [Sprint 3: iStoreOS P3 补齐](#sprint-3-istoreos-p3-补齐)

---

## Roadmap 总览

|阶段 | 内容 | 预估工作量 | 优先级 |
|-----|------|:---------:|:------:|
| Sprint 1 | iStoreOS P1 补齐（防火墙增强+实时图表+DHCP池+NAT回环） | ~6d | 🔴 P0 |
| Sprint 2 | VPN 配置重构（移除Tailscale+新增PPTP/IPSec/OpenVPN） | ~4d | 🔴 P0 |
| Sprint 3 | 应用流编排重构（n8n风格画板+设备/应用/规则/接口节点） | ~10d | 🔴 P0 |
| Sprint 4 | 自定义应用框架+AppStore重构（按1Panel标准） | ~8d | 🟠 P1 |
| Sprint 5 | iStoreOS P2 补齐（TurboACC+QoS+桥接+DDNS+UPnP） | ~8d | 🟠 P1 |
| Sprint 6 | 语音助手集成（Google/Amazon/Apple/HomeAssistant） | ~5d | 🟡 P2 |
| Sprint 7 | iStoreOS P3 补齐（无线高级+接口高级+FTP/LED/SNMP） | ~5d | 🟢 P3 |

---

# New Feature 1: 自定义应用框架 + AppStore 重构

## 背景
用户未来有些应用不在 AppStore 中，需要支持用户自行安装应用。应用可以是 Docker 容器、Docker Compose 项目、APT 包、或运行脚本。安装后需支持自启动、延时启动等。

## 1.1 自定义应用框架设计

### 应用类型体系

```
应用 (App)
├── Docker 应用          — 单个容器 (docker run)
├── Docker Compose 应用  — 多容器编排 (docker-compose.yml)
├── APT 包应用          — 通过 apt 安装的系统软件包
└── 脚本应用            — 自定义运行脚本 (bash/python/二进制)
```

### 应用定义文件格式 (app.yaml)

借鉴 1Panel 的 data.yml 设计，但扩展支持多种部署类型：

```yaml
# ─── 顶层元数据 (对标 1Panel) ───
name: my-custom-app
title: 我的自定义应用
version: "1.0.0"
description: "用户自定义安装的应用"
category: "自定义应用"    # 特殊分类标签
tags: [自定义, 用户安装]

# ─── 部署类型 (UbuntuRouter 扩展) ───
deploy:
  type: docker            # docker / docker-compose / apt / script
  # ── Docker 模式 ──
  image: nginx:latest
  container_name: my-nginx
  ports:
    - "8080:80"
  volumes:
    - ./data:/usr/share/nginx/html
  environment:
    - NGINX_HOST=example.com
  restart: always          # no / on-failure / unless-stopped / always
  depends_on: []           # 依赖的其他自定义应用

  # ── Docker Compose 模式 ──
  compose: |
    version: '3'
    services:
      app:
        image: ${IMAGE}
        ...

  # ── APT 模式 ──
  apt:
    packages:
      - htop
      - iotop
    ppa: ""                # 可选 PPA

  # ── 脚本模式 ──
  script:
    install: |
      #!/bin/bash
      curl -fsSL https://example.com/install.sh | bash
    uninstall: |
      #!/bin/bash
      # 清理逻辑
    start: systemctl start my-service
    stop: systemctl stop my-service
    status: systemctl is-active my-service
```

### 核心管理器: AppLifecycleManager

```python
class AppLifecycleManager:
    """
    统一管理所有类型的自定义应用生命周期
    """
    def install(self, app_def: AppDefinition) -> InstallResult
    def uninstall(self, app_id: str) -> bool
    def start(self, app_id: str) -> bool
    def stop(self, app_id: str) -> bool
    def restart(self, app_id: str) -> bool
    def status(self, app_id: str) -> AppStatus
    def get_logs(self, app_id: str, lines: int) -> str
```

### 自启动管理

- 基于 systemd 服务单元：为每个自定义应用生成 `.service` 文件
- 支持 `restart: always/no/on-failure/unless-stopped`
- 支持延时启动：`ExecStartPre=/bin/sleep 10` 或 `RestartSec=10`
- 支持依赖排序：`After=network-online.target docker.service`

### 应用统一注册到 AppStore

自定义应用安装后自动注册到 AppStore，出现在"自定义应用"分类下，跟商店应用一样可管理（启动/停止/卸载/查看状态）。

## 1.2 AppStore 增强（按 1Panel 标准）

| 维度 | 当前状态 | 目标 |
|------|---------|------|
| 参数表单 | 仅 text 类型 | 7种类型: text/number/password/select/boolean/service/apps |
| 参数验证 | 无 | paramPort/paramCommon 验证规则 |
| 自动随机密码 | 无 | random: true 支持 |
| 版本管理 | 单一版本 | 多版本目录 (支持 crossVersionUpdate) |
| 安装约束 | 无 | architectures/gpuSupport/memoryRequired |
| 子表单联动 | 无 | child 字段实现动态表单 |
| 脚本支持 | 仅 Docker Compose | install/upgrade 脚本 |
| 跨版本升级 | 无 | crossVersionUpdate 标记 |

---

# New Feature 2: VPN 配置（替代 Tailscale）+ 协议支持

## 背景
某些国家不允许使用 Tailscale。将其移除，在"网络配置"下新增"VPN 配置"，支持通用 VPN 协议。

## 2.1 架构变更

### 移除 Tailscale
- 删除 `vpn.py` 中的 Tailscale 相关端点
- 删除前端 Vue 页面中的 Tailscale 部分
- 删除 `addons/tailscale/` 模块

### 新增 VPN 配置模块

新的菜单结构：
```
网络配置
  ├── 接口配置
  ├── 无线管理
  ├── DNS 配置
  ├── 物理端口
  ├── 网络诊断
  └── VPN 配置           ← 新增
      ├── PPTP
      ├── IPSec/IKEv2
      └── OpenVPN
```

### VPN 协议支持详情

#### PPTP (Point-to-Point Tunneling Protocol)
```
后端: /api/v1/vpn/pptp/*
功能:
  - 启用/禁用 PPTP 服务
  - 配置: 服务器 IP, DNS, MPPE 加密
  - 用户管理: 用户名/密码 CRUD
  - 连接状态查看
  - 日志查看
实现: pptpd (pptpd + chap-secrets)
```

#### IPSec/IKEv2
```
后端: /api/v1/vpn/ipsec/*
功能:
  - 启用/禁用 IPSec 服务
  - 配置: 预共享密钥(PSK), 证书
  - IKEv2 用户名/密码认证
  - 客户端配置导出(.mobileconfig 等)
  - 连接状态查看
实现: strongSwan (ipsec.conf + certs)
```

#### OpenVPN
```
后端: /api/v1/vpn/openvpn/*
功能:
  - 启用/禁用 OpenVPN 服务
  - 配置: 协议(TCP/UDP), 端口, 加密方式
  - 证书管理: CA/Server/Client 证书生成
  - 客户端配置导出(.ovpn 文件)
  - 客户端管理: 为每个客户端签发独立证书
  - 连接状态查看
实现: openvpn + easy-rsa
```

---

# New Feature 3: 应用流编排重构（n8n 风格）

> ⚠️ **方案验证状态**: 应用识别方案（DNS 缓存 + TLS SNI 提取 + nDPI 兜底）为**待验证方案**。开发完成后用户将重点测试识别准确率和转发性能。见下方 [3.4 应用识别方案](#34-应用识别方案dns--tls-sni--ndpi) 详细设计。

## 背景
现有 `orchestrator.py` 已有设备检测、应用识别、规则编译、流量统计等基础能力。但交互方式是传统表单配置，不符合 n8n 风格的画板操作。需要重构为可视化画布 + 节点拖拽的方式。

## 3.1 现有代码资产

`orchestrator.py` (561行) 已有：
- `DeviceDetector` — 设备检测
- `AppDB` / `AppDetector` — 应用识别
- `RuleCompiler` — 规则编译
- `TrafficStats` — 流量统计
- `FailoverEngine` — 故障切换
- `Rule` / `RuleMatch` / `RuleAction` / `RuleSchedule` — 规则模型
- 预设模板 5 种 (gaming/video/chat/device/ai)
- RESTful API: devices/apps/rules/stats/templates

## 3.2 重构目标

### 前端：n8n 风格画板

```vue
<template>
  <div class="flow-canvas">
    <!-- 左侧工具栏 -->
    <div class="toolbar-panel">
      <div v-for="nodeType in nodeTypes" 
        class="toolbar-item"
        :data-type="nodeType.type"
        draggable="true"
        @dragstart="onDragStart($event, nodeType)">
        <NodeToolbarItem :icon="nodeType.icon" :label="nodeType.label" />
      </div>
    </div>

    <!-- 主画板 -->
    <div class="canvas-area" @drop="onDrop" @dragover.prevent>
      <!-- 自动生成的节点连接线 (SVG) -->
      <svg class="connections-layer">
        <path v-for="conn in connections"
          :d="computePath(conn)"
          stroke="#409EFF" stroke-width="2" fill="none" />
      </svg>

      <!-- 4 种节点 -->
      <NodeDevice v-for="device in devices"
        :data="device"
        :style="{ left: device.x + 'px', top: device.y + 'px' }" />
      <NodeApp v-for="app in apps"
        :data="app"
        :style="{ left: app.x + 'px', top: app.y + 'px' }" />
      <NodeRule v-for="rule in rules"
        :data="rule"
        :style="{ left: rule.x + 'px', top: rule.y + 'px' }" />
      <NodeInterface v-for="iface in interfaces"
        :data="iface"
        :style="{ left: iface.x + 'px', top: iface.y + 'px' }" />
    </div>

    <!-- 右侧配置面板 -->
    <div class="config-panel" v-if="selectedNode">
      <ConfigDevice v-if="selectedNode.type === 'device'" />
      <ConfigApp v-if="selectedNode.type === 'app'" />
      <ConfigRule v-if="selectedNode.type === 'rule'" />
      <ConfigInterface v-if="selectedNode.type === 'interface'" />
    </div>
  </div>
</template>
```

### 节点类型与呈现

| 节点 | 形状 | 颜色 | 图标 | 功能 |
|------|------|------|------|------|
| **设备** | 矩形 | #f9f | 设备类型 icon | 物理/虚拟设备 |
| **应用** | 圆形 | #bbf | 应用 logo | 运行的应用实例 |
| **规则** | 六边形 | #bfb | ⚙️ | 流量处理规则集合 |
| **接口** | 圆形+网口 | #ffb | 🌐 | WAN/VPN/代理出口 |

### 布局规则（树形拓扑）

```
Layer 1: [接口节点]        ← 出口层 (WAN/VPN/Clash)
         ↓
Layer 2: [规则节点]        ← 规则匹配层 (ACL/DPI)
         ↓
Layer 3: [应用节点组]      ← 按设备分组的应用层
         ├── 设备A: [App1] [App2] [App3]
         └── 设备B: [App1] [App4]
         ↓
Layer 4: [设备节点]        ← 硬件设备层
```

### 拓扑自动识别

利用现有 `DeviceDetector` + `AppDetector` 自动构建初始拓扑：
1. 扫描 ARP 表 + DHCP 租约 → 发现设备
2. 使用 DNS 缓存 + TLS SNI 识别各设备的流量应用 → 建立应用节点
3. 根据当前 nftables 规则和用户配置 → 规则节点
4. 检测系统网络接口 + Docker 网络 + VPN 接口 → 接口节点
5. 自动布局 → 树形排列

### 规则引擎增强

```python
class RuleMatch(BaseModel):
    # 现有
    devices: List[str]      # 设备 MAC 列表
    apps: List[str]         # 应用名称列表（由识别引擎解析）
    ports: List[str]        # 端口
    protocols: List[str]    # 协议
    src_ips: List[str]      # 源 IP
    dst_ips: List[str]      # 目标 IP

    # 新增
    exclude_devices: List[str] = []     # 排除设备
    exclude_apps: List[str] = []        # 排除应用
    exclude_ports: List[str] = []       # 排除端口
    time_range: TimeRange = None        # 时间范围
    rate_limit: RateLimit = None        # 速率限制
    dscp: int = 0                       # DSCP 标记
    connstate: str = ""                 # 连接状态 (new/est/related/invalid)
```

### 流量统计增强

每个节点自带流量统计（现有 `TrafficStats` 已支持）：
- 上行/下行速率 (bps)
- 总流量 (bytes)
- 连接数
- 实时显示在节点上

### 高性能转发

使用 nftables 进行数据路径转发（已有 `RuleCompiler` 支持）：
- 规则编译为 nftables set + mark 规则
- connmark 在 conntrack 中记录应用 ID
- fwmark + 策略路由实现出口选择
- 为 10GbE 场景优化

## 3.3 转发执行架构

识别出应用后，规则命中→标记→转发的完整链路：

```
[用户配置规则] → 编译 → [nftables 规则集 + 策略路由表]
                                  ↓
[数据包到达] → nftables prerouting → [conntrack 查找]
                                  ↓
                          已有 connmark？→ Yes → [直接走对应路由表]
                                  ↓ No
                  [DNS 缓存查找 dst_ip → 应用名]
                                  ↓
                        命中？→ Yes → 写入 connmark + nftables set
                                  ↓ No
                  [TLS SNI 提取 (nfqueue 仅首包)]
                                  ↓
                        命中？→ Yes → 写入 connmark + nftables set
                                  ↓ No
                  [nDPI 深度检测 (仅首包)]
                                  ↓
                        识别成功？→ Yes → 写入 connmark + nftables set
                                  ↓ No
                  [未识别 → 走默认规则]
```

nftables 数据路径（硬件 offload 兼容）：

```bash
# 编译后的规则集示例
table inet orchestrator {
    set app_mark_map {
        type ipv4_addr . inet_service . inet_proto
        # 动态填充: 由 DNS 缓存 + SNI 提取持续更新
    }

    chain pre {
        # 已有 connmark → 直接跳过（数据路径，零额外成本）
        ct mark 0x0064 meta mark set 0x0064
        ct mark 0x00C8 meta mark set 0x00C8
        
        # 新建连接查 connmark 或走 DPI
        meta nfproto ipv4 tcp dport 443 add @app_mark_map
    }
}
```

## 3.4 应用识别方案（DNS + TLS SNI + nDPI）— ⚠️ 待验证

> **方案验证标记**: 此方案为设计态，开发完成后需用户重点测试识别准确率和性能影响。
> 若验证不通过，将回退或调整为其他方案（如 eBPF/XDP SNI 提取、用户态全量 DPI 等）。

### 三层识别引擎

```
                  ┌──────────────────────────┐
[数据包到达]      │  Layer 2: DNS 缓存        │ ← 最快，零 CPU
                  │  监听 DNS 应答 → IP→域名   │
                  │  TTL 窗口内精准            │
                  └──────────────────────────┘
                               ↓ 未命中
                  ┌──────────────────────────┐
                  │  Layer 1: TLS SNI 提取     │ ← 最准，~1% CPU (仅首包)
                  │  nfqueue 采样 TLS Client   │
                  │  Hello → 域名 → 应用       │
                  │  覆盖 90%+ HTTPS 流量      │
                  └──────────────────────────┘
                               ↓ 非 TLS
                  ┌──────────────────────────┐
                  │  Layer 3: nDPI 兜底        │ ← 兜底，中CPU
                  │  协议特征分析             │
                  │  覆盖 UDP/QUIC/自定义协议  │
                  └──────────────────────────┘
```

### Layer 2: DNS 被动监听缓存（零 CPU，覆盖 60%）

原理：在路由器上监听 DNS 应答。设备查询域名后，DNS 返回的 IP 在 TTL 内就是该域名的。

```python
class DnsAppCache:
    """
    DNS 应答 → IP → 应用 缓存。
    配合 dnsmasq 的 log-queries 或 pcap 抓取。
    """
    def __init__(self):
        self.ip_to_app = {}        # IP → 应用名
        self.domain_to_app = {      # 预置域名规则
            "*.netflix.com": "Netflix",
            "*.nflxvideo.net": "Netflix",
            "*.youtube.com": "YouTube",
            "*.googlevideo.com": "YouTube",
            "*.weixin.qq.com": "WeChat",
            # ... 数千条，覆盖常见的 200+ 应用
        }
    
    def on_dns_response(self, domain: str, ips: List[str], ttl: int):
        """DNS 应答时由 dnsmasq hook/pcap 回调"""
        app = self._match_domain(domain)
        if app:
            for ip in ips:
                # 写入缓存 + 自动过期 (TTL)
                self.ip_to_app[ip] = {
                    "app": app, 
                    "expire": time.time() + ttl,
                    "domain": domain
                }
                # 同时写入 nftables set（后续包硬件匹配）
                nft_add_app_ip(app, ip)
```

**CDN 场景验证**：CDN 虽然 IP 多，但 DNS 解析是实时的。TTL 通常在 60-300 秒的窗口内，IP→域名映射是可靠的。TTL 过期后自动删除，等下一条 DNS 查询更新。

### Layer 1: TLS SNI 提取（最准，覆盖 90%+ HTTPS 流量）

原理：TLS Client Hello 首包明文包含 SNI。通过 nfqueue 只截取每个流的第一包做 SNI 解析，识别后立即 release。

```python
from scapy.all import *
from scapy.layers.inet import IP, TCP
from nfqueue import NFQueue

class SniExtractor:
    """
    nfqueue 采样 TLS SNI。
    只处理每条流的第一包 (TCP SYN + Client Hello)
    """
    
    def process_packet(self, packet):
        """收到 nfqueue 回调：解析 SNI"""
        if not self._is_tls_client_hello(packet):
            return packet  # 放行，不处理
        
        sni = self._extract_sni(packet)
        if not sni:
            return packet
        
        app = self._resolve_app(sni)
        if app:
            # 记录到 conntrack
            self._mark_connection(packet, app)
        
        return packet  # 放行
    
    def _extract_sni(self, packet):
        """从 TLS Client Hello 提取 SNI"""
        payload = bytes(packet[TCP].payload)
        if len(payload) < 50 or payload[0] != 0x16:
            return None  # 不是 TLS Handshake
        # 解析 TLS 记录 →
        # 跳过记录头(5) + Handshake(4) + 固定字段(4+2+32+1+2+2+2+1)
        # 遍历 Extensions → type=0x0000 (Server Name)
        return self._manual_sni_search(payload)
```

**性能保障**：
- 采样率可配置：默认每 100 条新连接采样 1 条
- nfqueue 只拦截首包，识别后立即放行
- 识别结果写入 connmark，后续包在 nftables 数据路径处理

### Layer 3: nDPI 兜底（非 TLS 流量）

对于非 HTTPS 流量（UDP 游戏、QUIC、自定义协议）做 nDPI 分析。

```python
class NdpiDetector:
    """
    nDPI 深度包检测，仅用于非 TLS 流量。
    """
    def detect(self, src_ip, dst_ip, sport, dport, protocol):
        """对指定流做 nDPI 分析"""
        # 只对非 443 端口、非 TCP 的流量做
        if protocol == "tcp" and dport == 443:
            return None  # TLS 流量由 SNI 处理
        
        # 调用 nDPI 库
        result = ndpi_detection_process(
            src_ip, sport, dst_ip, dport, protocol
        )
        app_name = result.protocol.app_name
        if app_name:
            return app_name
        return "未知"
```

### 预置应用识别数据库

开箱即用的域名→应用映射：

| 分类 | 应用 | 识别特征 |
|------|------|---------|
| 流媒体 | Netflix | `*.netflix.com`, `*.nflxvideo.net` |
| | YouTube | `*.youtube.com`, `*.googlevideo.com` |
| | Bilibili | `*.bilibili.com`, `*.hdslb.com` |
| | TikTok | `*.tiktokv.com` |
| 社交 | WeChat | `*.weixin.qq.com`, `*.wechat.com` |
| | Telegram | `*.telegram.org` |
| | Discord | `*.discord.com` |
| 游戏 | Steam | `*.steampowered.com`, `*.steamcontent.com` |
| | Epic | `*.epicgames.com` |
| 办公 | Teams | `*.teams.microsoft.com` |
| | Zoom | `*.zoom.us` |

### 用户自定义应用识别

画板上拖入"应用"节点时，用户可配置识别规则：

```yaml
name: "我的私有云"
match:
  domain: ["*.my-private-cloud.com"]
  sni: ["*.myapp.internal"]
  port: [tcp/8443, tcp/9000]
  exclude_domain: ["cdn.my-private-cloud.com"]
```

### 写入 nftables 数据路径

识别结果最终写入 connmark，后续包零成本：

```python
# 识别到 Netflix → 写入 conntrack mark 0x1001
os.system(f"conntrack -U -p tcp -d {dst_ip} --mark 1001")

# nftables 根据 connmark 转发
# ct mark 1001 → table 100 (Clash)
# ct mark 2001 → table 200 (Direct)
```

### 方案验证点

开发完成后用户将重点测试：

| 验证项 | 预期 | 风险 |
|--------|------|------|
| DNS 缓存对 CDN IP 的识别率 | ≥90% | TTL 过期窗口内部分 CDN IP 可能漏识别 |
| TLS SNI 提取对 HTTPS 流量的覆盖率 | ≥95% | ECH (Encrypted Client Hello) 将隐藏 SNI |
| nDPI 对非 TLS 流量的识别率 | ≥80% | QUIC/HTTP3 的 nDPI 识别还在完善 |
| nfqueue 采样对 10GbE 的性能影响 | <5% CPU | 采样率过高可能影响转发性能 |
| connmark → nftables 的端到端延迟 | <10ms | 用户态 set 写入到内核态生效的延迟 |

> 若 TLS ECH 大规模部署导致 SNI 不可读，将升级到 eBPF/XDP 方案或与 DNS 缓存深度绑定。

---

# New Feature 4: 语音助手集成

## 背景
支持 Google Assistant、Amazon Alexa、Apple Siri、Home Assistant 语音查询路由器状态。

## 4.1 架构设计

```
用户语音
  ├──→ Google Assistant → Webhook → UbuntuRouter API → 状态响应
  ├──→ Amazon Alexa    → Skill   → UbuntuRouter API → 状态响应
  ├──→ Apple Siri      → Shortcuts → UbuntuRouter API → 状态响应
  └──→ Home Assistant  → REST API → UbuntuRouter API → 状态响应
```

## 4.2 统一状态查询 API

所有语音助手调用一个统一的状态查询 API：

```python
GET /api/v1/voice/status          # 获取路由器状态摘要
GET /api/v1/voice/status/{module} # 获取特定模块状态

# 返回格式 (语音友好)
{
  "summary": "路由器运行正常。CPU使用率23%，内存使用率45%，已运行5天12小时，连接设备8台，当前上行2.3Mbps，下行15.6Mbps",
  "modules": {
    "system": {"cpu": 23, "memory": 45, "uptime": "5d12h"},
    "network": {"wan_ip": "192.168.1.1", "devices": 8},
    "traffic": {"upload": "2.3Mbps", "download": "15.6Mbps"},
    "services": {"docker": "running", "vpn": "running", "samba": "stopped"}
  }
}
```

## 4.3 Google Assistant 集成

- 创建 Actions on Google 项目
- 实现 Fulfillment Webhook: `POST /api/v1/voice/google`
- 意图 (Intents): `get_router_status`, `get_traffic`, `get_device_count`
- 使用 Dialogflow / Actions SDK

## 4.4 Amazon Alexa 集成

- 创建 Alexa Skill
- 实现 Skill Endpoint: `POST /api/v1/voice/alexa`
- 意图: `GetRouterStatus`, `GetTraffic`, `GetDevices`
- 使用 Alexa Skills Kit (ASK) SDK

## 4.5 Apple Siri 集成

- 提供 Shortcuts 支持
- Siri Shortcuts 通过 URL Scheme 调用
- 提供公开的 RESTful API 供 Shortcuts 调用

## 4.6 Home Assistant 集成

- 提供 Home Assistant Add-on / 配置模板
- 通过 REST API 对接 Home Assistant 的 sensor 实体
- 支持的传感器: CPU, 内存, 磁盘, 流量, 设备数, 服务状态

---

# Sprint 1: iStoreOS P1 补齐

## 1.1 防火墙规则增强 (3d)

| 项目 | 详情 |
|------|------|
| ICMP 协议支持 | rules.js 增加 ICMP/ICMPv6 协议选项面板(70+ type) |
| ipset 集成 | 新增 ipset 管理 + 规则中引用 ipset |
| rate limit 匹配 | 规则中增加速率限制 (limit/burst) |
| 时间限制规则 | 星期/日期/时间范围条件 (借鉴 iStoreOS 实现) |
| conntrack state | 连接状态匹配 (new/est/related/invalid) |
| MAC 地址匹配 | 规则中增加源 MAC 过滤 |
| NAT Loopback | 端口转发增加 NAT 回环选项 |
| Zone 增强 | 增加 covered networks 选择, log, family, mtu |

## 1.2 实时图表 (2d)

| 项目 | 详情 |
|------|------|
| WebSocket 推送 | 新增 WS 端点推送实时流量数据 |
| ECharts 趋势图 | 实时流量曲线 (类似 iStoreOS Realtime Graphs) |
| CPU/内存/连接趋势 | 多维度实时趋势 |

## 1.3 DHCP 池编辑 (0.5d)

| 项目 | 详情 |
|------|------|
| DHCP 池 CRUD | 新增 POST/PUT/DELETE /api/v1/dhcp/pool |
| 前端表单 | DHCP 起始/结束IP、子网掩码、租约时间 |

---

# Sprint 2: iStoreOS P2 补齐

## 2.1 Turbo ACC (硬件加速/BBR) — 1.5d

| 项目 | 详情 |
|------|------|
| BBR 拥塞控制 | 启用/禁用 BBR + BBRv3 |
| 硬件 offload | Flow offloading (software/hardware) |
| 前端页面 | 替换占位符为完整配置页 |

## 2.2 SQM QoS — 2d

| 项目 | 详情 |
|------|------|
| 队列管理 | fq_codel / cake / htb |
| 带宽设置 | 上行/下行带宽限制 |
| 前端页面 | 替换占位符 |

## 2.3 桥接/Bond 管理 — 1.5d

| 项目 | 详情 |
|------|------|
| Linux Bridge | 创建/删除/端口管理 |
| Bonding | 802.3ad (LACP), balance-rr, active-backup |
| 前端页面 | 桥接列表 + 创建/编辑 |

## 2.4 DDNS 更多提供商 — 1d

| 项目 | 详情 |
|------|------|
| No-IP | 新增 provider |
| HE.NET | 新增 provider |
| Oray/3322 | 新增 provider |

## 2.5 UPnP 增强 — 1d

| 项目 | 详情 |
|------|------|
| 协议选择 | TCP/UDP/Both |
| NAT-PMP | 支持 |
| 配置选项 | 接口选择, ACL, 端口范围 |
| 活跃转发 | upnp -l 实时查询 |

---

# Sprint 3: iStoreOS P3 补齐

## 3.1 无线高级参数 — 1d

| 项目 | 详情 |
|------|------|
| 发射功率 | txpower 设置 |
| 信道宽度 | 20/40/80/160MHz |
| 国家码 | country code 设置 |
| MAC 过滤 | 白名单/黑名单 |

## 3.2 接口高级参数 — 1d

| 项目 | 详情 |
|------|------|
| metric | 路由跃点数 |
| dhcp-identifier | MAC/duid |
| accept-ra | IPv6 RA 接受 |

## 3.3 FTP/LED/SNMP — 2d

| 项目 | 详情 |
|------|------|
| FTP 服务 | vsftpd 管理 |
| LED 配置 | 系统指示灯控制 |
| SNMP | snmpd 配置 |

---

## 修订历史

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-04-28 | v1.0 | 初版，合并 iStoreOS gap + 1Panel AppStore + 4项新需求 |
