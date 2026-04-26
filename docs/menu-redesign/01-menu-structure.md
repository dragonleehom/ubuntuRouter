# UbuntuRouter — 菜单结构重构文档

## 设计目标

1. **匹配 iStoreOS 层级范式**：采用一级侧栏 + 二级展开/折叠的子菜单结构
2. **合理合并冗余项**：从 iStoreOS 的 70+ 项压缩至 ~60 项，保留核心功能
3. **适配 UbuntuRouter 特性**：
   - Tailscale 并入 VPN 设置（作为子选项）
   - WiFi/Wireless 纳入网络配置模块
   - 应用商店/已安装应用保持独立

---

## 一级模块结构（主侧栏，共 8 个模块）

```
┌─────────────────────────────────┐
│  📊 仪表盘       (Dashboard)    │
│  🌐 路由状态     (Status)       │
│  🔧 网络配置     (Network)      │
│  📡 远程服务     (Remote Svc)   │
│  💾 存储管理     (Storage)      │
│  📦 应用管理     (Apps)         │
│  ⚙️ 系统设置     (System)       │
│  🔽 重启关机     (Power)        │
└─────────────────────────────────┘
```

---

## 完整菜单层级定义（60 项）

### 1. 仪表盘 (Dashboard)
| 路径 | 路由 path | 页面说明 | 来源 |
|---|---|---|---|
| /dashboard | `/dashboard` | 全局概览 / 信息面板 | 现有「仪表盘」|

**说明**：独立首页，不折叠。显示系统运行状态摘要、CPU/内存/网络概览。

---

### 2. 路由状态 (Status) — 8 项
| 路径 | 路由 path | 页面说明 | 来源 |
|---|---|---|---|
| 路由状态 > 概览 | `/status/overview` | 路由运行状态总览 | 现有「路由状态」改名 |
| 路由状态 > 接口总览 | `/status/interfaces` | 所有网络接口状态 | 现有「接口总览」移入 |
| 路由状态 > 路由表 | `/status/routes` | 内核路由表 / 策略路由 | 新增（对应 LuCI Status > Routes） |
| 路由状态 > 防火墙状态 | `/status/firewall` | 防火墙规则概览 | 新增（对应 LuCI Status > Firewall） |
| 路由状态 > 实时流量 | `/status/realtime` | 实时带宽/流量图表 | 现有「实时流量」移入 |
| 路由状态 > 流量监控 | `/status/traffic` | 历史流量统计 | 现有「流量监控」移入 |
| 路由状态 > 系统日志 | `/status/syslog` | 系统日志查看 | 现有「日志查看」移入 |
| 路由状态 > 进程管理 | `/status/processes` | 运行进程列表 | 新增 |

---

### 3. 网络配置 (Network) — 12 项
| 路径 | 路由 path | 页面说明 | 来源 |
|---|---|---|---|
| 网络配置 > 接口 | `/network/interfaces` | 物理/虚拟接口管理 | 现有「网络配置」改名 |
| 网络配置 > WiFi | `/network/wireless` | 无线网络配置 | 新增（iStoreOS 纳入无线）|
| 网络配置 > DHCP 服务器 | `/network/dhcp` | DHCP 服务设置 | 现有「DHCP设置」移入 |
| 网络配置 > 主机名映射 | `/network/hostnames` | 静态 DHCP 主机名 | 新增 |
| 网络配置 > DNS 设置 | `/network/dns` | DNS 服务器/转发配置 | 现有「DNS设置」移入 |
| 网络配置 > 静态路由 | `/network/static-routes` | IPv4/IPv6 静态路由 | 新增 |
| 网络配置 > 防火墙规则 | `/network/firewall` | 防火墙规则配置 | 现有「防火墙规则」移入 |
| 网络配置 > 端口转发 | `/network/port-forward` | NAT 端口转发规则 | 现有「端口转发」移入 |
| 网络配置 > SQM QoS | `/network/qos` | 智能队列管理/限速 | 新增 |
| 网络配置 > Turbo ACC | `/network/turbo-acc` | 网络加速/卸载配置 | 新增 |
| 网络配置 > 网络诊断 | `/network/diagnostics` | Ping/Traceroute/DNS 查询 | 新增 |
| 网络配置 > UPnP | `/network/upnp` | UPnP 端口映射 | 新增 |

**注意**：PPPoE 拨号和多线路融合进「接口」页面内，不独立成菜单项。

---

### 4. 远程服务 (Remote Services) — 7 项
| 路径 | 路由 path | 页面说明 | 来源 |
|---|---|---|---|
| 远程服务 > 动态域名 | `/remote/ddns` | DDNS 配置（多服务商） | 现有「动态域名」移入 |
| 远程服务 > VPN 设置 | `/remote/vpn` | VPN 总览（WireGuard/OpenVPN/IPSec） | 现有「VPN设置」移入 |
| 远程服务 > VPN > Tailscale | `/remote/vpn/tailscale` | Tailscale 配置（子页面） | 新拆分子页 |
| 远程服务 > FRP 客户端 | `/remote/frp-client` | FRP 内网穿透客户端 | 新增 |
| 远程服务 > FRP 服务端 | `/remote/frp-server` | FRP 内网穿透服务端 | 新增 |
| 远程服务 > Socat | `/remote/socat` | Socat 端口转发工具 | 新增 |
| 远程服务 > WebDAV | `/remote/webdav` | WebDAV 远程访问 | 新增 |

**说明**：Tailscale 作为 VPN 的子项，与 WireGuard、OpenVPN 同级。

---

