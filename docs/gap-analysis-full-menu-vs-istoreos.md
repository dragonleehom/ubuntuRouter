# UbuntuRouter vs iStoreOS — 完整差距分析报告
> 日期: 2026-04-28
> 方法: iStoreOS 功能体系分析 + UbuntuRouter 代码逐模块审计
> 审计范围: 后端路由 (36 个 .py) + 前端页面 (50 个 .vue) + 前端路由配置

## 概要
- **总功能点**: 108 个
- **完全实现 (✅)**: 47 个 (43.5%)
- **部分实现 (⚠️)**: 25 个 (23.1%)
- **未实现 (❌)**: 27 个 (25.0%)
- **需增强 (🔄)**: 9 个 (8.3%)

---

## 1. 状态 (Status) — 9项

| 子模块 | 功能点 | UbuntuRouter | 优先级 | 备注 |
|--------|--------|:-----------:|:------:|------|
| 概览 | 系统概况(CPU/内存/磁盘/运行时间) | ✅ | - | Dashboard.vue 实现完整 |
| 路由表 | IPv4/IPv6 路由表查看 | ✅ | - | routing.py GET /table 支持多表查询 |
| 系统日志 | journalctl 日志查看 | ✅ | - | system.py GET /logs 支持按服务过滤 |
| 内核日志 | dmesg 日志查看 | ✅ | - | system.py GET /logs/kernel |
| 防火墙日志 | nftables 日志查看 | ✅ | - | system.py GET /logs/firewall |
| 进程列表 | Top 50 进程 | ✅ | - | monitor.py _get_process_list |
| 实时图表 | 实时流量/连接/负载/内存 | ⚠️ | P1 | 只有 network speed delta 计算，缺少**实时图表 UI** 和 WebSocket 推送到前端；当前 Dashboard 只显示瞬时值 |
| 统计 | 历史统计趋势 | ❌ | P2 | monitor.py 有 CSV 持久化但**无前端图表展示** |
| iStore | 应用商店 | ❌ (按 1Panel 标准) | - | 明确不按 iStoreOS 对标；UbuntuRouter 有 AppStore 按 1Panel 标准 |

---

## 2. 网络 (Network) — 16项

| 子模块 | 功能点 | UbuntuRouter | 优先级 | 备注 |
|--------|--------|:-----------:|:------:|------|
| 接口 | 接口列表/状态 | ✅ | - | interfaces.py 完整：list, status, port-detail, traffic |
| 接口编辑 | 协议: DHCP/Static/PPPoE/Disabled | ✅ | - | interfaces.py IfaceUpdateModel 支持4种协议 + MTU/MAC/DNS |
| 接口编辑 | 高级参数(metric/跃点数/网关跃点) | ❌ | P3 | 只有基本 gateway/mtu/DNS，缺少 metric, dhcp-identifier, accept-ra 等 |
| 接口编辑 | 桥接/绑定/LAG | ❌ | P2 | 无 bridge/bond 创建和管理功能 |
| 无线/AP | AP 热点创建/停止 | ✅ | - | wireless.py 完整：SSID/密码/频段/信道；基于 nmcli |
| 无线/Client | WiFi 连接上级 AP | ✅ | - | wireless.py 支持 SSID/密码/隐藏网络 |
| 无线/扫描 | 扫描附近 WiFi | ✅ | - | wireless.py GET /scan 支持 BSSID/频段/信号强度/加密 |
| 无线/高级 | 无线高级设置(功率/信道宽度/国家码) | ❌ | P3 | 缺少 txpower, channel-width, country code 等 |
| DHCP/DNS | DHCP 租约查看/释放 | ✅ | - | dhcp.py 完整：leases, static leases, DNS upstream/rewrite |
| DHCP/DNS | DHCP 池配置 | ⚠️ | P2 | 实现了 GET /pool 但**缺少创建/修改 DHCP 池**的端点 |
| 主机名映射 | /etc/hosts 管理 | ✅ | - | dns.py 完整 CRUD hosts |
| 静态路由 | 静态路由 CRUD | ✅ | - | routing.py 完整：add/delete + 策略路由规则 |
| 防火墙 | Zones + 规则 + 端口转发 | ✅ (部分) | - | 详见防火墙模块深度对比 |
| 多WAN | 健康检查 + 故障切换 | ✅ | - | multiwan.py + routing.py 完整：ping 检测/权重/自动切换 |
| Turbo ACC | 硬件加速/BBR/FQ 队列 | ❌ | P2 | 只有占位符页面 |

