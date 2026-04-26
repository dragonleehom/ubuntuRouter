# 开发流程规范

## 总体流程

本项目采用 **文档驱动 + 迭代开发** 模式，共 8 个阶段，严格按顺序推进。
每个阶段必须产出对应文档并通过评审后，方可进入下一阶段。

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Phase 1 │───→│  Phase 2 │───→│  Phase 3 │───→│  Phase 4 │
│  需求分析 │    │ 可行性报告│    │  高阶设计 │    │  详细设计 │
│  (01-req)│    │ (02-feas)│    │  (03-hld)│    │  (04-lld)│
└──────────┘    └──────────┘    └──────────┘    └──────────┘
                                                     │
┌──────────┐    ┌──────────┐    ┌──────────┐         │
│  Phase 8 │←───│  Phase 7 │←───│  Phase 6 │←───┌────▼─────┐
│ 部署与发布│    │  测试验收 │    │  迭代开发 │    │  Phase 5 │
│(08-deploy)│   │(07-test) │    │(09-sprint)│    │ 架构决策  │
└──────────┘    └──────────┘    └──────────┘    │ +API规范 │
                                                │(05-arch) │
                                                │(06-api)  │
                                                └──────────┘
```

## 各阶段说明

### Phase 1: 需求分析 → `01-requirements/`

**目标**：明确项目做什么、不做什么

**产出文件**：
| 文件 | 内容 |
|------|------|
| `PRD.md` | 产品需求文档：目标用户、核心场景、功能列表、优先级 |
| `user-stories.md` | 用户故事：以用户视角描述功能需求 |
| `non-functional-req.md` | 非功能需求：性能、安全、可用性指标 |

**输入要求**（需用户提供）：
1. 目标用户群（家庭用户/SOHO/中小企业？）
2. 必须支持的网络场景（多WAN？VLAN？VPN？）
3. 硬件目标平台（x86小主机/虚拟机/云服务器？）
4. 性能期望（百兆/千兆/万兆？）
5. 是否需要与现有方案（OpenWrt等）兼容

**评审标准**：功能列表完整，优先级清晰，范围边界明确

---

### Phase 2: 可行性报告 → `02-feasibility/`

**目标**：确认技术方案可行，识别风险

**产出文件**：
| 文件 | 内容 |
|------|------|
| `feasibility-report.md` | 可行性报告：技术可行性、方案对比、风险评估 |
| `tech-selection.md` | 技术选型：各模块技术方案及选择理由 |

**评审标准**：技术风险可控，选型有充分依据

---

### Phase 3: 高阶设计 → `03-high-level-design/`

**目标**：确定系统整体架构和模块划分

**产出文件**：
| 文件 | 内容 |
|------|------|
| `HLD.md` | 高阶设计文档：系统架构、模块划分、数据流 |
| `module-overview.md` | 模块概述：每个模块的职责和边界 |
| `data-flow.md` | 数据流图：配置从输入到生效的完整路径 |

**评审标准**：模块边界清晰，接口定义明确，架构可扩展

---

### Phase 4: 详细设计 → `04-detailed-design/`

**目标**：每个模块的内部设计和接口规范

**产出文件**：
| 文件 | 内容 |
|------|------|
| `config-engine.md` | 配置引擎详细设计 |
| `network-manager.md` | 网络管理模块详细设计 |
| `firewall-manager.md` | 防火墙模块详细设计 |
| `routing-manager.md` | 路由管理模块详细设计 |
| `dhcp-dns-manager.md` | DHCP/DNS 模块详细设计 |
| `vpn-manager.md` | VPN 模块详细设计 |
| `web-gui.md` | Web GUI 详细设计 |

**评审标准**：接口签名明确，数据结构定义完整，边界条件考虑充分

---

### Phase 5: 架构决策记录 + API 规范 → `05-architecture/` + `06-api-spec/`

**目标**：记录关键架构决策，定义 API 契约

**产出文件**：
| 文件 | 内容 |
|------|------|
| `05-architecture/ADR-001-nftables.md` | ADR：为什么选 nftables 而非 iptables |
| `05-architecture/ADR-002-netplan.md` | ADR：为什么选 netplan 作为网络配置后端 |
| `05-architecture/ADR-003-fastapi.md` | ADR：为什么选 FastAPI 作为 API 框架 |
| `06-api-spec/rest-api-v1.yaml` | OpenAPI 3.0 规范 |
| `06-api-spec/cli-interface.md` | CLI 接口设计 |

**评审标准**：ADR 有充分的上下文和替代方案分析，API 定义可直接用于代码生成

---

### Phase 6: 迭代开发 → `09-iteration-plans/`

**目标**：按迭代计划编码实现

**产出文件**：
| 文件 | 内容 |
|------|------|
| `sprint-01.md` | Sprint 1 计划与回顾 |
| `sprint-02.md` | Sprint 2 计划与回顾 |
| ... | 每个 Sprint 一份 |

**迭代划分**：
- Sprint 1: 配置引擎 + CLI + 首次初始化
- Sprint 2: REST API + Auth + Dashboard 基础
- Sprint 3: 防火墙 + DHCP/DNS + 路由 Web 页面
- Sprint 4: VPN 通道 + 地图组件 + Multi-WAN
- Sprint 5: 应用市场 + 容器管理
- Sprint 6: 流量编排 + Dashboard 完善
- Sprint 7: VM 管理 + 集成测试 + Alpha 发布

---

### Phase 7: 测试验收 → `07-test-plan/`

**目标**：验证实现符合需求

**产出文件**：
| 文件 | 内容 |
|------|------|
| `test-strategy.md` | 测试策略：测试类型、工具、覆盖率目标 |
| `integration-test-cases.md` | 集成测试用例 |
| `acceptance-criteria.md` | 验收标准：对应 PRD 的验收检查表 |

---

### Phase 8: 部署发布 → `08-deployment/`

**目标**：生产环境部署方案

**产出文件**：
| 文件 | 内容 |
|------|------|
| `installation-guide.md` | 安装指南 |
| `system-hardening.md` | 系统加固 |
| `release-process.md` | 发布流程 |

---

## 评审机制

1. 每个阶段完成后，产出文档提交评审
2. 评审方式：用户审阅文档，提出修改意见
3. 评审通过后，进入下一阶段
4. 如需回退，更新文档后重新评审

## 会议纪要 → `10-meeting-notes/`

每次重大决策讨论后，产出会议纪要：
- 日期、参与人
- 讨论议题
- 决策结论
- 待办事项
