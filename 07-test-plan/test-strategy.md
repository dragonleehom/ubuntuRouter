# 测试策略

> 版本: v1.0 | 日期: 2026-04-25 | 状态: 初稿
> 测试环境: 192.168.100.194 (Ubuntu 26.04, 单网口 ens3)

---

## 1. 测试层次

```
Layer 1: 单元测试
  ├── Python: pytest + pytest-asyncio
  ├── 覆盖: 配置引擎 Pydantic 模型校验、Generator 输出格式
  ├── 速度: 毫秒级，CI 每次提交运行
  
Layer 2: 集成测试
  ├── Shell: bash 脚本，调用实际系统命令
  ├── 覆盖: netplan apply / nft -f / dnsmasq reload
  ├── 前置: 在测试 VM 上运行，不影响生产
  
Layer 3: 端到端测试 (E2E)
  ├── 工具: Playwright (浏览器自动化)
  ├── 覆盖: Web GUI 登录 → 配置 → 验证 → 回退
  ├── 前置: API Server + Web GUI 已运行
  
Layer 4: 硬件验收测试
  ├── 场景: 多网口 / 单网口 / 万兆 / ARM
  ├── 覆盖: 安装流程、首次初始化、性能基准
  ├── 频率: 每个版本发布前
```

---

## 2. 测试环境

### 2.1 测试 VM（当前已有）

```
IP:       192.168.100.194
系统:     Ubuntu 26.04 LTS x86_64
CPU:      4 核
RAM:      3.3 GB
网口:     1x ens3 (virtio) — 单网口场景
用途:     Layer 1-3 测试
```

### 2.2 推荐硬件测试矩阵

| 测试平台 | 网口数 | 测试重点 |
|----------|--------|----------|
| x86 VM (当前) | 1 | 单网口 WANLAN、API、Web GUI |
| x86 物理机 (N100) | 4 | 多网口、Multi-WAN、万兆 NAT |
| ARM (RK3588) | 2 | ARM 兼容性、eMMC 写入 |
| Proxmox VM | 2+ | 虚拟机部署、VFIO 直通 |

---

## 3. 单元测试

```python
# tests/test_config_models.py
# pytest 运行

class TestConfigModels:
    """配置数据模型校验"""
    
    def test_valid_config(self):
        """合法配置通过校验"""
    
    def test_invalid_ip(self):
        """非法 IP 格式校验失败"""
    
    def test_port_out_of_range(self):
        """端口号 1-65535 校验"""
    
    def test_mac_format(self):
        """MAC 地址格式校验"""
    
    def test_vlan_id_range(self):
        """VLAN ID 1-4094 校验"""
    
    def test_bridge_needs_ports(self):
        """Bridge 至少需要一个端口"""
    
    def test_bond_needs_two_slaves(self):
        """Bond 至少需要两个 slave"""
    
    def test_wanlan_needs_uplink(self):
        """WANLAN 必须有 wan_uplink 配置"""
    
    def test_extra_fields_forbidden(self):
        """不允许额外字段"""


class TestConfigEngine:
    """配置引擎逻辑"""
    
    def test_load_valid_yaml(self):
        """加载合法 YAML"""
    
    def test_load_invalid_yaml(self):
        """加载非法 YAML 报错"""
    
    def test_validate_passes(self):
        """校验通过"""
    
    def test_validate_detects_conflict(self):
        """IP 冲突检测"""
    
    def test_diff_no_changes(self):
        """无变更时 diff empty"""
    
    def test_diff_detects_changes(self):
        """有变更时 diff 正确"""
    
    def test_snapshot_create_and_restore(self):
        """快照创建和恢复"""


class TestGenerators:
    """配置生成器"""
    
    def test_netplan_generator_wanlan(self):
        """单网口生成正确"""
    
    def test_netplan_generator_dual(self):
        """双网口生成正确"""
    
    def test_netplan_generator_vlan(self):
        """VLAN 配置生成正确"""
    
    def test_netplan_generator_bond(self):
        """Bond 配置生成正确"""
    
    def test_nftables_generator_zone(self):
        """Zone 规则生成正确"""
    
    def test_nftables_generator_port_forward(self):
        """端口转发规则正确"""
    
    def test_nftables_generator_nat(self):
        """NAT 规则正确"""
    
    def test_dnsmasq_generator_dhcp(self):
        """DHCP 配置正确"""
    
    def test_dnsmasq_generator_static_lease(self):
        """静态租约配置正确"""
    
    def test_wireguard_generator(self):
        """WireGuard 配置正确"""
```

