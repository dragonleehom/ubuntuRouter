# Sprint 4: VPN 通道 + 地图组件 + Multi-WAN 健康检查

> 周期: 第 10-11 周 | 状态: 待开始 | 负责人: TBD

---

## 范围

实现 VPN/代理通道的统一管理 API 和状态监控，Dashboard 地图组件，Multi-WAN 健康检查引擎的集成。

## 任务拆解

### Week 10: VPN/通道 API + 状态监控

| ID | 任务 | 预估(h) | 前置 | 产出 |
|----|------|---------|------|------|
| 10.1 | 通道抽象 API：tunnels list / test / status | 6 | Sprint 1 | `ubunturouter/api/routes/vpn.py` |
| 10.2 | WireGuard API：peers CRUD / config 生成 / 二维码 | 10 | Sprint 1 | `ubunturouter/api/routes/wireguard.py` |
| 10.3 | Tailscale 状态集成：tailscale status --json 解析 | 6 | - | `ubunturouter/vpn/tailscale.py` |
| 10.4 | Clash 状态集成：Clash API proxy/traffic/delay | 6 | - | `ubunturouter/vpn/clash.py` |
| 10.5 | 通道健康检查：定时 ping 各通道对端 | 4 | 10.1 | `ubunturouter/vpn/health.py` |
| 10.6 | VPN Web 页面：通道总览 + WireGuard Peer 管理 + 配置生成 | 12 | 10.1-10.4 | `web/src/views/vpn/` |
| 10.7 | 集成测试：WG 建立/状态/配置生成 | 6 | 10.6 | `tests/integration/test_vpn.sh` |

### Week 11: 地图组件 + Multi-WAN 健康检查

| ID | 任务 | 预估(h) | 前置 | 产出 |
|----|------|---------|------|------|
| 11.1 | GeoIP 引擎：内置 GeoIP 数据库查询 + 缓存 | 6 | - | `ubunturouter/vpn/geoip.py` |
| 11.2 | 地图数据聚合 API：收集所有通道地理信息 | 6 | 11.1 + 10.1 | `ubunturouter/api/routes/geo.py` |
| 11.3 | 前端地图组件：Leaflet.js + OSM 瓦片 + 节点标注 + 链路线条 | 14 | 11.2 + 6.3 | `web/src/components/GeoMap.vue` |
| 11.4 | Multi-WAN 健康检查引擎集成：后台线程 + 状态回调 + 自动切换 | 8 | Sprint 1 | `ubunturouter/routing/healthcheck.py` |
| 11.5 | Multi-WAN Dashboard 集成：WAN 线路状态实时显示 | 6 | 11.4 + 5.2 | Dashboard WS 推送更新 |
| 11.6 | E2E 测试：地图组件渲染 + 通道状态验证 | 8 | 11.3 | `web/e2e/geo-map.spec.ts` |

## 验收标准

| # | 验收项 | 验证方式 |
|---|--------|----------|
| S4-01 | WireGuard Peer 添加后 VPN 隧道建立 | wg show |
| S4-02 | 客户端配置文件生成后可导入手机 | 生成 .conf 验证格式 |
| S4-03 | Tailscale 状态在 Dashboard 中显示 | 页面验证 |
| S4-04 | Clash 节点延迟在 Dashboard 中显示 | 页面验证 |
| S4-05 | 地图渲染：本地位置 + 各节点 + 链路 | 浏览器验证 |
| S4-06 | 地图链路颜色按延迟分级 | 绿/黄/红 正确 |
| S4-07 | Multi-WAN 健康检查自动切换 | 断开网线验证 |