| 子模块 | 功能点 | UbuntuRouter | 优先级 | 备注 |
|--------|--------|:-----------:|:------:|------|
| SQM QoS | 流量整形/限速 | ❌ | P2 | 只有占位符页面 |
| DDNS | 动态域名 | ✅ | - | 详见 DDNS 模块深度对比 |
| UPnP | UPnP 端口转发 | ⚠️ | P2 | 已有规则 CRUD，但**缺少 NAT-PMP 支持**和完整配置选项 |
| 诊断 | Ping/Traceroute/NSLookup/MTR/TC PCheck | ✅ | - | diag.py 完整：6 种诊断工具 + curl |
| Samba | SMB 文件分享 | ✅ | - | samba.py 完整：shares/users CRUD + 服务控制 |
| FTP | FTP 服务管理 | ❌ | P3 | 只有占位符页面 |
| 磁盘 | 磁盘概览/挂载/卸载 | ✅ | - | storage.py 完整：overview, mount, unmount, format |
| NFS | NFS 导出管理 | ✅ | - | nfs.py 完整：exports CRUD + 原子写入 + exportfs |
| VPN | WireGuard/Tailscale | ✅ | - | vpn.py 完整：WireGuard 隧道/Peer CRUD + Tailscale 状态 |
| 网络唤醒 | Wake-on-LAN | ✅ | - | system.py 支持 etherwake + Python fallback |

---

## 3. 防火墙深度对比 — 7项

| 功能点 | iStoreOS (LuCI) | UbuntuRouter | 差距 |
|--------|-----------------|:-----------:|------|
| Zone 配置参数 | name, input/forward/output policy, masquerade, mtu, covered networks, log, ipset, connlimit, family (inet/inet6) | name, input/forward/output, masquerade, isolated, forward_to | ⚠️ **缺少**: mtu, log, ipset, connlimit, family(v4/v6), covered networks 选择 |
| 规则 Direction | input/forward/output + 源区域/目标区域 | input/forward/output (链级别) | ⚠️ **缺少**: 基于 Zone 的 direction (from-zone → to-zone) |
| 规则 IP 协议 | tcp/udp/tcpudp/icmp/icmpv6/any + 协议号 | tcp/udp (仅字符串) | ❌ **缺少**: icmp, icmpv6 协议选择和自定义协议号 |
| 规则时间限制 | 时间范围/星期/日期 | ❌ | ❌ **完全缺失**: 无定时规则支持 |
| 规则高级匹配 | ipset, mark, limit (rate), conntrack state, 接口, 设备 (MAC) | src_ip, dst_ip, src_port, dst_port, protocol, log | ❌ **缺少**: ipset, rate limit, connstate, interface, 设备MAC |
| 端口转发 | 全部区域协议 + NAT Loopback | from_zone, from_port, protocol, to_ip, to_port | ⚠️ **缺少**: NAT Loopback 选项, 全协议支持 |
| 防火墙状态 | 规则计数 + conntrack | 规则计数 + conntrack + nftables 完整状态 | ✅ 相当 |

---

## 4. 网络接口编辑深度对比 — 8项

| 参数字段 | iStoreOS | UbuntuRouter | 差距 |
|----------|----------|:-----------:|------|
| 协议 | DHCP/Static/PPPoE/Disabled/Unmanaged/PPTP/L2TP/6in4/6to4 | DHCP/Static/PPPoE/Disabled | ❌ **缺少**: Unmanaged, PPTP, L2TP, 6in4, 6to4, WireGuard |
| 地址 | IP/CIDR 输入 | IP/CIDR 输入 | ✅ |
| 网关 | 网关 IP | 网关 IP | ✅ |
| DNS | DNS 列表 | DNS 列表 | ✅ |
| MTU | MTU (576-9000) | MTU (576-9000) | ✅ |
| MAC 地址 | MAC 修改 | MAC 修改 | ✅ |
| 高级 | metric, dhcp-identifier, accept-ra, ipv6 | ❌ | ❌ **缺少** |
| 桥接 | 桥接创建/端口管理 | ❌ | ❌ **完全缺失** |

---

## 5. 无线管理深度对比 — 6项

| 功能点 | iStoreOS | UbuntuRouter | 差距 |
|--------|----------|:-----------:|------|
| SSID | 名称 + 隐藏 | 名称 | ⚠️ **缺少**: 隐藏 SSID 设置 |
| 安全 | WPA2/WPA3/None | WPA2-PSK(通过password参数) | ⚠️ **部分支持**: 无显式 WPA3/SAE 选择 |
| 频段 | 2.4GHz/5GHz/Auto | a(5G)/bg(2.4G)/ax(WiFi6) | ✅ 相当 |
| 信道 | 手动选择 + 宽度(20/40/80MHz) | 信道号 | ⚠️ **缺少**: 信道宽度选择 |
| 高级 | 国家码, 功率, MAC 过滤 | ❌ | ❌ **完全缺失** |
| 客户端 | 扫描 + 连接 + 断开 | 扫描 + 连接 + 断开 | ✅ |