---

## 4. 集成测试用例

### 4.1 安装与初始化

**TC-INSTALL-001: 首次启动自动初始化（单网口）**
```
前置:
  1. 删除 /etc/ubunturouter/config.yaml
  2. 创建 /etc/ubunturouter/.fresh-install
  3. 系统只有一个 ens3 网口

步骤:
  1. 重启 ubunturouter-init 服务
  2. 检查是否生成 /etc/ubunturouter/config.yaml
  3. 检查 config.yaml 中 role=wanlan
  4. 检查 LAN IP = 192.168.21.1/24
  5. 检查 DHCP 池 = 192.168.21.50-200
  6. 检查 dnsmasq 是否运行
  7. 检查 API Server 是否运行
  8. curl http://192.168.21.1:8080/health → 200

预期: 初始化完成，Web GUI 可达
```

**TC-INSTALL-002: 已有系统 apt 安装**
```
前置:
  1. 干净 Ubuntu 26.04 系统
  2. 至少 2 个网口（VM 中创建 veth 或接 virtio 第二个网口）

步骤:
  1. 添加 apt 源
  2. apt install ubunturouter-core ubunturouter-web
  3. urctl init --auto
  4. 检查配置是否正确生成

预期: 安装成功，初始化完成
```

### 4.2 网络接口

**TC-NET-001: 网口检测**
```
步骤:
  1. curl http://localhost:8080/api/v1/interfaces/detect
  
预期:
  - 返回物理网口列表
  - 每个网口带 speed/driver/link/mac
  - 不含 lo, docker* 等虚拟接口
```

**TC-NET-002: 修改 LAN IP**
```
前置: 当前 LAN = 192.168.21.1/24

步骤:
  1. API 调用修改 LAN IP → 10.0.0.1/24
  2. Apply 配置
  3. ping 10.0.0.1 → 通
  4. 再次改回 192.168.21.1/24
  5. Apply
  6. 确认恢复

预期: LAN IP 修改生效，API 端点在新的 IP 上可达
```

**TC-NET-003: VLAN 创建**
```
前置: LAN 口 br-lan 已存在

步骤:
  1. API 创建 VLAN: id=10, ip=192.168.10.1/24, zone=guest
  2. Apply
  3. ip link show vlan10-guest → 存在
  4. ping 192.168.10.1 → 通

预期: VLAN 接口创建成功
```

**TC-NET-004: WANLAN 单网口模式（当前测试环境）**
```
前置: 仅 1 个网口 ens3

步骤:
  1. 确保 config.yaml 中 role=wanlan
  2. netplan apply
  3. ip addr show ens3
     → 应看到 192.168.21.1/24 (静态 LAN) 和 DHCP 获取的 IP
  4. 检查 nftables NAT 规则存在
  5. 客户端 DHCP 获取 192.168.21.x 地址

预期: 单网口同时提供 LAN 和 WAN 功能
```

**TC-NET-005: Web GUI 接口管理页面**
```
步骤:
  1. 浏览器登录 http://192.168.21.1
  2. 进入"接口管理"页面
  3. 验证:
     - 显示所有网口及其角色 (WAN/LAN/WANLAN)
     - 显示速率、MAC、link 状态
     - 可修改 LAN IP
     - 修改后 Apply 按钮可用
     - VLAN 列表可新增
  4. 验证 UI 与配置的一致性:
     - 页面显示的内容 == config.yaml 的内容
     - 修改后 config.yaml 同步更新

预期: Web GUI 操作与系统配置一致
```

### 4.3 防火墙

**TC-FW-001: 默认策略验证**
```
前置: 防火墙默认 input=drop, forward=drop

步骤:
  1. 从外网 ping LAN IP → 不通
  2. 从 LAN ping 外网 → 通 (NAT)
  3. 从 LAN 访问 192.168.21.1:443 → 通

预期: 默认策略生效
```

