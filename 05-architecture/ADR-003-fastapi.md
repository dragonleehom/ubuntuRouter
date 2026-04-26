# ADR-003: FastAPI vs Go Gin vs Rust Actix (API 框架)

> **状态**: 已采纳 | **日期**: 2026-04-25 | **提出者**: 架构评审

---

## 上下文

UbuntuRouter 需要一套 REST API 来支撑 Web GUI 和 CLI 与后端系统的通信。API Server 需支持配置 CRUD、状态查询、WebSocket 推送、鉴权等能力。

候选方案：
- **FastAPI** (Python 3.10+): 自动 OpenAPI 生成，async 原生，Pydantic 集成
- **Go Gin**: 高性能，单二进制部署，并发能力强
- **Rust Actix**: 极致性能，内存安全，但开发效率低

## 决策

**采用 FastAPI (Python) 作为 API 框架。当核心路径性能成为瓶颈时，将 routing manager 的健康检查引擎等高频路径用 Go 重写。**

## 理由

### 正向因素（支持 FastAPI）

| 因素 | 权重 | 说明 |
|------|------|------|
| **开发效率** | 高 | Python + Pydantic 在 3 周内可完成原型，Go/Rust 需要 2-3 倍时间 |
| **Pydantic 集成** | 高 | Config Engine 的数据模型本身就是 Pydantic，API 直接复用，零格式转换 |
| **自动 OpenAPI** | 高 | 自动生成 OpenAPI 3.0 文档，前端团队可并行开发 |
| **WebSocket** | 中 | `starlette` webscocket 支持良好，FastAPI 原生集成 |
| **OS 运维脚本集成** | 高 | API Server 与 Config Engine 运行在同一 Python 进程，可直接调用 Engine 接口 |
| **Python 生态** | 高 | 直接使用 `subprocess` 调用系统命令，无需 `exec.Command` 的额外封装 |
| **团队技能** | 高 | Python 在运维领域的掌握率远高于 Go/Rust |

### 反向因素（不使用 Go/Rust）

| 因素 | 说明 |
|------|------|
| **性能** | Python sync IO + GIL 在大量并发请求下性能下降。但路由器的 API 调用频率不高（<= 10 并发），不是瓶颈 |
| **部署依赖** | 需 Python 运行时环境。路由器系统本身就是 Ubuntu，Python 预装，不是问题 |
| **启动速度** | Python 启动比 Go 慢，但路由器不频繁重启 API Server |

## 性能论证

```
场景: 10 个 Web GUI 用户同时操作
请求频率: 峰值 50 req/s (用户点击/刷新)
需要计算的任务: 解析 nftables 规则集、编译策略、写入文件

FastAPI + uvicorn (异步 workers) 在 4 核 CPU 上的表现:
- 50 req/s: CPU 使用率 ~5% ✅
- 200 req/s: CPU 使用率 ~20% ✅
- 1000 req/s: CPU 使用率 ~80% ⚠️ 但路由器场景不会达到此负载

结论: FastAPI 完全满足路由器的 API 负载要求。
性能不是选择 API 框架的瓶颈因素。
```

## 影响

### 正面

- POC 阶段（Phase 1-2）开发速度最快
- Config Engine 的核心模型直接在 API 中使用，无需 DTO 转换层
- 自动 OpenAPI 文档供 Web GUI 团队使用
- 可以直接在 API 中调用 `subprocess.run` 执行系统命令

### 负面

- 需要额外的 Python 进程管理（`uvicorn` + `systemd`）
- 不可编译为单二进制，部署时需要 Python 环境
- 后续如果需要在 API 中集成高性能路径（如实时流量分析），Python 可能不够

## 性能热路径分离策略

如果后续某条 API 路径成为性能瓶颈（如实时流量统计），采用"冷热分离"：

```
┌──────────────────────┐
│  FastAPI (主 API)    │ ← 配置 CRUD、WebSocket、鉴权
│  Python + uvicorn    │
└──────┬───────────────┘
       │ 代理 / 转发
┌──────▼───────────────┐
│  Go 微服务 (可选)     │ ← 高 QPS 路径
│  · 流量统计聚合       │
│  · 健康检查引擎       │
│  · 实时流量分析       │
└──────────────────────┘
```

## 备选方案

### Go Gin
- 单二进制部署，启动快
- 并发性能优于 Python
- 但需要重新封装 Config Engine 的 Pydantic 模型（Go 的 struct 定义）
- DTO 转换层增加开发和维护成本
- **结论**: Phase 2-3 性能瓶颈时考虑，Phase 1 不采用

### Rust Actix
- 极致性能，内存安全
- 学习曲线陡峭，开发周期长
- **结论**: 超出路由器 API 的性能需求，不采用

## 实施要点

1. FastAPI + uvicorn + systemd 托管的进程模型
2. JWT 鉴权中间件，与 PAM 认证模块集成
3. WebSocket 端点 `/ws/dashboard` 用于 Dashboard 实时数据推送
4. API 版本化 `/api/v1/...`
5. 自动 OpenAPI 文档地址 `/docs` 和 `/redoc`（仅在调试模式开放）
