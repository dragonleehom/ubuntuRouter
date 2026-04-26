# CLI 接口设计 — urctl

> 版本: v1.0 | 日期: 2026-04-25 | 状态: 初稿
> 入口: `/usr/bin/urctl`
> 鉴权: 通过 `sudo` / `polkit`，系统用户直接执行

---

## 1. 全局选项

```bash
urctl [--format json|yaml|table] [--quiet] [--debug] <command> [args...]

# 环境变量
URCTL_CONFIG=/etc/ubunturouter/config.yaml   # 配置路径
URCTL_API=http://localhost:8080              # API Server 地址（远程模式）
URCTL_FORMAT=table                           # 输出格式
```

---

## 2. 命令树

### 2.1 初始化

```bash
urctl init                     # 交互式初始化（检测网口 → 确认 → 生成配置）
urctl init --auto              # 全自动初始化（信任自动检测）
urctl init --wan=enp1s0        # 手动指定 WAN 口
urctl init --lan=enp2s0,enp3s0 # 手动指定 LAN 口（逗号分隔多个）
urctl init --mode=single       # 强制单网口模式
```

### 2.2 状态查询

```bash
urctl status                   # 系统整体状态概览
urctl status --watch           # 实时监控（类似 top）

urctl status interfaces        # 网口状态
urctl status wan               # WAN 线路状态
urctl status routing           # 路由表
urctl status conntrack         # 连接跟踪
urctl status tunnels           # 所有 VPN/代理通道
urctl status health            # 健康检查摘要
```

### 2.3 配置管理

```bash
urctl config validate          # 校验当前配置
urctl config show              # 显示当前配置
urctl config diff              # 显示未应用的变更

urctl config apply             # 应用配置变更（带回滚保护）
urctl config rollback          # 回滚到上一快照
urctl config rollback --id=xxx # 回滚到指定快照

urctl config snapshots         # 列出快照
urctl config export > backup.yaml      # 导出配置
urctl config import < backup.yaml      # 导入配置
```

### 2.4 系统诊断

```bash
urctl doctor                   # 全量诊断
urctl doctor --quick           # 快速诊断（仅检查关键项）
urctl doctor --section=network # 仅检查网络部分

urctl doctor                   # 输出示例:
# [✓] 系统运行正常
# [✓] 网口: enp1s0 (WAN, 1000M, UP), enp2s0 (LAN, 1000M, UP)
# [✓] 防火墙: nftables 规则加载成功
# [✓] DHCP: 活跃租约 12/15
# [✓] DNS: 上游可达, 缓存命中率 75%
# [✓] WAN: 192.168.1.100 (电信), ping 8.8.8.8 = 5ms
# [✓] 磁盘: / 使用 15/64GB (23%)
```

### 2.5 服务管理

```bash
urctl service list             # 列出所有 UbuntuRouter 服务状态
urctl service restart <name>   # 重启服务 (engine / api / dnsmasq / nftables)
urctl service logs <name>      # 查看服务日志
urctl service logs <name> --follow  # 实时日志
```

### 2.6 高级调试

```bash
urctl debug nftables           # nft list ruleset 的格式化输出
urctl debug netplan            # netplan 当前配置
urctl debug routes             # ip route show table all
urctl debug conntrack          # conntrack -L 简化输出
urctl debug arp                # arp 表
```

---

## 3. 输出格式示例

### `urctl status` (table 模式)

```
UbuntuRouter v1.0.0 — 运行中
────────────────────────────────────────────────────────────────
主机: router                   运行时间: 12d 3h 45m
系统: Ubuntu 26.04 LTS x86_64  内核: 7.0.0-14-generic

网络:
  WAN:   enp1s0 — 1000M — UP — 192.168.1.100 (DHCP)
  LAN:   br-lan — 1000M — UP — 192.168.21.1/24
         ├ enp2s0
         └ enp3s0

通道:
  🌐 直连        → 🟢 healthy   延迟: 5ms
  🛡 Tailscale   → 🟢 connected 出口: us-node (32ms)
  🔗 Clash       → 🟢 running   节点: US 01 (180ms)
  🔒 WireGuard   → 🟢 active    对端: phone, office

防火墙:   input=DROP forward=DROP output=ACCEPT
连接数:   12,345 / 500,000 (2.5%)
DHCP:     12 活跃 / 15 总计
DNS:      缓存命中率 75% | 拦截 5,000/100,000

系统:
  CPU:  12.5% ████░░░░░░░░ (N100 4核)
  内存: 2.1/8.0GB ███░░░░░░░░ (26%)
  磁盘: 15/64GB ███░░░░░░░░░ (23%)  (/)
```

### `urctl status --format json`

```json
{
  "version": "1.0.0",
  "uptime": "12d 3h 45m",
  "hostname": "router",
  "interfaces": [
    {"name": "enp1s0", "role": "wan", "speed": 1000, "link": true}
  ],
  "tunnels": [...],
  "cpu": {"usage": 12.5, "cores": 4},
  "memory": {"total_gb": 8, "used_gb": 2.1}
}
```

---

## 4. 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 成功 |
| 1 | 通用错误 |
| 2 | 配置校验失败 |
| 3 | Apply 失败 |
| 4 | 权限不足 |
| 5 | 服务不可用 |
| 64 | 用户取消操作（交互模式） |
