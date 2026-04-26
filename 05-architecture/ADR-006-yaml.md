# ADR-006: YAML vs TOML vs JSON (配置格式)

> **状态**: 已采纳 | **日期**: 2026-04-25 | **提出者**: 架构评审

---

## 上下文

UbuntuRouter 的核心配置文件和 App Store 应用模板需要一种序列化格式。候选方案：

- **YAML**: 人类可读性最佳，使用缩进，支持注释，netplan/FRR/K8s 等大量使用
- **TOML**: 类 INI 格式，明确结构，常用于 Rust/Cargo 等工具
- **JSON**: 最通用，机器解析最快，但没有注释

## 决策

**主配置使用 YAML。App Store 使用 YAML。内部 API 数据交换使用 JSON。**

## 理由

### 正向因素（支持 YAML）

| 因素 | 权重 | 说明 |
|------|------|------|
| **netplan 兼容** | 高 | netplan 本身使用 YAML，Config Engine 生成的 netplan 配置也是 YAML，统一格式减少转换 |
| **可读性** | 高 | YAML 的缩进格式经过精心排版后，人类阅读效率最高 |
| **注释支持** | 高 | `#` 注释在配置文件中极其重要（字段说明、安全警告），JSON/TOML 的注释方案各有问题 |
| **Pydantic 集成** | 高 | Python 的 `pyyaml` + Pydantic 可一键反序列化为类型化对象 |
| **复杂数据结构** | 高 | 路由器的防火墙规则、端口映射、应用市场的层级结构需要嵌套列表和字典，YAML 表达最清晰 |
| **OpenWrt 兼容** | 中 | OpenWrt 的 UCI 不是 YAML，但 YAML 比 UCI 更容易理解 |

### 不使用 JSON 作为配置格式

| 因素 | 说明 |
|------|------|
| **无注释** | 配置文件的注释对运维人员至关重要，JSON 不支持 |
| **括号爆炸** | 复杂嵌套配置时 `}}}` 的层级难以分辨 |
| **尾逗号** | JSON 不允许尾逗号，手动编辑容易出错 |

### 不使用 TOML

| 因素 | 说明 |
|------|------|
| **嵌套限制** | TOML 的 `[[array]]` 表和 `[table]` 表在深层嵌套（如防火墙规则列表）时不够直观 |
| **社区采用率** | 网络设备配置文件的社区实践中，YAML 远远领先于 TOML |

## 影响

### 正面

- 配置格式与 netplan 一致，熟悉 netplan 的用户可以直接阅读
- YAML 的锚点 `&` 和别名 `*` 功能可减少重复配置（如多个接口共享相同 DNS 配置）
- GitHub/GitLab 对 YAML 的 diff 渲染最佳

### 负面

- YAML 的缩进敏感性是常见错误来源，但通过 Pydantic 的 Schema 校验可以捕获大部分缩进错误
- YAML 全量加载速度慢于 JSON（但对于 KB 级别的配置文件无感知差异）

## 分层格式策略

```
┌─────────────────────────────────────┐
│  人类可编辑的配置文件               │
│  /etc/ubunturouter/config.yaml       │  ← YAML（人工编辑 + 注释）
│  应用模板 / App Store manifest.yaml  │  ← YAML（人工编写）
├─────────────────────────────────────┤
│  API 交互层                          │
│  REST API 请求/响应                   │  ← JSON（Web 标准，机器解析快）
│  WebSocket 消息                      │  ← JSON（前端消费）
├─────────────────────────────────────┤
│  内部数据层                          │
│  Pydantic 内存对象                   │  ← Python 类型化对象
│  快照存储                           │  ← YAML（保留注释，可比对）
│  状态缓存 / 序列化                   │  ← JSON（启动时快速加载）
└─────────────────────────────────────┘
```

## 实施要点

1. 使用 `yaml.CLoader`（C 扩展）加速 YAML 解析
2. 所有 YAML 文件通过 Pydantic model 反序列化，确保类型安全
3. API 的 `request/response` 使用 JSON（FastAPI + Pydantic 自动转换，对开发者透明）
4. 配置快照同时保存原始 YAML（用于 diff）和 JSON（用于快速加载）
5. 提供 `urctl validate` 命令校验 YAML 语法和 Schema
