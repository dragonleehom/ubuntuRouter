# Sprint 1: 配置引擎 + CLI + 首次初始化

> 周期: 第 1-3 周 | 状态: 待开始 | 负责人: TBD

---

## 范围

构建整个 UbuntuRouter 的最底层：配置引擎负责配置文件的读写、校验、转换、Apply、回滚；初始化器负责首次启动的网口检测和初始配置生成；CLI 提供命令行入口。

## 任务拆解

### Week 1: 配置数据模型 + 配置引擎核心

| ID | 任务 | 预估(h) | 前置 | 产出 |
|----|------|---------|------|------|
| 1.1 | 创建项目骨架：Python package 结构、pyproject.toml、依赖声明 | 4 | - | 可 pip install 的包 |
| 1.2 | 实现 Pydantic 配置模型：`UbunturouterConfig` + 所有子模型 | 8 | 1.1 | `ubunturouter/config/models.py` |
| 1.3 | 实现 ConfigEngine 核心：load/save/validate/diff | 12 | 1.2 | `ubunturouter/engine/engine.py` |
| 1.4 | 实现配置序列化：YAML 读写 + 原子写入 (write-then-rename) | 4 | 1.2 | `ubunturouter/config/serializer.py` |
| 1.5 | 文件锁实现：fcntl 并发控制 | 2 | 1.3 | `ubunturouter/engine/lock.py` |
| 1.6 | 单元测试：配置模型校验 | 6 | 1.2 | `tests/test_config_models.py` |
| 1.7 | 单元测试：ConfigEngine 核心接口 | 6 | 1.3 | `tests/test_engine.py` |

**Week 1 交付物**：`config-engine.md` 中定义的 Pydantic 模型和 ConfigEngine 接口全部可运行，单元测试通过。

### Week 2: 生成器 + Apply 流程 + 回滚

| ID | 任务 | 预估(h) | 前置 | 产出 |
|----|------|---------|------|------|
| 2.1 | Generator 基类 + GeneratorRegistry | 4 | 1.3 | `ubunturouter/engine/generators/base.py` |
| 2.2 | NetplanGenerator: 物理口/VLAN/Bridge/Bonding/WANLAN | 12 | 2.1 + 网络模型 | `ubunturouter/engine/generators/netplan.py` |
| 2.3 | NftablesGenerator: Zone/NAT/端口转发 | 12 | 2.1 + 防火墙模型 | `ubunturouter/engine/generators/nftables.py` |
| 2.4 | DnsmasqGenerator: DHCP/静态租约 | 6 | 2.1 + DHCP模型 | `ubunturouter/engine/generators/dnsmasq.py` |
| 2.5 | ConfigApplier: 原子 Apply + 服务 Reload 顺序 | 8 | 2.2-2.4 | `ubunturouter/engine/applier.py` |
| 2.6 | RollbackManager: 快照创建/回滚/清理 | 6 | 2.5 | `ubunturouter/engine/rollback.py` |
| 2.7 | 集成测试：在 VM 上验证 netplan/nftables/dnsmasq 生成 | 8 | 2.5 | `tests/integration/test_generators.sh` |

**Week 2 交付物**：配置引擎可生成有效的 netplan/nftables/dnsmasq 配置，Apply 后在 VM 上验证生效。回滚机制可用。

### Week 3: Initializer + CLI + 系统服务

| ID | 任务 | 预估(h) | 前置 | 产出 |
|----|------|---------|------|------|
| 3.1 | Initializer: 网口检测 + 角色自动分配 | 8 | 1.3 | `ubunturouter/engine/initializer.py` |
| 3.2 | Initializer: 初始配置生成 + Apply | 6 | 3.1 + 2.2-2.4 | 同上 |
| 3.3 | urctl CLI: init/status/apply/doctor 命令 | 12 | 3.2 | `ubunturouter/cli/main.py` |
| 3.4 | systemd service: ubunturouter-init + ubunturouter-engine | 4 | 3.2 | `deploy/systemd/*.service` |
| 3.5 | 安装脚本: deb 打包 + postinst 配置 | 8 | 3.4 | `deploy/DEBIAN/postinst` |
| 3.6 | Sprint 1 集成测试: 完整流程 (clean install → init → apply) | 8 | 3.5 | `tests/e2e/sprint1.sh` |

**Week 3 交付物**：可在 VM 上通过 apt 安装，首次启动自动初始化，`urctl status` 显示系统状态，`urctl doctor` 诊断可用。

## 验收标准

| # | 验收项 | 验证方式 |
|---|--------|----------|
| S1-01 | Pydantic 模型可正确反序列化合法 YAML | pytest |
| S1-02 | 非法配置（IP 格式错误、端口越界）拒绝 Apply | pytest |
| S1-03 | `netplan apply` 后网络接口正确配置 | 在 VM 上 `ip addr show` 验证 |
| S1-04 | `nft -f` 后防火墙规则生效 | `nft list ruleset` 验证 |
| S1-05 | `dnsmasq` 服务启动，DHCP 分配 IP | VM 另一网卡获取 IP |
| S1-06 | Apply 后修改 IP 导致断网 → 60s 自动回滚 | 手动验证 |
| S1-07 | 单网口 WANLAN 模式初始化完成 | curl http://192.168.21.1 |
| S1-08 | `urctl status` 输出正确 | 命令行验证 |
| S1-09 | `urctl doctor` 检测到常见问题 | 命令行验证 |

## 依赖关系

```
Week 1: 模型 + 引擎核心（无外部依赖）
  │
  ▼
Week 2: 生成器 + Apply（依赖 Week 1，外部依赖 OS 命令）
  │
  ▼
Week 3: CLI + 初始化 + 服务化（依赖 Week 1+2）
```

## 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| netplan 版本兼容性 | 中 | 高 | 在 Ubuntu 24.04/26.04 上都测试 |
| nftables 规则冲突 | 低 | 中 | 使用独立 table 名 `ubunturouter` |
| 回滚导致服务不可用 | 低 | 高 | 回滚也有连通性检测，回滚失败保留现场 |
| 单网口 WANLAN 模式 bug | 中 | 中 | 测试环境就是单网口，可即时发现 |