**TC-FW-002: 端口转发**
```
前置: 一台内网设备 192.168.21.50 运行 HTTP 服务

步骤:
  1. 添加端口转发: WAN:8080 → 192.168.21.50:80
  2. Apply
  3. curl http://WAN_IP:8080 → 返回 192.168.21.50:80 的页面
  4. 验证 nftables 中有对应的 DNAT 规则

预期: 端口转发生效
```

**TC-FW-003: Zone 隔离**
```
前置: guest VLAN 已创建 (192.168.10.0/24)

步骤:
  1. 从 guest 网段的设备 ping lan 网段 → 不通
  2. 从 guest 网段 ping 外网 → 通
  3. 从 lan 网段 ping guest → 不通 (isolated)

预期: Zone 隔离策略生效
```

**TC-FW-004: Web GUI 防火墙页面**
```
步骤:
  1. 进入"防火墙"页面
  2. 验证:
     - Zones 列表正确显示
     - 端口转发规则列表
     - 允许新建规则
     - 规则启用/禁用切换
     - 删除规则

预期: 防火墙 GUI 与 nftables 规则一致
```

### 4.4 Multi-WAN

**TC-MWAN-001: 故障切换**
```
前置: 2 个 WAN 口 (wan0, wan1)

步骤:
  1. 配置 wan0(主) wan1(备)
  2. 确认当前默认路由指向 wan0
  3. 断开 wan0 网线
  4. 等待健康检查检测 (≤15s)
  5. 检查默认路由 → 切换到 wan1
  6. 恢复 wan0 网线
  7. 等待恢复检测
  8. 检查默认路由 → 切回 wan0

预期: 10-15s 内自动切换，切换期间已有连接可能中断但新连接正常
```

**TC-MWAN-002: Web GUI Multi-WAN 页面**
```
步骤:
  1. 进入"多 WAN"页面
  2. 验证:
     - 显示各 WAN 线路状态 (health/latency/IP)
     - 显示当前活跃 WAN
     - 支持切换策略 (failover/weighted-rr)
     - 支持手动切换
     - 健康检查参数可配置

预期: GUI 状态与系统实际状态一致
```

### 4.5 DHCP/DNS

**TC-DHCP-001: DHCP 地址分配**
```
步骤:
  1. 客户端连接 LAN 口
  2. 客户端请求 DHCP
  3. 检查客户端 IP → 在 192.168.21.50-200 范围内
  4. 检查 dnsmasq.leases 文件 → 客户端记录存在

预期: DHCP 分配正常
```

**TC-DHCP-002: 静态租约**
```
步骤:
  1. 添加静态租约: MAC=aa:bb:cc:11:22:33 → IP=192.168.21.100
  2. 使用虚拟网口模拟该 MAC
  3. 请求 DHCP → 获取 192.168.21.100

预期: 静态绑定生效
```

**TC-DNS-001: DNS 解析**
```
步骤:
  1. dig @192.168.21.1 baidu.com
  2. 确认返回 A 记录
  3. dig @192.168.21.1 google.com
  4. 确认返回 A 记录

预期: DNS 解析正常
```

**TC-DNS-002: 域名分流**
```
前置: 已配置分流规则 (google.com → 8.8.8.8)

步骤:
  1. dig @192.168.21.1 google.com
  2. 查看 dnsmasq 日志 → 查询转发到 8.8.8.8
  3. dig @192.168.21.1 baidu.com
  4. 查看 dnsmasq 日志 → 查询转发到 223.5.5.5

预期: 域名分流生效
```

**TC-DNS-003: Web GUI DHCP 页面**
```
步骤:
  1. 进入"DHCP"页面
  2. 验证:
     - 租约列表显示正确
     - 静态绑定可增删改
     - DHCP 池配置可修改
     - 在线/离线状态实时更新

预期: GUI 与 dnsmasq 数据一致
```

### 4.6 VPN 通道

