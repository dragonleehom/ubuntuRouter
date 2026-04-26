# DHCP/DNS 管理模块详细设计 — DHCP/DNS Manager

> 版本: v1.0 | 日期: 2026-04-25 | 状态: 初稿
> 对应 HLD 模块: 3.5 DHCP/DNS Manager
> 依赖模块: Configuration Engine, Network Manager
> 后端技术: dnsmasq (默认) + Unbound (DNS 缓存) + AdGuard Home (广告过滤，可选)

---

## 1. 模块定位

DHCP/DNS Manager 负责局域网 IP 地址分配、DNS 解析缓存/转发、广告过滤的统一管理。支持两种部署模式：**轻量集成模式**（dnsmasq 同时提供 DHCP+DNS）和 **高性能分离模式**（Unbound 做 DNS 缓存 + 独立 DHCP 服务）。

---

## 2. 数据结构

```python
# ubunturouter/dhcpdns/models.py

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from enum import Enum


class DHCPServerType(str, Enum):
    DNSMASQ = "dnsmasq"           # 默认，轻量
    KEA = "kea"                   # 高性能，可选


class DNSMode(str, Enum):
    FORWARD = "forward"           # 转发模式（默认），dnsmasq 转发到上游
    RECURSIVE = "recursive"       # 递归模式，Unbound 做递归解析
    ADGUARD = "adguard"           # AdGuard Home 接管 DNS (需 Docker)


class DHCPLease(BaseModel):
    """DHCP 租约条目"""
    mac: str
    ip: str
    hostname: Optional[str] = None
    expires: str                   # 到期时间 ISO 格式
    online: bool = False           # 当前在线
    interface: Optional[str] = None


class StaticLease(BaseModel):
    """静态租约绑定"""
    mac: str = Field(..., pattern=r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$')
    ip: str
    hostname: Optional[str] = None
    description: Optional[str] = None
    enabled: bool = True


class DHCPRange(BaseModel):
    """DHCP 地址池"""
    start: str
    end: str
    netmask: str = "255.255.255.0"
    lease_time: int = 86400         # 秒 (24小时)


class DHCPPool(BaseModel):
    """DHCP 池配置（对应一个接口）"""
    interface: str
    enabled: bool = True
    range: DHCPRange
    gateway: str
    dns: List[str] = ["192.168.21.1"]
    domain: Optional[str] = "lan"
    static_leases: List[StaticLease] = []
    options: Dict[str, str] = {}    # 自定义 DHCP 选项
    pxe: Optional['PXEConfig'] = None


class PXEConfig(BaseModel):
    """PXE 网络启动配置"""
    enabled: bool = False
    server_ip: str
    boot_file: str                  # "undionly.kpxe"
    next_server: str                # TFTP 服务器
    menu_file: Optional[str] = None # 启动菜单


class DNSRewrite(BaseModel):
    """DNS 重写/劫持"""
    domain: str                     # "*.example.com"
    ip: str                         # "192.168.21.50"
    enabled: bool = True


class DNSForwarder(BaseModel):
    """DNS 上游转发"""
    domain: Optional[str] = None    # None = 默认上游
    servers: List[str]              # ["223.5.5.5", "119.29.29.29"]
    port: int = 53
    doh: bool = False               # 是否使用 DNS over HTTPS


class AdGuardConfig(BaseModel):
    """AdGuard Home 集成"""
    enabled: bool = False
    container_name: str = "adguardhome"
    port: int = 5353                # AdGuard 监听端口
    web_port: int = 3000            # AdGuard Web 管理端口
    upstream: List[str] = ["https://dns.alidns.com/dns-query"]
    blocklists: List[str] = [
        "https://easylist-downloads.adblockplus.org/easylistchina.txt"
    ]


class DHCPDNSConfig(BaseModel):
    """DHCP/DNS 完整配置"""
    server_type: DHCPServerType = DHCPServerType.DNSMASQ
    dns_mode: DNSMode = DNSMode.FORWARD
    pools: List[DHCPPool] = []
    upstream: List[str] = [
        "223.5.5.5",
        "119.29.29.29",
        "8.8.8.8"
    ]
    doh_upstream: List[str] = []
    rewrites: List[DNSRewrite] = []
    forwarders: List[DNSForwarder] = []
    adguard: AdGuardConfig = AdGuardConfig()
    # 高级选项
    dnssec: bool = True
    cache_size: int = 10000
    bind_interfaces: bool = True    # 仅监听 LAN 接口
    rate_limit: int = 1000          # DNS 查询限速/秒


# ─── 运行时状态 ──────────────────────────────────────

class DHCPStats(BaseModel):
    """DHCP 统计"""
    total_leases: int = 0
    active_leases: int = 0
    static_leases: int = 0
    pools: List[Dict] = []


class DNSStats(BaseModel):
    """DNS 统计"""
    queries_total: int = 0
    cached_hits: int = 0
    blocked: int = 0               # 广告拦截数
    upstream_queries: int = 0
    top_domains: List[Dict[str, int]] = []
    top_clients: List[Dict[str, int]] = []
```

