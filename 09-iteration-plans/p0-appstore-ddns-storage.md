# P0 模块迭代计划 — 应用商店兼容 1Panel + DDNS + 存储管理

> 日期: 2026-04-26 | 基于之前深度分析 | 优先级: P0

## 1. 应用商店 — 兼容 1Panel AppStore

**现状：** 自建 `ubuntu-router/apps-official` 仓库不存在。1Panel 已有 249 个 Docker 应用（https://github.com/1Panel-dev/appstore），标准化 data.yml + docker-compose.yml。

**改造方案：**
- 后端新增 `1panel` repo 源（git clone 1Panel-dev/appstore）
- 编写适配器将 data.yml → AppManifest 格式
- 按 1Panel 分类（database/tool/runtime/middleware/storage/network）组织
- 直接使用 1Panel 的 docker-compose.yml 部署
- 可选项：手动添加自建仓库、自定义源

## 2. DDNS 动态域名解析（全新模块）

**需求场景：** 路由器的核心功能，支持主流 DDNS 服务商。
- HTTP 接口：更新 IP 记录（支持 IPv4/IPv6）
- 定时任务：周期性检查 IP 变化并更新
- 服务商支持：DDNSTO / AliDNS / Cloudflare / DNSPod / HE.net / DuckDNS

**模块结构：**
```
ddns/
├── __init__.py    # DDNSManager 统一入口
├── providers/
│   ├── base.py    # 基础 Provider 接口
│   ├── ddnsto.py  # DDNSTO 客户端
│   ├── alidns.py  # 阿里云 DNS
│   ├── cloudflare.py
│   ├── dnspod.py
│   ├── duckdns.py
│   └── henet.py   # Hurricane Electric
├── scheduler.py   # cron 定时任务
api/routes/ddns.py # REST API
```

## 3. 存储管理（全新模块）

**需求场景：** 查看磁盘信息、S.M.A.R.T 状态、文件系统挂载。

**模块结构：**
```
storage/
├── __init__.py   # StorageManager
├── disk.py       # 磁盘发现 + 分区信息
├── smart.py      # S.M.A.R.T 状态
├── mount.py      # 挂载管理
api/routes/storage.py  # REST API
```

## 实施顺序
1. 应用商店 1Panel 兼容（重构引擎 + 适配器 + 前端微调）
2. DDNS 模块（完整的 API + 前端页面）
3. 存储管理（API + 前端页面）

预计工期：每个模块约 2-4 小时编码 + 1 小时测试验证。
