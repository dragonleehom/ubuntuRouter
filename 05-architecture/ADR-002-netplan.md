# ADR-002: netplan vs 直接使用 systemd-networkd

> **状态**: 已采纳 | **日期**: 2026-04-25 | **提出者**: 架构评审

---

## 上下文

UbuntuRouter 需要管理网络接口（物理口/VLAN/Bridge/Bonding）并向系统下发配置。Ubuntu 提供了两套网络配置机制：

- **netplan**: Ubuntu 官方网络配置抽象层，使用声明式 YAML，渲染器可选 networkd 或 NetworkManager
- **systemd-networkd 直接配置**: 直接编写 `.network` / `.netdev` 文件，无中间抽象层

## 决策

**主路径使用 netplan。当 netplan 不支持的高级特性（如策略路由、netdev 自定义参数）时，通过 drop-in 文件直接写入 systemd-networkd 配置作为补充。**

## 理由

### 正向因素（支持 netplan）

| 因素 | 权重 | 说明 |
|------|------|------|
| **Ubuntu 官方推荐** | 高 | 未来 Ubuntu 版本将持续优化 netplan，不会出现兼容性问题 |
| **声明式 YAML** | 高 | 与 UbuntuRouter 的声明式配置理念一致，无需再封装一层抽象 |
| **配置验证** | 高 | `netplan generate` 能预检语法错误，networkd 直接配置需要人工检查 |
| **回滚能力** | 中 | netplan apply 内置 60 秒超时回滚（`netplan apply --timeout`） |
| **向后兼容** | 中 | netplan 支持切换到 NetworkManager 渲染器（虽然我们不使用） |
| **社区成熟度** | 高 | Ubuntu Server 的默认方案，文档和社区支持完善 |

### 反向因素（不使用纯 networkd）

| 因素 | 说明 |
|------|------|
| **高级特性限制** | netplan 不支持部分 advanced networkd 特性（如策略路由的复杂匹配条件，VXLAN 某些参数） |
| **中间抽象层** | 多一层间接，调试时需查看生成的 networkd 文件 |
| **文档更新滞后** | netplan 文档有时落后于 networkd 新特性 |

## 影响

### 正面

- 90% 的网络配置场景（ethernet/bridge/vlan/bonding）直接使用 netplan YAML，开发效率高
- 生成的配置文件标准化，团队间理解成本低
- 与 Ubuntu 官方工具链对齐，升级兼容性有保障

### 负面

- 需要维护两套生成逻辑：主路径 netplan + 降级路径 networkd drop-in
- 需要一套检测机制判断 netplan 是否支持某个配置项，不支持时自动 fallback

## 具体策略

```
配置输入 → Config Engine
    │
    ├─ netplan 能表达？
    │     ├─ 是 → 生成 /etc/netplan/01-ubunturouter.yaml
    │     └─ 否 → 生成 /etc/systemd/network/99-ubunturouter-*.network
    │
    ├─ netplan apply → 成功？→ 生效
    │
    └─ netplan apply → 失败？
          ├─ 检查 fallback_list 中是否有对应配置
          └─ 使用 networkd 直接配置
```

**已知 netplan 不支持但需要的特性**：
- `ip rule` 策略路由（由 Routing Manager 通过 `ip rule add` 直接管理，不依赖 netplan）
- WireGuard 配置（直接写 `/etc/wireguard/wg0.conf`，不经过 netplan）
- 仅在 netplan 无法表达时才使用 networkd drop-in

## 备选方案

### 纯 systemd-networkd 
- 直接控制 `.network` / `.netdev` 文件
- 完全控制权，无抽象限制
- 但需要自行处理配置验证、回滚、格式生成
- **结论**: 备用方案，仅在 netplan 无法满足时使用

### NetworkManager
- 主要为桌面/笔记本设计，服务器场景不推荐
- 配置模型复杂，不适合声明式管理
- **结论**: 不采用

## 实施要点

1. 主生成器 NetplanGenerator → `/etc/netplan/01-ubunturouter.yaml`
2. 提供 `netplan generate --debug` 的集成，用于调试生成结果
3. 保留 `netplan apply` 的 60 秒超时回滚机制作为 ConfigEngine 回滚的补充
4. 特殊场景（策略路由、WireGuard）直接由对应 Manager 管理，不经过 netplan