---

## 3. 核心接口

```python
# ubunturouter/dhcpdns/manager.py


class DHCPDNSManager:
    """DHCP/DNS 管理模块"""

    # ─── DHCP 操作 ─────────────────────────────────

    def list_leases(self, pool_interface: Optional[str] = None) -> List[DHCPLease]:
        """
        查看 DHCP 租约
        
        来源: /var/lib/misc/dnsmasq.leases
        格式: 1712345678 aa:bb:cc:dd:ee:ff 192.168.21.100 iphone *
        解析后按在线/离线分组
        """

    def add_static_lease(self, lease: StaticLease) -> None:
        """添加静态租约绑定"""

    def remove_static_lease(self, mac: str) -> None:
        """删除静态租约绑定"""

    def delete_lease(self, mac: str) -> None:
        """
        强制释放 DHCP 租约
        实现: dnsmasq 不直接支持删除，通过修改租约文件 + reload 实现
        """

    # ─── DNS 操作 ──────────────────────────────────

    def flush_dns_cache(self) -> None:
        """
        清空 DNS 缓存
        dnsmasq: kill -SIGHUP $(pidof dnsmasq)
        Unbound: unbound-control flush-all
        """

    def get_dns_stats(self) -> DNSStats:
        """
        获取 DNS 统计
        dnsmasq: 解析日志文件
        AdGuard: 通过 API 查询
        """

    def get_blocked_domains(self) -> List[str]:
        """获取当前拦截的域名列表"""

    # ─── 配置 Apply ─────────────────────────────────

    def apply(self, config: UbunturouterConfig) -> None:
        """
        应用 DHCP/DNS 配置
        
        dnsmasq 模式:
          → DnsmasqGenerator → /etc/dnsmasq.d/ubunturouter.conf
        
        Unbound 模式:
          → UnboundGenerator → /etc/unbound/unbound.conf.d/
        
        AdGuard 模式:
          → 检查 Docker 容器运行状态 → 更新配置
        """
    
    # ─── 设备识别联动（供 Traffic Orchestrator 使用）─

    def get_online_devices(self) -> List[DHCPLease]:
        """获取当前在线设备列表（用于流量编排的设备识别）"""
```

---

## 4. dnsmasq 配置生成