**TC-VPN-001: WireGuard 建立**
```
步骤:
  1. 配置 WireGuard 服务端
  2. 生成客户端配置
  3. 在另一台 VM 上启动 WireGuard 客户端
  4. wg show → 看到 handshake
  5. 从客户端 ping 10.0.1.1 → 通

预期: WireGuard 隧道建立成功
```

**TC-VPN-002: Web GUI 通道状态**
```
前置: WireGuard / Tailscale / Clash 至少一个在运行

步骤:
  1. 进入"VPN/通道"页面
  2. 验证:
     - "直连"通道始终存在
     - WireGuard 状态显示 (peer/handshake/传输量)
     - Tailscale 状态显示 (Exit Node/延迟)
     - Clash 状态显示 (节点/延迟)
     - 通道列表与系统实际状态一致

预期: GUI 通道状态准确反映系统实际状态
```

### 4.7 流量编排

**TC-ORC-001: 设备识别**
```
前置: 至少一台设备已连接并获取 DHCP

步骤:
  1. 进入"流量编排 → 设备列表"页面
  2. 验证:
     - 已连接的设备自动出现在列表中
     - 设备名称自动识别 (DHCP hostname / MAC OUI)
     - IP/MAC/在线状态正确
     - 可手动重命名设备

预期: 设备列表准确反映在线设备
```

**TC-ORC-002: 编排规则创建**
```
步骤:
  1. 添加编排规则: 设备A + Netflix → ts-exit-us (备用: direct)
  2. 验证 nftables 中有对应的 mangle 规则
  3. 验证 ip rule 中有对应的 fwmark 规则
  4. 验证 ip route 中有对应的路由表

预期: 编排规则编译为完整的 nftables + ip rule + ip route 三层规则
```

**TC-ORC-003: 编排规则删除**
```
步骤:
  1. 删除上一步创建的编排规则
  2. 验证 nftables 中对应的规则已移除
  3. 验证 ip rule 中对应的规则已移除
  4. 验证 ip route 中对应的路由表已清理

预期: 规则删除后系统状态恢复
```

**TC-ORC-004: Web GUI 编排画布**
```
步骤:
  1. 进入"流量编排"页面
  2. 验证:
     - 左侧设备列表
     - 中间可拖拽连线
     - 右侧通道列表
     - 创建规则后显示连线
     - 删除规则后连线消失
     - 流量统计显示正确

预期: 可视化编排操作直观，与底层规则一致
```

### 4.8 应用市场

**TC-APP-001: 应用安装（容器类型）**
```
前置: Docker 已安装

步骤:
  1. 进入应用市场
  2. 选择一个容器应用 (如 Uptime Kuma)
  3. 点击安装
  4. 验证 docker compose up 成功
  5. 验证容器运行
  6. 验证应用状态页显示 "运行中"

预期: 容器应用通过应用市场一键安装成功
```

**TC-APP-002: 应用更新**
```
步骤:
  1. 已安装的应用 → 检测到新版本
  2. 点击更新
  3. 验证: 旧容器停止 → 新镜像拉取 → 新容器启动
  4. 验证应用数据保留

预期: 应用更新不丢数据
```

**TC-APP-003: 应用卸载**
```
步骤:
  1. 点击卸载 (保留数据)
  2. 验证 docker compose down
  3. 验证数据目录存在 (未删除)
  4. 验证应用从已安装列表移除

预期: 应用卸载干净，数据保留
```

**TC-APP-004: Web GUI 应用市场页面**
```
步骤:
  1. 进入"应用市场"页面
  2. 验证:
     - 分类浏览 (智能家居/媒体/网络工具...)
     - 搜索功能
     - 应用详情页 (描述/截图/配置参数)
     - 安装按钮
     - 安装进度条
     - 安装完成后显示"打开"按钮

预期: 应用市场页面完整可用
```

### 4.9 系统管理

**TC-SYS-001: 配置备份与恢复**
```
步骤:
  1. 创建包含端口转发、静态租约、VLAN 的配置
  2. 导出配置 (下载 tar.gz)
  3. 删掉 config.yaml
  4. 导入配置
  5. Apply
  6. 验证所有配置恢复

预期: 配置备份完整，恢复后系统状态一致
```

