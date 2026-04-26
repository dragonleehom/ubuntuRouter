# P1 模块迭代计划 — 系统监控增强 + Samba 共享管理

> 日期: 2026-04-26 | 优先级: P1

## 1. 系统监控增强

**需求场景：** 相比 iStoreOS 缺失实时图表、温度传感器、系统负载趋势。

**模块结构：**
```
api/routes/monitor.py   # 监控 API
web/src/views/monitor/   # 监控前端
```

**API 端点 (`/api/v1/monitor/`):**
- `GET /realtime` — CPU/内存/磁盘/网络/温度实时数据（单次快照）
- `GET /history?metric=cpu&range=1h` — 历史趋势数据（从本地时序文件读取）
- `GET /sensors` — 硬件传感器（lm-sensors / thermal_zone）
- `GET /processes` — 进程列表（CPU/内存排序，top 采样）
- `GET /processes/{pid}` — 进程详情

**数据采集方式：**
- `/proc/stat` → CPU 使用率
- `/proc/meminfo` → 内存
- `/proc/net/dev` → 网口流量
- `/sys/class/thermal/thermal_zone*/temp` → CPU 温度
- `sensors -j` → 完整传感器（lm-sensors 可选）
- `ps aux --sort=-%cpu` → 进程
- 历史数据：每 60s 追加到 `/opt/ubunturouter/data/monitor/` 目录下的 CSV 文件，保留 24h

**前端：**
- 新增导航"系统监控"
- CPU/内存/磁盘/网络 4 个实时折线图（ECharts）
- 传感器卡片
- 进程列表页

## 2. Samba 共享管理

**需求场景：** 路由器的 NAS 功能，管理 Samba/CIFS 共享。

**模块结构：**
```
storage/
├── samba/               # 新建
│   ├── __init__.py      # SambaManager
api/routes/samba.py      # REST API
```

**API 端点 (`/api/v1/samba/`):**
- `GET /status` — Samba 服务状态 + 配置概览
- `POST /start` / `POST /stop` / `POST /restart` — 服务控制
- `GET /shares` — 列出共享目录
- `POST /shares` — 创建共享
- `PUT /shares/{name}` — 修改共享配置
- `DELETE /shares/{name}` — 删除共享
- `GET /users` — Samba 用户列表
- `POST /users` — 添加 Samba 用户（`smbpasswd -a`）
- `DELETE /users/{username}` — 删除 Samba 用户

**后端实现：**
- 读取/写入 `/etc/samba/smb.conf`
- `testparm` 验证配置语法
- `systemctl` 控制 smbd/nmbd 服务
- `smbpasswd` 管理密码
- `smbstatus` 查看当前连接

## 实施顺序
1. 系统监控增强（后端采集 + API + 前端实时图表）
2. Samba 共享管理（后端 + API + 前端）