```python
# ubunturouter/engine/generators/dnsmasq.py

class DnsmasqGenerator(ConfigGenerator):

    def generate(self, config: UbunturouterConfig) -> Dict[str, str]:
        """
        生成 /etc/dnsmasq.d/ubunturouter.conf
        
        dnsmasq 配置结构：
        
        # 基础设置
        domain-needed
        bogus-priv
        no-resolv
        bind-interfaces
        
        # DHCP
        dhcp-authoritative
        dhcp-leasefile=/var/lib/misc/dnsmasq.leases
        
        # LAN 接口 DHCP 池
        interface=br-lan
        dhcp-range=br-lan,192.168.21.50,192.168.21.200,255.255.255.0,24h
        
        # 静态租约
        dhcp-host=aa:bb:cc:11:22:33,192.168.21.100,tv
        dhcp-host=dd:ee:ff:44:55:66,192.168.21.101,iphone
        
        # 网关/DNS 选项
        dhcp-option=br-lan,3,192.168.21.1
        dhcp-option=br-lan,6,192.168.21.1
        
        # 上游 DNS
        server=223.5.5.5
        server=119.29.29.29
        server=8.8.8.8
        
        # DNS 重写 (劫持)
        address=/example.com/192.168.21.50
        
        # 域名上游分流
        server=/google.com/8.8.8.8
        server=/baidu.com/223.5.5.5
        
        # 广告过滤（如果启用）
        # addn-hosts=/etc/ubunturouter/blocked.hosts
        
        # DNS 缓存
        cache-size=10000
        
        # 限速
        dns-forward-max=1000
        """
```

### dnsmasq 配置示例（完整）

```
# /etc/dnsmasq.d/ubunturouter.conf
# 由 UbuntuRouter DHCP/DNS Manager 生成

# 基础
domain-needed
bogus-priv
no-resolv
bind-interfaces
domain=lan
local=/lan/

# 日志
log-dhcp
log-queries
log-facility=/var/log/dnsmasq.log

# 缓存
cache-size=10000
dns-forward-max=1000

# DHCP 授权模式
dhcp-authoritative
dhcp-leasefile=/var/lib/misc/dnsmasq.leases

# === 接口: br-lan (192.168.21.1/24) ===
interface=br-lan
dhcp-range=br-lan,192.168.21.50,192.168.21.200,255.255.255.0,86400s
dhcp-option=br-lan,3,192.168.21.1         # 网关
dhcp-option=br-lan,6,192.168.21.1          # DNS
dhcp-option=br-lan,42,192.168.21.1          # NTP

# 静态租约
dhcp-host=aa:bb:cc:11:22:33,192.168.21.100,tv
dhcp-host=dd:ee:ff:44:55:66,192.168.21.101,iphone
dhcp-host=11:22:33:44:55:66,192.168.21.102,nas

# 上游 DNS
server=223.5.5.5
server=119.29.29.29
server=8.8.8.8
server=1.1.1.1

# 分流 DNS
server=/google.com/8.8.8.8
server=/youtube.com/8.8.8.8
server=/baidu.com/223.5.5.5

# DNS 重写 (本地域名)
address=/nas.lan/192.168.21.50
address=/router.lan/192.168.21.1
address=/proxy.lan/192.168.21.60

# 广告拦截 hosts
# 如果启用了流量编排的 DNS 拦截
```

---

## 5. Unbound DNS 缓存配置

当 `dns_mode = recursive` 时，使用 Unbound 替代 dnsmasq 做 DNS 解析，dnsmasq 只做 DHCP。

### 5.1 Unbound 配置生成

```python
# ubunturouter/engine/generators/unbound.py

class UnboundGenerator(ConfigGenerator):

    def generate(self, config: UbunturouterConfig) -> Dict[str, str]:
        """
        生成 /etc/unbound/unbound.conf.d/ubunturouter.conf
        
        关键配置：
        - 监听 LAN 接口 (192.168.21.1)
        - 仅允许 LAN 网段访问
        - DNSSEC 验证
        - 预取 + 缓存优化
        - 根提示文件
        """
```

### 5.2 Unbound 配置示例

