# Sprint 4: VPN 通道 + 网络拓扑地图 + Multi-WAN 完善

> 周期: 第 10-12 周 | 状态: **✅ 已完成** | 负责人: TBD

---

## 范围

实现 WireGuard VPN 隧道管理（后端引擎 + API + Web GUI）、网络拓扑可视化地图组件，以及 Multi-WAN 的持久化配置与健康检查自动切换。

---

## Week 10: VPN 通道管理

### 任务拆解

| ID | 任务 | 预估(h) | 前置 | 产出 |
|----|------|---------|------|------|
| 10.1 | VPN 后端引擎 — `src/ubunturouter/vpn/__init__.py` | 10 | Sprint 1 | WireGuardManager: 隧道 CRUD、Peer CRUD、启停、状态检测 |
| 10.2 | VPN API 路由 — `api/routes/vpn.py` | 6 | 10.1 | 隧道列表/详情、Peer 管理、启停操作、状态统计 |
| 10.3 | VPN Web 页面 — `web/src/views/vpn/` | 12 | 10.2 + Sprint 2 | 隧道管理表格、Peer 管理、连接状态、流量统计 |
| 10.4 | 导航菜单 + 路由注册 | 2 | 10.3 | MainLayout + router/index.js 更新 |

## 验收标准

| # | 验收项 | 状态 | 验证方式 |
|---|--------|------|----------|
| S4-01 | Web 创建 WireGuard 隧道 → `wg show` 确认接口 up | ✅ | API 创建配置 + wg-quick up 启动成功 |
| S4-02 | Web 添加 Peer → wg show 确认 | ✅ | API 添加 peer 到配置 + 运行时同步 |
| S4-03 | Web 启停隧道 → 接口状态变化 | ✅ | wg-quick up/down 成功 |
| S4-04 | Web 查看隧道流量统计 → RX/TX 显示 | ✅ | API 返回 transfer_rx/transfer_tx |
| S4-05 | Dashboard 显示网络拓扑图 | ✅ | ECharts 力导向图，含路由器+接口+ARP 设备 |
| S4-06 | 设备离线时节点变红色 | ✅ | ARP 节点 online=false → 红色标记 |

## Week 11: 网络拓扑地图

### 任务拆解

| ID | 任务 | 预估(h) | 前置 | 产出 |
|----|------|---------|------|------|
| 11.1 | 设备发现 API — ARP 表扫描 + 接口邻居 | 4 | Sprint 1 | `api/routes/topology.py`: `GET /topology/devices` |
| 11.2 | 拓扑地图组件 — `web/src/components/NetTopo.vue` | 14 | 11.1 | ECharts 力导向图: 设备节点 + 链路 + 状态颜色 |
| 11.3 | Dashboard 集成拓扑图 | 4 | 11.2 | Dashboard.vue 嵌入 NetTopo 组件 |

### 验收标准

| # | 验收项 | 验证方式 |
|---|--------|----------|
| S4-05 | Dashboard 显示网络拓扑图，节点包括路由器+客户端 | 浏览器查看 |
| S4-06 | 设备离线时节点变红色 | ARP 表删除后刷新 |

---

## Week 12: Multi-WAN 完善

### 任务拆解

| ID | 任务 | 预估(h) | 前置 | 产出 |
|----|------|---------|------|------|
| 12.1 | Multi-WAN 持久化配置 — 写入 Netplan 策略路由 | 8 | Sprint 3 | 路由规则持久化到 YAML |
| 12.2 | 健康检查引擎 — ping/http 探测 + 自动切换 | 10 | 12.1 | `src/ubunturouter/multiwan/health.py` |
| 12.3 | Multi-WAN 后端 API 增强 | 4 | 12.2 | 健康检查配置、自动切换设置 |
| 12.4 | Multi-WAN Web 配置页面 | 8 | 12.3 | 健康检查参数配置、策略选择 |
| 12.5 | 集成测试 + E2E 测试 | 8 | 12.4 | `tests/` |

### 验收标准

| # | 验收项 | 验证方式 |
|---|--------|----------|
| S4-07 | 配置健康检查参数 → 定时 ping 执行 | 查看日志 |
| S4-08 | WAN1 断线 → 自动切换到 WAN2 | ping + ip route |
| S4-09 | 策略路由 reboot 后持久化 | reboot + ip route |
| S4-10 | Multi-WAN 负载均衡基础规则生效 | nftables mark + ip rule |

---

## 总体交付清单

| 交付物 | 类型 | 路径 |
|--------|------|------|
| WireGuardManager | Python 模块 | `src/ubunturouter/vpn/__init__.py` |
| VPN API | FastAPI 路由 | `src/ubunturouter/api/routes/vpn.py` |
| VPN Web | Vue 组件 | `web/src/views/vpn/VpnTunnels.vue` |
| 设备发现 API | FastAPI 路由 | `src/ubunturouter/api/routes/topology.py` |
| NetTopo 组件 | Vue 组件 | `web/src/components/NetTopo.vue` |
| Multi-WAN 健康检查 | Python 模块 | `src/ubunturouter/multiwan/health.py` |
| Multi-WAN 配置页 | Vue 组件 | `web/src/views/multiwan/` |