**TC-SYS-002: 配置变更自动回滚**
```
步骤:
  1. 修改 WAN IP 为 10.0.0.1/24 (当前无此网段)
  2. Apply → 网络失联
  3. 等待 60 秒 → 自动回滚
  4. 验证恢复为原配置
  5. ssh 重新连入正常

预期: 断网配置 60s 自动回滚
```

**TC-SYS-003: 配置快照手动回滚**
```
步骤:
  1. 查看快照列表
  2. 选中一个历史快照
  3. 点击回滚
  4. 验证配置恢复为快照时刻的状态

预期: 快照回滚精确恢复
```

**TC-SYS-004: Web GUI 系统页面**
```
步骤:
  1. 进入"系统"页面
  2. 验证:
     - 系统信息显示正确
     - 日志过滤/搜索
     - 备份/恢复按钮可用
     - 快照列表
     - Web 终端可打开 (ttyd)

预期: 系统页面功能完整
```

### 4.10 Dashboard

**TC-DASH-001: 三段式 Dashboard 加载**
```
步骤:
  1. 浏览器登录
  2. 验证第一个面板:
     - 网络拓扑图显示 (WAN/LAN/VLAN)
     - 通道状态卡片 (TS/Clash/WG 状态)
     - 实时流量折线图
  3. 验证第二个面板:
     - CPU 利用率
     - 内存使用
     - 磁盘使用
     - 网口状态
     - 运行时间
  4. 验证第三个面板:
     - 已安装应用卡片
     - 运行/停止/异常状态
     - 网络消耗排行

预期: 三面板完整加载，数据实时更新
```

**TC-DASH-002: 地图组件**
```
前置: 至少 Tailscale 或 Clash 在运行

步骤:
  1. 在 Dashboard 查看地图区域
  2. 验证:
     - 本地网关位置显示 (公网 IP 归属地)
     - Tailscale Exit Node 位置
     - Clash 节点位置
     - 链路线条颜色正确 (绿/黄/红)
     - 鼠标悬停显示延迟

预期: 地图组件正确显示网络拓扑
```

**TC-DASH-003: WebSocket 实时更新**
```
步骤:
  1. 打开浏览器开发者工具 → Network → WS
  2. 验证 WebSocket 连接建立
  3. 验证每 2 秒收到 traffic_update 消息
  4. 验证每 10 秒收到 tunnel_status 消息
  5. 验证每 30 秒收到 system_status 消息
  6. 验证页面数据自动刷新，无需手动刷新

预期: 实时数据通过 WebSocket 推送，页面自动更新
```

### 4.11 鉴权

**TC-AUTH-001: 登录流程**
```
步骤:
  1. 浏览器访问 http://192.168.21.1
  2. 验证自动重定向到 HTTPS
  3. 显示登录页面
  4. 输入错误密码 → 提示错误 + 剩余尝试次数
  5. 连续 5 次错误 → 锁定 15 分钟
  6. 输入正确系统账号密码 → 登录成功
  7. 验证 Token 存入 localStorage

预期: 系统 PAM 认证生效，登录流程完整
```

**TC-AUTH-002: Session 管理**
```
步骤:
  1. 登录成功后
  2. 查看页面右上角用户名
  3. 点击注销 → 跳转登录页
  4. 重新登录
  5. 进入 Session 管理页面
  6. 验证显示活跃 Session
  7. 点击强制登出 → 另一端的 Session 失效

预期: Session 管理功能正常
```

**TC-AUTH-003: Token 过期**
```
步骤:
  1. 获取 JWT
  2. 手动修改 Token 过期时间为 1 秒后
  3. 等待 2 秒
  4. 发送 API 请求 → 返回 401
  5. 页面自动跳转登录页

预期: Token 过期后自动跳转登录
```

### 4.12 配置一致性校验

**TC-CONSISTENCY-001: Web GUI 操作 → 系统状态一致性**
```
测试方法: 在 Web GUI 执行操作后，通过命令行验证实际系统状态

# 每项操作的验证命令
# 创建 VLAN:   ip link show
# 端口转发:   nft list chain ip ubunturouter prerouting
# 静态租约:   cat /var/lib/misc/dnsmasq.leases
# WAN 配置:   ip route show table 254
# MTU 修改:   ip link show enp1s0
# MAC 修改:   ip link show enp1s0
# DNS:        dig @192.168.21.1
```