```
# /etc/unbound/unbound.conf.d/ubunturouter.conf

server:
    # 接口
    interface: 192.168.21.1
    interface: 127.0.0.1
    port: 53
    
    # 访问控制
    access-control: 127.0.0.0/8 allow
    access-control: 192.168.21.0/24 allow
    access-control: 0.0.0.0/0 refuse
    
    # 递归
    do-ip4: yes
    do-ip6: yes
    prefer-ip6: no
    
    # DNSSEC
    auto-trust-anchor-file: /var/lib/unbound/root.key
    val-clean-additional: yes
    
    # 缓存
    cache-min-ttl: 300
    cache-max-ttl: 86400
    prefetch: yes
    prefetch-key: yes
    msg-cache-size: 100m
    rrset-cache-size: 200m
    
    # 性能
    num-threads: 4
    so-rcvbuf: 1m
    so-sndbuf: 1m
    
    # 隐私
    hide-identity: yes
    hide-version: yes
    
    # 日志
    verbosity: 1
    use-syslog: yes

# 上游转发
forward-zone:
    name: "."
    forward-addr: 223.5.5.5
    forward-addr: 119.29.29.29
    forward-addr: 1.1.1.1@853#cloudflare-dns.com  # DNS over TLS
```

### 5.3 两种模式的 DNS 查询路径对比

```
dnsmasq 模式 (简单):
  Client → dnsmasq:53 → 缓存匹配 → 上游 DNS → 返回

分离模式 (高性能):
  Client → dnsmasq:53(DHCP+DNS) → 仅转发到 Unbound:5353
                                  → 缓存 → 递归解析 → 返回
  
  uClient → dnsmasq:53(DHCP only) → /etc/resolv.conf → Unbound:53
  nUnbound 直接做递归解析，dnsmasq 退出 DNS 功能
  
广告过滤集成:
  Client → Unbound:53 → AdGuard Home:5353 → 上游 DNS
           (缓存)         (规则过滤)
```

---

## 6. 广告过滤集成

### 6.1 集成方式

```
模式A: dnsmasq + hosts 文件（轻量，无额外容器）
  - dnsmasq 加载 /etc/ubunturouter/blocked.hosts
  - 定期从订阅列表更新
  - 优点：无额外依赖
  - 缺点：功能有限

模式B: AdGuard Home 容器（推荐，功能完整）
  - Docker 运行 adguard/adguardhome
  - AdGuard 监听 5353（DNS）+ 3000（Web）
  - dnsmasq/Unbound 中的上游指向 localhost:5353
  - Web GUI 中嵌入 AdGuard 管理页面
  - 定期更新拦截列表
```

### 6.2 AdGuard 容器管理

```python
class AdGuardIntegration:
    """AdGuard Home 集成"""

    def ensure_container(self):
        """确保 AdGuard 容器运行"""
        docker compose up -d -f /var/lib/ubunturouter/docker/adguard/docker-compose.yml

    def update_config(self, config: AdGuardConfig):
        """
        更新 AdGuard 配置
        通过 AdGuard API (port 3000) 更新上游 DNS、黑白名单
        """

    def get_stats(self):
        """
        获取过滤统计
        通过 AdGuard API: GET /control/stats
        """
```

**AdGuard Docker Compose**：

```yaml
# /var/lib/ubunturouter/docker/adguard/docker-compose.yml
version: '3'
services:
  adguardhome:
    image: adguard/adguardhome:latest
    container_name: adguardhome
    restart: unless-stopped
    ports:
      - "5353:53/tcp"
      - "5353:53/udp"
      - "3000:3000/tcp"     # Web 管理
    volumes:
      - ./work:/opt/adguardhome/work
      - ./conf:/opt/adguardhome/conf
    cap_add:
      - NET_BIND_SERVICE
    network_mode: "host"     # 使用 host 模式以便获取真实客户端 IP
```

DNS 查询路径（AdGuard 模式）：
```
Client DNS Query (53)
    │
    ▼
dnsmasq (53) 或 Unbound (53)
    │ 上游指向 localhost:5353
    ▼
AdGuard Home (5353)
    │ 过滤 + 缓存
    ▼
上游 DNS (223.5.5.5 或 DoH)
```

---

## 7. 域名分流 DNS

支持不同域名走不同上游 DNS，解决国内/国外 DNS 污染问题：

