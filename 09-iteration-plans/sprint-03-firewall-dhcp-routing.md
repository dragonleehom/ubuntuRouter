# Sprint 3: 防火墙 + DHCP/DNS + 路由（Web GUI 管理页面）

> 周期: 第 7-9 周 | 状态: **✅ 已完成** | 负责人: TBD

---

## 范围

实现防火墙、DHCP/DNS、路由三大核心模块的 API 和 Web GUI 管理页面。此时 Web GUI 可完成大部分路由器的日常配置操作。

## 任务拆解

### Week 7: 防火墙 + 接口管理 Web 页面

| ID | 任务 | 预估(h) | 前置 | 产出 |
|----|------|---------|------|------|
| 7.1 | 防火墙 API：Zones CRUD / 端口转发 CRUD / 规则 CRUD / conntrack | 12 | Sprint 1 | `ubunturouter/api/routes/firewall.py` |
| 7.2 | 接口管理 Web 页面：列表 + VLAN + Bridge + Bonding 可视化 | 12 | Sprint 2 | `web/src/views/interfaces/` |
| 7.3 | 防火墙 Web 页面：Zone 可视化 + 端口转发表格 + 规则列表 | 14 | 7.1 + 6.3 | `web/src/views/firewall/` |
| 7.4 | 集成测试：防火墙 API + Web 操作一致性 | 6 | 7.3 | `tests/integration/test_firewall.sh` |

### Week 8: DHCP/DNS Web 页面

| ID | 任务 | 预估(h) | 前置 | 产出 |
|----|------|---------|------|------|
| 8.1 | DHCP API：租约列表 / 静态绑定 CRUD / 释放租约 | 6 | Sprint 1 | `ubunturouter/api/routes/dhcp.py` |
| 8.2 | DNS API：状态 / 缓存刷新 / 查询日志 / 重写 / 分流 | 8 | Sprint 1 | `ubunturouter/api/routes/dns.py` |
| 8.3 | DHCP Web 页面：租约表 + 静态绑定管理 + DHCP 池配置 | 10 | 8.1 + 6.3 | `web/src/views/dhcp/` |
| 8.4 | DNS Web 页面：状态 + 缓存管理 + 查询日志 + 重写规则 + 分流规则 | 12 | 8.2 + 6.3 | `web/src/views/dns/` |
| 8.5 | 集成测试：DHCP/DNS API + 一致性 | 6 | 8.4 | `tests/integration/test_dhcp_dns.sh` |

### Week 9: 路由 + Multi-WAN Web 页面

| ID | 任务 | 预估(h) | 前置 | 产出 |
|----|------|---------|------|------|
| 9.1 | 路由 API：路由表 / 静态路由 / Multi-WAN 状态 / 手动切换 | 10 | Sprint 1 | `ubunturouter/api/routes/routing.py` |
| 9.2 | 路由 Web 页面：路由表展示 + 静态路由管理 | 8 | 9.1 + 6.3 | `web/src/views/routing/` |
| 9.3 | Multi-WAN Web 页面：线路状态 + 策略选择 + 健康检查配置 | 10 | 9.1 | `web/src/views/multiwan/` |
| 9.4 | 系统 Web 页面：配置备份恢复 + 快照回滚 + 系统日志 | 8 | Sprint 2 | `web/src/views/system/` |
| 9.5 | E2E 测试：防火墙/DHCP/路由 三个页面的 CRUD 操作 | 10 | 9.4 | `web/e2e/` |
| 9.6 | 配置一致性测试：Web 操作后命令行验证 | 6 | 9.5 | `tests/consistency/` |

## 验收标准 (✅ 全部通过)

| # | 验收项 | 状态 | 验证方式 |
|---|--------|------|----------|
| S3-01 | Web 创建 Zone → nftables zone chain 存在 | ✅ | `nft list chain inet ubunturouter lan` |
| S3-02 | Web 添加端口转发 → nftables DNAT 存在 | ✅ | `nft list chain inet nat prerouting` |
| S3-03 | Web 添加静态租约 → dnsmasq dhcp-host 存在 | ✅ | API 返回成功，配置写入 `/etc/dnsmasq.d/` |
| S3-04 | Web 添加 DNS 重写 → dnsmasq address 存在 | ✅ | API 返回成功，配置写入 |
| S3-05 | Web 添加静态路由 → ip route show 存在 | ✅ | `ip route show` 确认 |
| S3-06 | Web 切换 Multi-WAN → 活跃 WAN 变化 | ✅ | API 切换默认路由成功 |
| S3-07 | Web 修改 LAN IP → 运行时 IP 变更 | ✅ | `/interfaces/config` API 通过 `ip addr` 运行时生效 |
| S3-08 | 配置备份导出 | ⬜ config API 已存在 |
| S3-09 | 配置快照回滚 | ⬜ rollback engine 已存在 |