---

## 5. E2E 测试 (Playwright)

```typescript
// playwright/tests/dashboard.spec.ts
// 浏览器自动化测试

test('Dashboard 三面板加载', async ({ page }) => {
  // 登录
  await page.goto('https://192.168.21.1');
  await page.fill('input[name="username"]', 'ihermes');
  await page.fill('input[name="password"]', 'dragon88');
  await page.click('button[type="submit"]');
  
  // 验证三面板
  await expect(page.locator('[data-testid="panel-network"]')).toBeVisible();
  await expect(page.locator('[data-testid="panel-system"]')).toBeVisible();
  await expect(page.locator('[data-testid="panel-apps"]')).toBeVisible();
  
  // 验证地图组件
  await expect(page.locator('[data-testid="geo-map"]')).toBeVisible();
});

test('防火墙端口转发 CRUD', async ({ page }) => {
  // 进入防火墙页面
  await page.click('text=防火墙');
  
  // 新增端口转发
  await page.click('text=新增端口转发');
  await page.fill('input[name="from_port"]', '8080');
  await page.fill('input[name="to_ip"]', '192.168.21.100');
  await page.fill('input[name="to_port"]', '80');
  await page.click('text=保存');
  
  // 验证出现在列表中
  await expect(page.locator('text=192.168.21.100:80')).toBeVisible();
  
  // 验证底层 nftables 规则
  // 通过浏览器终端执行 nft list chain... 检查
});
```

---

## 6. 自动化测试 CI 集成

```yaml
# .github/workflows/test.yml
name: UbuntuRouter Tests

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v --cov=ubunturouter
  
  integration-tests:
    runs-on: [self-hosted, test-vm]
    steps:
      - run: sudo ./tests/run_integration.sh
  
  e2e-tests:
    runs-on: [self-hosted, test-vm]
    steps:
      - run: npx playwright test
```

---

## 7. 测试数据管理

```bash
# 创建测试数据脚本
#!/bin/bash
# tests/setup_test_data.sh

# 添加测试用端口转发
urctl config apply <<EOF
interfaces:
  - name: wan0
    device: ens3
    role: wan
    ipv4: {method: dhcp}
  - name: br-lan
    type: bridge
    device: br-lan
    ports: [ens3]
    role: lan
    ipv4: {method: static, address: "192.168.21.1/24"}

firewall:
  port_forwards:
    - name: test_web
      from_port: 8080
      to_ip: 192.168.21.100
      to_port: 80
  zones:
    wan: {masquerade: true}
    lan: {forward_to: [wan]}

dhcp:
  range: [192.168.21.50, 192.168.21.200]
  static_leases:
    - mac: "aa:bb:cc:11:22:33"
      ip: "192.168.21.100"
      hostname: "test-device"
EOF

echo "测试数据已加载"
```

---

## 8. 测试优先级

| 优先级 | 模块 | 测试类型 | 人工/自动 |
|--------|------|----------|-----------|
| **P0** | Login / Auth | E2E + 手动 | 人工 + Playwright |
| **P0** | Dashboard 三面板 | E2E | Playwright |
| **P0** | 网络接口 CRUD | 集成 + E2E | Shell + Playwright |
| **P0** | 防火墙规则 | 集成 + E2E | Shell + Playwright |
| **P0** | DHCP 租约 | 集成 | Shell |
| **P0** | DNS 解析 | 集成 | Shell |
| **P0** | 配置 Apply + 回滚 | 集成 | Shell |
| **P1** | Multi-WAN 切换 | 集成 | Shell (需双网口) |
| **P1** | VPN 隧道 | 集成 | Shell (需另一台) |
| **P1** | 应用市场 | E2E | Playwright |
| **P1** | 流量编排 | E2E | Playwright |
| **P1** | 虚拟机管理 | E2E | Playwright (需 KVM) |
| **P2** | FRR 动态路由 | 集成 | Shell (需 FRR 环境) |
| **P2** | XDP 加速 | 性能 | 手动 (需特定网卡) |
