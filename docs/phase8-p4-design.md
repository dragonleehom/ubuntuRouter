# Phase 8 — P4 模块设计文档

## 1. 系统日志查看器

### 1.1 功能需求
- 图形化 journalctl 查看器：按服务、时间、严重级别过滤
- 实时日志流（WebSocket 或轮询流）
- 日志搜索高亮
- 日志下载/分享

### 1.2 API 端点
```
GET    /api/v1/system/logs?service=ubunturouter&lines=50&priority=6&since=1h&follow=false
       → { logs: [...], total: N, truncated: bool }
```

### 1.3 后端实现
- 复用现有的 `/api/v1/system/logs` 端点但扩展参数
- 使用 `journalctl --since` 和 `--priority` 过滤
- follow 模式使用 SSE 流式输出
- 添加到现有 `system.py` 路由

### 1.4 前端
- 增强 System.vue 或独立 LogViewer.vue
- 路由复用 `/system`（系统设置页面加日志 tab）

---

## 2. 连接跟踪 (conntrack)

### 2.1 功能需求
- 实时 conntrack 连接列表（源/目标 IP、端口、状态、协议）
- 按条件过滤（IP/端口/状态/协议）
- 手动清除连接或按条件批量清除
- 连接统计概览（总数/各状态数量）

### 2.2 API 端点
```
GET    /api/v1/system/conntrack?limit=100&offset=0&proto=tcp&state=ESTABLISHED
       → { entries: [...], total: N, stats: { total, established, time_wait, ... } }
DELETE /api/v1/system/conntrack/{ip}       # 清除某个 IP 的所有连接
DELETE /api/v1/system/conntrack            # 清除全部连接
```

### 2.3 后端实现
- 调用 `conntrack -L -o extended -n` 解析输出
- 解析后的 JSON 分页返回
- 统计信息聚合

### 2.4 前端
- ConntrackView.vue — 连接列表 + 过滤 + 批量清除
- 路由 `/conntrack`

---

## 3. SSL 证书管理

### 3.1 功能需求
- 查看已安装的 SSL 证书（路径、过期时间、签发者）
- 使用 ACME 协议自动申请 Let's Encrypt 证书
- 证书续签（手动触发 + 自动 cron）
- 支持通配符证书和 DNS-01 验证

### 3.2 API 端点
```
GET    /api/v1/system/certificates              # 列出已安装的证书
POST   /api/v1/system/certificates              # 导入证书（上传 PEM）
POST   /api/v1/system/certificates/acme         # 通过 ACME 申请证书
POST   /api/v1/system/certificates/{name}/renew # 续签证书
DELETE /api/v1/system/certificates/{name}       # 删除证书
```

### 3.3 后端实现
- 扫描常见路径：`/etc/ssl/certs/`, `/etc/letsencrypt/live/`
- ACME 使用 certbot 封装或纯 Python acme 库
- 自动续签 cron

### 3.4 前端
- CertificateManager.vue — 证书列表 + 申请/导入/续签
- 路由 `/certificates`

---

## 4. 告警/通知系统

### 4.1 功能需求
- 系统事件告警（CPU 过载、内存不足、磁盘满、服务宕机）
- 通知渠道：Web UI 通知中心、Telegram 集成
- 告警规则配置（阈值、间隔、启用/禁用）
- 告警历史查看

### 4.2 API 端点
```
GET    /api/v1/system/alerts/rules              # 告警规则列表
POST   /api/v1/system/alerts/rules              # 创建告警规则
PUT    /api/v1/system/alerts/rules/{id}         # 更新规则
DELETE /api/v1/system/alerts/rules/{id}         # 删除规则
GET    /api/v1/system/alerts/history            # 告警历史
POST   /api/v1/system/alerts/ack/{id}           # 确认告警
```

### 4.3 后端实现
- 后台线程定期检查阈值
- 告警规则持久化到 YAML
- 通知写入数据库或内存队列
- 前端轮询获取未读告警

### 4.4 前端
- AlertRules.vue — 规则管理页面
- AlertHistory.vue — 告警历史
- 全局告警图标（顶部栏）
- 路由 `/alerts`

---

## 5. 侧边栏和路由注册

新增路由：
```
/system      → System.vue（原有）+ 日志 tab 增强
/conntrack   → ConntrackView.vue
/certificates → CertificateManager.vue
/alerts      → AlertRules.vue + AlertHistory.vue（子路由）
```
