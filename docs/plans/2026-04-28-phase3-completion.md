# Phase 3 (P3 增强) 完成计划

> **目标**: 完成 Phase 3 全部 12 项任务，补齐剩余功能
>
> **当前状态**: 4 项已完成(3.1, 3.3, 3.5, 3.12)，3 项部分完成(3.4, 3.6, 3.8, 3.11)，5 项未开始(3.2, 3.7, 3.9, 3.10)
>
> **Phase 3 总工作量估算**: ~9 人天

---

## Sprint 1: 快赢项 — 纯前端 + 后端已就绪补充（3项）

### Task 1.1: 应用排序（3.2） — 纯前端，0.5d

**目标**: 在 AppStore.vue 中添加排序控件（按下载量/评分/更新时间），替换当前仅按字母排序

**涉及文件**:
- 修改: `web/src/views/appstore/AppStore.vue`

**实现方案**:
- 在分类 Tab 下方增加排序下拉框
- 排序选项: 默认(字母), 最近更新, 热门下载, 评分
- 后端 `/api/v1/appstore/apps` 已返回完整列表，前端排序即可

### Task 1.2: Conntrack 前端页面（3.4 补充） — 纯前端，0.5d

**目标**: 防火墙页面新增「连接跟踪」子标签页，展示 conntrack 表和提供刷新按钮

**涉及文件**:
- 修改: `web/src/views/firewall/FirewallRules.vue` (或新建子组件)

**后端已就绪**: `GET /api/v1/firewall/conntrack`, `POST /api/v1/firewall/conntrack/flush`

### Task 1.3: 进程列表前端页面（3.11 补充） — 纯前端，0.5d

**目标**: 系统监控页面增加「进程列表」子标签页，展示进程详情的表格

**涉及文件**:
- 修改: `web/src/views/monitor/SystemMonitor.vue`
- 删除或替换: `web/src/views/StatusProcessPlaceholder.vue` (占位符)

**后端已就绪**: `GET /api/v1/monitor/processes`, `GET /api/v1/monitor/processes/{pid}`

---

## Sprint 2: 中等复杂度（2项）

### Task 2.1: NFS 管理完善（3.8） — 后端+前端，1d

**目标**: 补充 NFS 导出/挂载管理 API 和完整前端页面

**涉及文件**:
- 新建: `src/ubunturouter/api/routes/nfs.py`
- 修改: `src/ubunturouter/api/main.py` (注册路由)
- 修改/新建: `web/src/views/StorageNfsPlaceholder.vue` → `web/src/views/nfs/NfsManager.vue`

**后端端点**:
```
GET    /api/v1/nfs/exports        # NFS 导出列表
POST   /api/v1/nfs/exports        # 添加 NFS 导出
DELETE /api/v1/nfs/exports/{name} # 删除 NFS 导出
GET    /api/v1/nfs/status         # NFS 服务状态
POST   /api/v1/nfs/restart        # 重启 NFS 服务
```

### Task 2.2: HTTPS 证书管理（3.6） — 后端+前端，1.5d

**目标**: 将现有 `api/tls.py` 底层模块暴露为 API 路由，添加前端证书管理页面（上传/查看/续签）

**涉及文件**:
- 新建: `src/ubunturouter/api/routes/tls_manager.py`
- 修改: `src/ubunturouter/api/main.py` (注册路由)
- 新建: `web/src/views/tls/TlsManager.vue`

**后端端点**:
```
GET    /api/v1/tls/status          # 证书状态（存在/过期时间/CN）
POST   /api/v1/tls/renew           # 重新生成自签证书
POST   /api/v1/tls/upload          # 上传自定义证书（cert + key）
POST   /api/v1/tls/toggle-https    # 切换 HTTPS 启用/禁用（需重启）
```

---

## Sprint 3: 重头戏（3项）

### Task 3.1: Docker 网络/卷管理（3.9） — 后端+前端，1d

**目标**: 容器管理页面新增「网络」和「卷」子标签页，独立管理 Docker 网络和卷资源

**涉及文件**:
- 修改: `src/ubunturouter/api/routes/containers.py` (新增端点)
- 新建: `web/src/views/containers/DockerNetworks.vue`
- 新建: `web/src/views/containers/DockerVolumes.vue`
- 修改: `web/src/views/containers/ContainerManager.vue` (增加 Tab)

**后端端点** (添加到 containers.py):
```
GET    /api/v1/docker/networks          # 网络列表
POST   /api/v1/docker/networks          # 创建网络
DELETE /api/v1/docker/networks/{name}   # 删除网络
GET    /api/v1/docker/volumes           # 卷列表
POST   /api/v1/docker/volumes           # 创建卷
DELETE /api/v1/docker/volumes/{name}    # 删除卷
```

### Task 3.2: 系统重置（3.10） — 后端，0.5d

**目标**: 提供安全恢复出厂设置功能（清除配置、重置网络）

**涉及文件**:
- 新建: `src/ubunturouter/api/routes/factory_reset.py`
- 修改: `src/ubunturouter/api/main.py` (注册路由)

**后端端点**:
```
POST   /api/v1/system/factory-reset     # 恢复出厂设置（需二次确认 token）
```

### Task 3.3: HDD 硬盘休眠（3.7） — 后端，0.5d

**目标**: 提供硬盘休眠管理功能（查看/设置 APM 级别、休眠超时）

**涉及文件**:
- 修改: `src/ubunturouter/api/routes/storage.py` (新增端点)

**后端端点** (添加到 storage.py):
```
GET    /api/v1/storage/disks/{dev}/apm      # 查看 APM/休眠状态
POST   /api/v1/storage/disks/{dev}/apm      # 设置 APM 级别/休眠超时
```

---

## 执行顺序

```
Sprint 1 (最快见效):
  Task 1.1 → Task 1.2 → Task 1.3  (全部纯前端，可并行或顺序)

Sprint 2 (功能补齐):
  Task 2.1 (NFS) → Task 2.2 (TLS)

Sprint 3 (完整功能):
  Task 3.1 (Docker网络/卷) → Task 3.2 (系统重置) → Task 3.3 (HDD休眠)
```

验证方式:
1. 每个 Task 完成后，本地 `git add && git commit`
2. 推送后 SSH 到 VM 部署验证
3. 前端页面无控制台报错，表单提交正常
4. 不破坏已有功能
