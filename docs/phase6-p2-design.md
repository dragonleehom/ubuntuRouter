# Phase 6 — P2 模块设计文档

## 1. PPPoE 拨号管理

### 1.1 功能需求
- 查看 PPPoE 连接状态（ppp0 接口统计、IP、uptime、流量）
- 配置 PPPoE 拨号参数（用户名、密码、MTU、自动重连）
- 连接控制（拨号 / 断线 / 重连）
- 持久化配置到 `/etc/ubunturouter/pppoe.yaml`
- 基于 `pon`/`poff` 和 `/etc/ppp/peers/` 配置

### 1.2 API 端点
```
GET    /api/v1/pppoe/status        # 连接状态 + 接口统计
POST   /api/v1/pppoe/connect       # 拨号连接
POST   /api/v1/pppoe/disconnect    # 断开连接
POST   /api/v1/pppoe/reconnect     # 重新拨号
GET    /api/v1/pppoe/config        # 获取拨号配置
PUT    /api/v1/pppoe/config        # 更新拨号配置（用户名/密码/MTU/自动重连）
```

### 1.3 后端模块
- `app/pppoe/__init__.py` — PPPoEManager 主类
- `app/pppoe/config.py` — 配置读写（YAML + `/etc/ppp/peers/` 模板）
- 实现方式：`pon <provider>` / `poff <provider>` / `plog` 查看日志
- 状态检测：`ip addr show ppp0` + `/proc/net/dev` 获取流量

### 1.4 前端页面
- PPPoEConnection.vue — 状态卡片 + 连接控制按钮
- PPPoEConfig.vue — 配置表单（用户名/密码/MTU/自动重连）
- 作为路由 `/pppoe` 注册，侧边栏显示

---

## 2. TTYD 终端集成

### 2.1 功能需求
- 在 Web 界面内嵌终端（基于 ttyd）
- 通过 `/api/v1/ttyd` 获取 ttyd 地址和连接参数
- 前端 iframe 嵌入或独立窗口打开
- ttyd 作为独立 systemd 服务（`ubunturouter-ttyd`）

### 2.2 API 端点
```
GET    /api/v1/ttyd/info          # 获取 ttyd 连接信息（URL、端口、是否运行）
POST   /api/v1/ttyd/start         # 启动 ttyd 服务
POST   /api/v1/ttyd/stop          # 停止 ttyd 服务
```

### 2.3 后端实现
- 检测系统是否安装 ttyd，未安装提示安装命令
- ttyd 运行在 7681 端口，绑定 127.0.0.1 确保安全
- 通过代理或直接 URL 暴露到前端

### 2.4 前端页面
- WebTerminal.vue — 内嵌终端（iframe + 状态检测）
- 路由 `/terminal`

---

## 3. APT 软件源管理

### 3.1 功能需求
- 查看当前 APT 源列表
- 添加/删除源（检测 Ubuntu 版本自动选择合适源）
- 手动 `apt update`
- 源备份和恢复
- 支持国内镜像源（清华/阿里/中科大/华为）切换

### 3.2 API 端点
```
GET    /api/v1/apt/sources         # 列出所有源
POST   /api/v1/apt/sources         # 添加源
DELETE /api/v1/apt/sources         # 删除源
PUT    /api/v1/apt/sources/mirror   # 切换镜像源
POST   /api/v1/apt/update          # apt update
GET    /api/v1/apt/status          # 源状态（数量、最后更新时间）
```

### 3.3 后端模块
- `app/apt/__init__.py` — APTManager 主类
- 操作 `/etc/apt/sources.list` 和 `/etc/apt/sources.list.d/`
- 预置镜像源映射表（ubuntu 版本检测自动匹配）

### 3.4 前端页面
- AptSources.vue — 源列表 + 添加/删除 + 镜像切换 + apt update 按钮
- 路由 `/apt`

---

## 4. 侧边栏和路由注册

在 router/index.js 增加：
```
/pppoe     → PPPoE 拨号
/terminal  → Web 终端
/apt       → 软件源管理
```

在 MainLayout.vue 侧边栏增加对应菜单项。
