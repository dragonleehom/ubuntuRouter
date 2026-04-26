# Phase 7 — P3 模块设计文档

## 1. DNS 管理增强（分流/转发/重写）

### 1.1 功能需求
当前 DHCP/DNS 页面只做了基础配置。需要增强 DNS 独立管理：
- DNS 转发规则管理（域名 → 特定 DNS 服务器）
- DNS 重写/劫持规则（特定域名返回指定 IP）
- DNS 查询日志实时查看
- DNS 缓存状态和刷新

### 1.2 API 端点
```
GET    /api/v1/dns/status              # DNS 服务状态（dnsmasq 运行/端口/缓存数）
GET    /api/v1/dns/forwards            # 转发规则列表
POST   /api/v1/dns/forwards            # 添加转发规则（域名/IP → 目标 DNS）
DELETE /api/v1/dns/forwards/{id}       # 删除转发规则
GET    /api/v1/dns/rewrites            # 重写规则列表
POST   /api/v1/dns/rewrites            # 添加重写规则（域名 → IP）
DELETE /api/v1/dns/rewrites/{id}       # 删除重写规则
POST   /api/v1/dns/flush-cache         # 刷新 DNS 缓存
GET    /api/v1/dns/logs?lines=50       # DNS 查询日志
GET    /api/v1/dns/hosts               # /etc/hosts 解析列表
```

### 1.3 后端实现
- 调用 `killall -HUP dnsmasq` 刷新缓存
- 读取 `/var/log/dnsmasq.log` 作为查询日志
- 操作 `/etc/dnsmasq.d/` 下的配置文件
- `/etc/hosts` 读写

### 1.4 前端
- DnsConfig.vue（增强版）— 在路由 `/dns` 下，替代现有的简版

---

## 2. 网络诊断工具

### 2.1 功能需求
- 内嵌网络诊断工具：Ping / Traceroute / DNS 查询 / MTR / TCP 端口检测
- 异步执行 + 实时输出流式显示（WebSocket 或轮询）
- 结果可复制

### 2.2 API 端点
```
POST   /api/v1/diag/ping               # 执行 ping（目标/IP/次数/超时）
POST   /api/v1/diag/traceroute         # 执行 traceroute
POST   /api/v1/diag/nslookup           # DNS 查询
POST   /api/v1/diag/mtr                # 执行 mtr
POST   /api/v1/diag/tcpcheck           # TCP 端口检测
GET    /api/v1/diag/result/{id}        # 获取执行结果
GET    /api/v1/diag/result/{id}/stream # 流式获取正在执行的输出
```

### 2.3 后端实现
- 后台 subprocess 执行 + 临时文件记录输出
- 任务 ID 跟踪，可查询进度
- 超时控制（默认 30s）

### 2.4 前端
- NetworkDiag.vue — 诊断工具面板，路由 `/diag`

---

## 3. 配置备份/恢复

### 3.1 功能需求
- 导出全部配置为 tar.gz 压缩包
- 从压缩包恢复全部配置（带预览）
- 列出历史备份
- 自动备份（每次配置变更时）

### 3.2 API 端点
```
POST   /api/v1/system/backup            # 创建备份（返回下载 URL）
GET    /api/v1/system/backups           # 备份列表（时间/大小/说明）
POST   /api/v1/system/restore           # 上传备份文件恢复
DELETE /api/v1/system/backups/{id}      # 删除备份
GET    /api/v1/system/backups/{id}/download  # 下载备份文件
POST   /api/v1/system/backup/settings   # 配置自动备份设置
```

### 3.3 后端实现
- 收集 `/etc/ubunturouter/`, `/etc/dnsmasq.d/`, `/etc/nftables.d/` 等配置
- tar.gz 打包下载
- 恢复时先备份当前状态再覆盖

### 3.4 前端
- SystemBackup.vue — 备份管理页面，路由 `/backup`

---

## 4. 侧边栏和路由注册

新增路由：
```
/dns         → DnsConfig.vue（替换原 dhcp 页面中的 DNS 部分）
/diag        → NetworkDiag.vue
/backup      → SystemBackup.vue
```
