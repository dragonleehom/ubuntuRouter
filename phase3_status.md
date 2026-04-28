# Phase 3 功能模块实现状态检查

检查时间: 2026-04-28
项目路径: /mnt/aiassistant/Hermes/hermes_home/workspace/ubuntu-router

## 后端 API 路由文件
路径: src/ubunturouter/api/routes/
所有路由文件已检查: appstore, containers, firewall, monitor, storage, system, 等

## 检查结果

| # | 功能 | 后端 API | 前端页面 | 后端文件 | 前端文件 |
|---|------|---------|---------|---------|---------|
| 3.1 | 应用详情弹窗 | N/A (纯前端) | ✅ 已实现 | N/A | web/src/views/appstore/AppStore.vue (含 viewDetail 方法) |
| 3.2 | 应用排序(下载量/评分/更新) | N/A (纯前端) | ❌ 未实现 | N/A | AppStore.vue 仅有标签筛选和搜索, 无排序控件 |
| 3.3 | 实时带宽监控 | ✅ | ✅ | api/routes/monitor.py (`GET /network/traffic`, `GET /realtime`) | web/src/views/monitor/SystemMonitor.vue |
| 3.4 | 防火墙连接跟踪表 | ✅ | ❌ 未找到 | api/routes/firewall.py (`GET /conntrack`, `POST /conntrack/flush`); firewall/__init__.py (ConntrackEntry, get_conntrack, flush_conntrack) | 无独立 conntrack 页面 |
| 3.5 | 分区图表/格式化 | ❌ | ❌ | disk.py 仅有 lsblk 磁盘列表, 无分区创建/格式化 API | StorageManager.vue 仅有磁盘概览 |
| 3.6 | HTTPS证书管理 | ❌ | ❌ | api/tls.py (仅自签证书生成, 无 API 路由端点) | 无证书管理页面 |
| 3.7 | HDD硬盘休眠 | ❌ | ❌ | 全项目无 hdparm/spindown 相关代码 | 无对应页面 |
| 3.8 | NFS管理 | ✅ | ⏳ 占位符 | api/routes/storage.py (`POST /mount/nfs`, `POST /mount/cifs`) | web/src/views/StorageNfsPlaceholder.vue ("NFS — 开发中") |
| 3.9 | Docker网络/卷管理 | ❌ | ❌ | container/__init__.py 仅有容器 CRUD/Compose, 无 network/volume API 端点 | ContainerManager.vue 仅管理容器和镜像 |
| 3.10 | 系统重置 | ❌ | ❌ | 全项目无 factory reset 相关代码 | 无对应页面 |
| 3.11 | 进程列表 | ✅ | ⏳ 占位符 | api/routes/monitor.py (`GET /processes`, `GET /processes/{pid}`) | web/src/views/StatusProcessPlaceholder.vue ("进程管理 — 开发中") |
| 3.12 | 带宽历史统计 | ✅ | ✅ | api/routes/monitor.py (`GET /history`, CSV 持久化收集器) | SystemMonitor.vue (图表展示历史数据) |

## 汇总

**已实现 (后端 ✅ + 前端 ✅):**
- 3.3 实时带宽监控 (完整)
- 3.12 带宽历史统计 (完整)

**仅后端实现 (后端 ✅, 前端 ❌/占位符):**
- 3.4 防火墙连接跟踪表 (后端完整, 无前端页面)
- 3.8 NFS管理 (后端完整, 前端仅占位符)
- 3.11 进程列表 (后端完整, 前端仅占位符)

**纯前端 (后端 N/A):**
- 3.1 应用详情弹窗 (已实现)
- 3.2 应用排序 (未实现)

**未实现 (后端 ❌):**
- 3.5 分区图表/格式化
- 3.6 HTTPS证书管理 (仅底层 tls.py, 无路由)
- 3.7 HDD硬盘休眠
- 3.9 Docker网络/卷管理
- 3.10 系统重置
