# UbuntuRouter — 基于 Ubuntu Linux 的现代软路由框架

## 项目简介

UbuntuRouter 是一个基于 Ubuntu Linux 的软路由管理框架，旨在将 Ubuntu Server 从"能做路由"提升到"开箱即用的软路由"。通过声明式配置和 Web GUI，统一管理 netplan/nftables/FRR/DHCP/DNS 等分散子系统。

**项目路径**：`/mnt/aiassistant/Hermes/hermes_home/workspace/ubuntu-router/`

## 项目目录结构

本项目遵循 **文档驱动开发** 流程，每个阶段产出均存入对应目录：

```
ubuntu-router/
├── README.md                 # 项目总览（本文件）
├── 01-requirements/          # 需求分析：PRD、用户故事、功能清单
├── 02-feasibility/           # 可行性报告：技术选型、风险评估
├── 03-high-level-design/     # 高阶设计：系统架构、模块划分
├── 04-detailed-design/       # 详细设计：模块接口、数据结构、流程图
├── 05-architecture/          # 架构决策记录（ADR）、技术规范
├── 06-api-spec/              # API 规范：REST API 文档、CLI 接口
├── 07-test-plan/             # 测试方案：单元测试、集成测试、验收标准
├── 08-deployment/            # 部署方案：安装脚本、系统裁剪、发布流程
├── 09-iteration-plans/       # 迭代计划：Sprint 规划、里程碑
└── 10-meeting-notes/         # 会议纪要：决策记录、待办事项
```

## 开发流程

```
需求分析(01) → 可行性报告(02) → 高阶设计(03) → 详细设计(04)
     ↑                                              ↓
验收测试(07) ← 部署方案(08) ← 迭代开发(09) ← 架构决策(05) + API规范(06)
```

每个阶段的文档是下一阶段的输入。文档完成后进入下一阶段，不跳步。

## 当前状态

- [x] Phase 0: 可行性报告 → `02-feasibility/feasibility-report.md`
- [x] Phase 1: 需求分析 → `01-requirements/PRD.md` + `user-stories.md` + `non-functional-req.md`
- [x] Phase 2: 技术选型 → `02-feasibility/tech-selection.md`
- [x] Phase 3: 高阶设计 → `03-high-level-design/HLD.md` + `module-overview.md` + `data-flow.md`
- [ ] Phase 4: 详细设计（LLD）→ `04-detailed-design/`
- [ ] Phase 5: 架构决策记录（ADR）→ `05-architecture/`
- [ ] Phase 6: API 规范 → `06-api-spec/`
- [ ] Phase 7: 迭代开发 → `09-iteration-plans/`
- [ ] Phase 8: 测试与验收 → `07-test-plan/`
- [ ] Phase 9: 部署与发布 → `08-deployment/`