```yaml
# config.yaml 中的 DNS 分流配置示例
dns:
  upstream:
    - "223.5.5.5"              # 默认上游
    - "119.29.29.29"
  
  forwarders:                   # 域名分流
    - domain: "*.google.com"
      servers: ["8.8.8.8", "1.1.1.1"]
      doh: true
    - domain: "*.youtube.com"
      servers: ["8.8.8.8"]
    - domain: "*.twitter.com"
      servers: ["8.8.8.8"]
    - domain: "*.github.com"
      servers: ["8.8.8.8", "1.1.1.1"]
    - domain: "*.baidu.com"
      servers: ["223.5.5.5"]
    - domain: "*.qq.com"
      servers: ["223.5.5.5"]
```

dnsmasq 生成的配置：
```
# 国内域名走国内 DNS
server=/baidu.com/223.5.5.5
server=/qq.com/223.5.5.5
server=/taobao.com/223.5.5.5

# 国外域名走国外 DNS
server=/google.com/8.8.8.8
server=/youtube.com/8.8.8.8
server=/github.com/8.8.8.8
server=/twitter.com/1.1.1.1
```

---

## 8. DNS 与流量编排的联动

```
DNS 查询是流量编排中应用识别的最重要数据源：

dnsmasq/Unbound log → App Detector 监听
    │
    ▼
提取: 谁(device_mac) 查询了什么域名 (domain)
    │
    ▼
匹配应用特征库:
  nflxvideo.net → Netflix
  douyin.com → 抖音
  steamcontent.com → Steam
    │
    ▼
更新 设备→应用 映射表
    │
    ▼
WebSocket 推送 → Dashboard 实时更新
    │
    ▼
Traffic Orchestrator 编排规则匹配:
  电视 + Netflix → ts-exit-us
  iPhone + 抖音 → direct
```

---

## 9. DHCP 与设备识别的联动

```
DHCP 是设备识别的最主要数据源：

dnsmasq dhcp-lease-file 变化
    │
    ▼
Device Detector 监听 lease 文件 (inotify)
    │
    ▼
新设备上线:
  MAC: aa:bb:cc:11:22:33
  IP: 192.168.21.100
  Hostname: xiaomi-tv
    │
    ▼
MAC OUI 匹配: aa:bb:cc → Xiaomi Communications
mDNS 查询: _airplay._tcp, _googlecast._tcp → "XiaoMi TV Stick"
    │
    ▼
设备记录:
  name: "XiaoMi TV Stick" (或用户手动命名 "客厅电视")
  mac: aa:bb:cc:11:22:33
  ip: 192.168.21.100
  vendor: "Xiaomi"
  type: "tv" (通过 OUI + mDNS 推断)
    │
    ▼
Traffic Orchestrator 设备列表中可见
```

---

## 10. 测试用例

| 测试场景 | 预期 |
|----------|------|
| 客户端请求 DHCP | 分配到 192.168.21.50-200 范围内的 IP |
| 静态租约绑定 MAC aa:bb:cc:11:22:33 → 192.168.21.100 | 该设备始终获取 192.168.21.100 |
| 客户端 DNS 查询 example.com | 返回正确 IP |
| 广告过滤: 访问含广告域名的页面 | DNS 返回 0.0.0.0 或 NXDOMAIN |
| 域名分流: dig google.com | 走 8.8.8.8 |
| 域名分流: dig baidu.com | 走 223.5.5.5 |
| DNS 缓存: 重复查询同域名 | 第二次缓存命中，延迟极低 |
| DNSSEC: dig +dnssec sigfail.verteiltesysteme.net | 返回 SERVFAIL |
| DHCP 租约过期 | 设备自动获取新租约 |
| 设备识别: iPhone 连接 WiFi | DHCP lease + mDNS → 识别为 "iPhone" |
| DNS 重写: nas.lan → 192.168.21.50 | ping nas.lan 返回 192.168.21.50 |