### 5. 存储管理 (Storage) — 7 项
| 路径 | 路由 path | 页面说明 | 来源 |
|---|---|---|---|
| 存储管理 > 磁盘概览 | `/storage/overview` | 磁盘/分区/挂载总览 | 现有「存储管理」改名 |
| 存储管理 > 文件管理 | `/storage/files` | NAS 文件浏览器 | 现有「NAS文件」移入 |
| 存储管理 > Samba | `/storage/samba` | SMB/CIFS 共享配置 | 现有「Samba共享」移入 |
| 存储管理 > FTP | `/storage/ftp` | FTP 服务器配置 | 新增 |
| 存储管理 > NFS | `/storage/nfs` | NFS 导出配置 | 新增 |
| 存储管理 > 磁盘管理 | `/storage/disks` | 分区/格式化/挂载操作 | 新增 |
| 存储管理 > 备份还原 | `/storage/backup` | 系统配置备份/还原 | 现有「备份恢复」移入 |

---

### 6. 应用管理 (Apps) — 7 项
| 路径 | 路由 path | 页面说明 | 来源 |
|---|---|---|---|
| 应用管理 > 应用市场 | `/apps/market` | 应用商店（安装/卸载） | 现有「应用市场」移入 |
| 应用管理 > 已安装应用 | `/apps/installed` | 安装的应用列表 | 现有「应用列表」移入 |
| 应用管理 > Docker 概览 | `/apps/docker` | Docker 引擎总览 | 现有「容器管理」改名 |
| 应用管理 > Docker > 容器 | `/apps/docker/containers` | 容器列表/管理 | 新拆分子页 |
| 应用管理 > Docker > 镜像 | `/apps/docker/images` | 镜像管理 | 新拆分子页 |
| 应用管理 > Docker > 网络 | `/apps/docker/networks` | Docker 网络配置 | 新拆分子页 |
| 应用管理 > Docker > 存储卷 | `/apps/docker/volumes` | 数据卷管理 | 新拆分子页 |

**说明**：Docker 作为应用管理下的可展开子模块。应用市场与已安装应用保持独立入口，不合并。

---

### 7. 系统设置 (System) — 12 项
| 路径 | 路由 path | 页面说明 | 来源 |
|---|---|---|---|
| 系统设置 > 系统 | `/system/settings` | 主机名/时区/语言等 | 现有「系统设置」改名 |
| 系统设置 > 用户管理 | `/system/users` | 本地用户/密码管理 | 现有「用户管理」移入 |
| 系统设置 > SSH 密钥 | `/system/ssh-keys` | SSH 公钥授权管理 | 新增 |
| 系统设置 > 软件包 | `/system/software` | opkg/apt 软件包管理 | 现有「软件源」改造 |
| 系统设置 > 启动项 | `/system/startup` | 开机自启服务管理 | 新增 |
| 系统设置 > 定时任务 | `/system/scheduled-tasks` | Cron 定时任务编辑 | 新增 |
| 系统设置 > LED 配置 | `/system/led` | 状态指示灯配置 | 新增 |
| 系统设置 > SNMP | `/system/snmp` | SNMP 代理配置 | 新增 |
| 系统设置 > TTYD 终端 | `/system/ttyd` | Web 终端 | 现有「Web终端」移入 |
| 系统设置 > 设备管理 | `/system/devices` | 设备/硬件清单 | 现有「系统监控」改造 |
| 系统设置 > 配置编辑 | `/system/config` | 配置文件编辑 | 现有「配置编辑」移入 |
| 系统设置 > 定时重启 | `/system/timed-reboot` | 定时重启计划 | 新增 |

---

### 8. 重启关机 (Power) — 2 项
| 路径 | 路由 path | 页面说明 | 来源 |
|---|---|---|---|
| 重启关机 > 重启 | `/power/reboot` | 系统重启 | 现有「重启关机」拆解 |
| 重启关机 > 关机 | `/power/shutdown` | 系统关机 | 现有「重启关机」拆解 |

**说明**：独立底部模块，显示为最小化卡片，不展开子菜单。

---

## 路由映射对照表

| 旧路径 | 新路径 | 操作 |
|---|---|---|
| `/dashboard` | `/dashboard` | ✅ 保留 |
| `/interfaces` | `/status/interfaces` | 🔄 迁移 |
| `/firewall` | `/network/firewall` | 🔄 迁移 |
| `/dhcp` | `/network/dhcp` | 🔄 迁移 |
| `/routing` | `/status/routes` | 🔄 迁移 |
| `/vpn` | `/remote/vpn` | 🔄 迁移（拆分子页）|
| `/multiwan` | `/network/interfaces` (合并进接口) | 🔄 合并 |
| `/containers` | `/apps/docker` | 🔄 迁移（拆分子页）|
| `/appstore` | `/apps/market` | 🔄 迁移 |
| `/ddns` | `/remote/ddns` | 🔄 迁移 |
| `/storage` | `/storage/overview` | 🔄 迁移 |
| `/monitor` | `/system/devices` (设备管理) | 🔄 改造 |
| `/samba` | `/storage/samba` | 🔄 迁移 |
| `/pppoe` | `/network/interfaces` (合并进接口) | 🔄 合并 |
| `/terminal` | `/system/ttyd` | 🔄 迁移 |
| `/apt` | `/system/software` | 🔄 改造 |
| `/dns` | `/network/dns` | 🔄 迁移 |
| `/diag` | `/network/diagnostics` | 🔄 迁移 |
| `/backup` | `/storage/backup` | 🔄 迁移 |
| `/config` | `/system/config` | 🔄 迁移 |
| `/orchestrator` | `/network/interfaces` (流量编排功能) | 🔄 合并 |
| `/vm` | `/apps/docker` (虚拟化管理) | 🔄 合并 |
| `/system` | `/system/settings` | 🔄 改名 |