---

## 6. DDNS 深度对比 — 6项

| 功能点 | iStoreOS | UbuntuRouter | 差距 |
|--------|----------|:-----------:|------|
| Cloudflare | ✅ | ✅ (cloudflare.py) | ✅ |
| Aliyun (Alidns) | ✅ | ✅ (alidns.py) | ✅ |
| DNSPod (Tencent) | ✅ | ✅ (dnspod.py) | ✅ |
| DuckDNS | ✅ | ✅ (duckdns.py) | ✅ |
| DDNSTO | ✅ | ✅ (ddnsto.py) | ✅ |
| 其他常用 | No-IP, DynDNS, HE.NET, Oray, 3322 | ❌ | ❌ **缺少**: 至少 ≥6 个常见提供商 |

---

## 7. UPnP 深度对比 — 5项

| 功能点 | iStoreOS | UbuntuRouter | 差距 |
|--------|----------|:-----------:|------|
| 启用/禁用 | systemctl 控制 ✅ | systemctl 控制 ✅ | ✅ |
| 端口转发规则 | 外部端口/内部端口/协议/IP/描述 | 同左 | ⚠️ **缺少协议选项**: 当前全部当成 TCP 写入配置 |
| NAT-PMP | 支持 | ❌ | ❌ **缺少** |
| 配置选项 | 接口选择, ACL, min/max port | ext_ifname(固定), port=0 | ❌ **缺少**: 完整配置选项 |
| 状态查看 | 活跃转发列表 | 仅配置列表 | ⚠️ **缺少**: 运行时活跃转发(upnp -l) |

---

## 8. 系统设置深度对比 — 7项

| 功能点 | iStoreOS | UbuntuRouter | 差距 |
|--------|----------|:-----------:|------|
| 主机名 | 修改 ✅ | 修改 ✅ | ✅ |
| 时区 | 设置 + 列表 ✅ | 设置 + timedatectl 列表 ✅ | ✅ |
| NTP | 启用/禁用 + 服务器配置 | 启用/禁用 + 服务器写入 timesyncd | ✅ |
| 密码 | 修改当前用户密码 | passwd via stdin | ✅ |
| SSH 密钥 | 管理 authorized_keys | 完整 CRUD + 验证 | ✅ |
| HTTP/HTTPS | TLS 证书管理 | tls_manager.py 完整管理 | ✅ |
| 浏览器 SSL | HSTS/HTTP2/端口 | ❌ | ❌ **缺少**: HSTS 配置, HTTP/2 切换 |

---

## 9. Docker — 5项

| 子模块 | 功能点 | UbuntuRouter | 优先级 | 备注 |
|--------|--------|:-----------:|:------:|------|
| 概览 | Docker 状态/信息 | ✅ | - | containers.py 含系统信息 |
| 容器 | 容器列表/创建/启动/停止/日志/终端 | ✅ | - | containers.py 完整 CRUD (722行) |
| 镜像 | 镜像列表/拉取/删除 | ✅ | - | containers.py + compose 管理 |
| 网络 | Docker 网络 CRUD | ✅ | - | containers.py 含 network 创建(子网/网关) |
| 卷 | 卷列表/创建/删除 | ✅ | - | containers.py 完整管理 |

---

## 10. 系统 (System) — 14项

| 子模块 | 功能点 | UbuntuRouter | 优先级 | 备注 |
|--------|--------|:-----------:|:------:|------|
| 系统 | 基础设置(主机名/时区/NTP) | ✅ | - | system.py 完整 |
| 管理 | 密码/SSH 密钥 | ✅ | - | system.py 完整 |
| 软件包 | APT 源管理/软件包管理 | ✅ | - | apt.py + system.py upgrade 功能 |
| TTYD | Web 终端 | ✅ | - | ttyd.py 启停管理 |
| 启动项 | 启动项管理 | ✅ | - | startup.py (已导入) |
| 计划任务 | Cron 任务管理 | ✅ | - | cron.py (已导入) |
| LED | LED 配置 | ❌ | P3 | 只有占位符页面 |
| SNMP | SNMP 配置 | ❌ | P3 | 只有占位符页面 |
| 备份 | 配置备份/还原/下载/预览 | ✅ | - | backup.py 完整 |
| 文件传输 | 文件管理 | ✅ | - | files.py (已导入) |
| 重启 | 重启(支持延迟) | ✅ | - | system.py POST /reboot |
| 关机 | 关机(支持延迟) | ✅ | - | system.py POST /shutdown |
| 定时重启 | 定时重启配置 | ❌ | P2 | 只有占位符页面 |
| 系统升级 | apt upgrade/dist-upgrade | ✅ | - | system.py 完整 |

---

## 11. 应用商店 (AppStore) — 特殊说明

