# Sprint 6: 流量编排 + Dashboard 完整化

> 周期: 第 15-17 周 | 状态: **✅ 已完成** | 负责人: TBD

---

## 范围

实现流量编排的完整功能：设备识别、应用特征库、可视化编排画布、规则编译、故障转移、流量统计。同时完善 Dashboard 的地图组件和应用卡片。

## 任务拆解

### Week 15: 设备识别 + 应用特征库

| ID | 任务 | 预估(h) | 前置 | 产出 |
|----|------|---------|------|------|
| 15.1 | 设备检测引擎：DHCP lease 监听 + MAC OUI 库 + mDNS 侦测 | 10 | Sprint 2 | `ubunturouter/orchestrator/device_detector.py` |
| 15.2 | 应用特征库：YAML 格式定义 + 域名/IP 集合 | 8 | - | `ubunturouter/orchestrator/app_db.py` |
| 15.3 | DNS 应用识别：hook dnsmasq 日志，匹配应用特征 | 6 | 15.2 | `ubunturouter/orchestrator/app_detector.py` |
| 15.4 | 设备 API：list / rename / status | 6 | 15.1 | `ubunturouter/api/routes/devices.py` |
| 15.5 | 应用 API：list / search | 4 | 15.2 | `ubunturouter/api/routes/apps.py` |

### Week 16: 规则编译器 + 可视化编排画布

| ID | 任务 | 预估(h) | 前置 | 产出 |
|----|------|---------|------|------|
| 16.1 | Rule Compiler：编排规则 → nftables set + mark + ip rule + 路由表 | 14 | 15.2 + Sprint 1 | `ubunturouter/orchestrator/compiler.py` |
| 16.2 | 规则增量更新：nft add element / ip rule replace | 6 | 16.1 | `ubunturouter/orchestrator/compiler.py` |
| 16.3 | 故障转移引擎：通道状态监听 + 自动切换 | 8 | 16.1 + 10.5 | `ubunturouter/orchestrator/failover.py` |
| 16.4 | 流量统计聚合：conntrack + nft counter 读取 | 6 | 16.1 | `ubunturouter/orchestrator/stats.py` |
| 16.5 | 编排 API：rules CRUD / stats / tunnels | 10 | 16.1-16.4 | `ubunturouter/api/routes/orchestrator.py` |
| 16.6 | 集成测试：规则编译 → 系统规则验证 | 8 | 16.5 | `tests/integration/test_orchestrator.sh` |

### Week 17: Web GUI 画布 + Dashboard 完善

| ID | 任务 | 预估(h) | 前置 | 产出 |
|----|------|---------|------|------|
| 17.1 | 设备列表组件：设备卡片 + 在线状态 + 已识别应用 | 6 | 15.4 + 6.3 | `web/src/components/DeviceList.vue` |
| 17.2 | 可视化编排画布：拖拽设备→选择应用→选择通道→连线 | 16 | 16.5 | `web/src/views/orchestrator/OrchestratorCanvas.vue` |
| 17.3 | 编排规则列表：表格展示 + 启用/禁用/删除 | 6 | 17.2 | `web/src/views/orchestrator/RuleList.vue` |
| 17.4 | 流量统计视图：按设备/应用/通道 维度 | 8 | 16.5 | `web/src/views/orchestrator/StatsView.vue` |
| 17.5 | 预置编排模板：海外视频/国内直连/游戏加速/NAS 远程 | 6 | 17.2 | `web/src/views/orchestrator/Templates.vue` |
| 17.6 | Dashboard 应用卡片完善：状态颜色 + 网络消耗排行 + 快捷操作 | 8 | Sprint 2 | 更新 `AppPanel.vue` |
| 17.7 | 通道状态 WebSocket 集成到 Dashboard 地图 | 4 | 17.6 + 11.3 | 更新 Dashboard WS |
| 17.8 | E2E 测试：编排画布完整流程 + Dashboard 一致性 | 10 | 17.7 | `web/e2e/orchestrator.spec.ts` |

## 验收标准

| # | 验收项 | 验证方式 |
|---|--------|----------|
| S6-01 | 设备自动识别（DHCP 设备出现后 10s 内） | 页面验证 |
| S6-02 | DNS 查询匹配应用特征 (dig nflxvideo.net → Netflix) | 页面验证 |
| S6-03 | 编排规则创建 → nftables mangle + ip rule + ip route 生成 | 命令行验证 |
| S6-04 | 编排画布拖拽连线创建规则 | 浏览器验证 |
| S6-05 | 故障转移：主通道 dead → 备通道生效 | 断线验证 |
| S6-06 | 流量统计按设备/应用/通道 正确 | 页面验证 |
| S6-07 | 预置模板一键应用 | 模板规则可删除 |
| S6-08 | Dashboard 三面板数据与系统实际状态一致 | 对比验证 |