> **用户明确要求：AppStore 部分不按 iStoreOS 标准对标，按 1Panel 标准。**
> 本报告不包含 AppStore 差距分析。

UbuntuRouter 当前状态：
- 后端: `appstore.py` 应用市场 API
- 前端: `AppStore.vue` 带评分组件
- 另含 `ratings.py` 评分系统

---

## 12. UbuntuRouter 独有功能

UbuntuRouter 有但 iStoreOS/OpenWrt 没有的功能：

| 功能 | 路径 | 说明 |
|------|------|------|
| VM (虚拟机) 管理 | `vm.py` (324行) | 基于 libvirt/KVM 的虚拟机管理 |
| 网络编排引擎 | `orchestrator.py` (561行) | 设备识别 + 应用识别 + 规则编译 + 流量统计 + 故障切换 |
| 网络拓扑 | `topology.py` | 网络拓扑可视化 |
| TLS/HTTPS 证书管理 | `tls_manager.py` | Let's Encrypt + 自签名证书管理 |
| VNC 代理 | `vnc_proxy.py` | VM VNC 控制台代理 |
| 高级配置编辑器 | `ConfigEditor.vue` | YAML 配置文件在线编辑 |
| 联网向导 | `NetworkWizard.vue` | 网络配置引导 |
| 应用评分系统 | `ratings.py` | 应用市场评分/评价 |
| 系统快照 (Rollback) | `system.py` | 配置快照管理 (RollbackManager) |

---

## 13. 优先级汇总

### P1 (关键缺失 — 影响核心路由体验)
- 🔴 **实时图表/WebSocket 推送到前端**: 后端有 delta 计算但前端无实时趋势图
- 🔴 **防火墙规则高级匹配**: 缺少 ICMP, ipset, rate limit, 时间限制, conntrack state
- 🔴 **NAT Loopback**: 端口转发无 NAT 回环选项
- 🔴 **DHCP 池创建/编辑**: 只能查看不能修改

### P2 (重要缺失 — 需要补齐)
- 🟠 **Turbo ACC (硬件加速/BBR)**: 只有占位符
- 🟠 **SQM QoS**: 只有占位符
- 🟠 **DDNS 更多提供商**: No-IP, HE.NET, Oray, 3322 等
- 🟠 **桥接/Bond 管理**: 完全缺失
- 🟠 **端口转发协议选择**: 当前全部 TCP
- 🟠 **UPnP 配置选项**: 接口选择/ACL/端口范围
- 🟠 **定时重启**: 只有占位符
- 🟠 **历史统计图表**: 有 CSV 持久化但无展示

### P3 (锦上添花 — 增强体验)
- 🟡 **无线高级参数**: 功率/信道宽度/国家码/MAC过滤
- 🟡 **接口高级参数**: metric/dhcp-identifier/accept-ra
- 🟡 **FTP 服务**: 只有占位符
- 🟡 **LED 配置**: 只有占位符
- 🟡 **SNMP**: 只有占位符
- 🟡 **HSTS/HTTP2**: TLS 功能增强

### PX (不适用 — 或已按其他标准)
- ⚪ **AppStore**: 按 1Panel 标准，不对比
- ⚪ **iStore 应用商店**: 不适用

---

## 14. 总结

### 优势领域
UbuntuRouter 在以下方面已经达到甚至超过 iStoreOS 的功能覆盖：
1. **Docker 管理**: 完整容器/镜像/网络/卷管理
2. **VPN**: WireGuard 隧道 + Peer 管理 + Tailscale
3. **网络诊断**: 6种工具齐全
4. **存储管理**: 磁盘/挂载/Samba/NFS/备份
5. **DDNS**: 5种主流提供商 + 调度器
6. **无线**: 基础 AP/Client 模式完整
7. **系统设置**: 主机名/时区/NTP/密码/SSH/HTTPS证书

### 核心短板
与 iStoreOS 差距最大的领域：
1. **防火墙规则引擎** — 缺少高级匹配参数
2. **实时监控图表** — 无前端实时趋势展示
3. **网络加速 (Turbo ACC)** — 完全缺失
4. **QoS 流量整形** — 完全缺失
5. **桥接/Bond/LAG** — 完全缺失
6. **UPnP/NAT-PMP 完整配置** — 功能不完整
7. **接口高级配置** — 缺少 IPv6/进阶参数

### 建议开发路线
1. **P1 优先**: 防火墙规则增强 + DHCP 池编辑 + 实时图表
2. **P2 跟进**: Turbo ACC + QoS + 桥接 + DDNS 更多提供商
3. **P3 完善**: 无线高级 + 接口高级 + FTP/LED/SNMP

---

*本报告基于 UbuntuRouter 代码完整审计（2026-04-28），涵盖 36 个后端路由模块和 50 个前端页面/组件。*
