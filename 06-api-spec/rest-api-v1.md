# REST API 规范 v1.0

> 版本: v1.0 | 日期: 2026-04-25 | 状态: 初稿
> 基 URL: `https://192.168.21.1:443/api/v1`
> 鉴权: `Authorization: Bearer <JWT>`

---

## 1. 鉴权

### POST /auth/login

系统 PAM 登录，返回 JWT Token。

**Request**:
```json
{
  "username": "uradmin",
  "password": "password123",
  "otp_code": null
}
```

**Response (200)**:
```json
{
  "token": "eyJhbGciOi...",
  "expires_in": 1800,
  "user": {
    "username": "uradmin",
    "uid": 1000,
    "groups": ["sudo", "adm"]
  }
}
```

**Response (401)**:
```json
{
  "error": "invalid_credentials",
  "message": "用户名或密码错误",
  "remaining_attempts": 4
}
```

### POST /auth/logout

注销当前 Session。

### GET /auth/sessions

列出当前活跃的 Session。

**Response**:
```json
{
  "sessions": [
    {"id": "sess_xxx", "ip": "192.168.21.100", "created_at": "...", "last_active": "..."}
  ]
}
```

### DELETE /auth/sessions/{session_id}

强制登出指定 Session。

---

## 2. Dashboard

### GET /dashboard/status

Dashboard 全量状态（首次加载用）。

**Response**:
```json
{
  "network": {
    "interfaces": [
      {"name": "enp1s0", "role": "wan", "speed": 1000, "link": true,
       "ip": "192.168.1.100", "rx_rate": 1234567, "tx_rate": 890123}
    ],
    "tunnels": [
      {"id": "ts-exit-us", "name": "Tailscale 美国", "status": "connected",
       "latency_ms": 32, "location": "Los Angeles"}
    ],
    "conntrack_count": 12345,
    "gateway": {"ip": "192.168.1.1", "location": "上海 电信"}
  },
  "system": {
    "hostname": "router",
    "version": "1.0.0",
    "uptime": "12d 3h 45m",
    "cpu": {"usage": 12.5, "cores": [8, 15, 10, 5], "model": "Intel N100", "count": 4},
    "memory": {"total_gb": 8, "used_gb": 2.1, "available_gb": 5.2},
    "disk": [{"mount": "/", "total_gb": 64, "used_gb": 15, "avail_gb": 46}],
    "temperature": {"cpu": 45.2, "board": 38.0}
  },
  "apps": {
    "total": 8,
    "running": 6,
    "stopped": 1,
    "error": 1,
    "list": [
      {"id": "ha", "name": "Home Assistant", "type": "docker", "status": "running",
       "cpu": 2.3, "memory_mb": 128, "rx_bytes": 1000000000, "tx_bytes": 2000000000,
       "uptime": "12d", "web_url": "http://192.168.21.50:8123"}
    ]
  },
  "geo_map": {
    "nodes": [
      {"id": "local", "name": "本地网关", "lat": 31.23, "lng": 121.47,
       "city": "上海", "country": "CN", "type": "local"},
      {"id": "ts-us", "name": "Tailscale 美国", "lat": 34.05, "lng": -118.24,
       "city": "Los Angeles", "country": "US", "type": "tunnel",
       "latency_ms": 32}
    ],
    "links": [
      {"from": "local", "to": "ts-us", "latency_ms": 32, "status": "up"}
    ]
  }
}
```

### WS /ws/dashboard

WebSocket 实时推送。

**Server → Client 消息格式**:

```json
{
  "type": "traffic_update",
  "timestamp": "2026-04-25T10:00:00Z",
  "data": {
    "interfaces": [
      {"name": "enp1s0", "rx_rate": 1234567, "tx_rate": 890123}
    ]
  }
}
```

```json
{
  "type": "tunnel_status",
  "data": {
    "tunnels": [
      {"id": "ts-exit-us", "status": "connected", "latency_ms": 32}
    ]
  }
}
```

```json
{
  "type": "system_status",
  "data": {
    "cpu": {"usage": 12.5},
    "memory": {"used_gb": 2.1, "available_gb": 5.2}
  }
}
```

```json
{
  "type": "app_status",
  "data": {
    "apps": [...],
    "summary": {"total": 8, "running": 6, "stopped": 1, "error": 1}
  }
}
```

---

## 3. 接口管理

### GET /interfaces

列出所有接口配置。

**Response**:
```json
{
  "interfaces": [
    {"name": "wan0", "device": "enp1s0", "type": "ethernet", "role": "wan",
     "ipv4": {"method": "dhcp", "address": "192.168.1.100/24"},
     "firewall": {"zone": "wan"},
     "enabled": true}
  ]
}
```

### GET /interfaces/status

所有接口运行时状态。

**Response**:
```json
{
  "interfaces": [
    {"name": "enp1s0", "type": "ethernet", "operstate": "UP", "carrier": true,
     "speed": 1000, "ipv4": [...], "mac": "aa:bb:cc:11:22:33", "mtu": 1500,
     "rx_bytes": 1234567890, "tx_bytes": 987654321}
  ]
}
```

### POST /interfaces/detect

重新检测物理网口。

**Response**:
```json
{
  "nics": [
    {"name": "enp1s0", "driver": "i226", "speed": 1000, "link": true},
    {"name": "enp2s0", "driver": "i226", "speed": 2500, "link": true}
  ]
}
```

---

## 4. 防火墙

### GET /firewall/zones

列出所有 Zone。

### POST /firewall/zones

创建 Zone。

**Request**:
```json
{
  "name": "guest",
  "masquerade": false,
  "forward_to": ["wan"],
  "isolated": true,
  "input": "drop",
  "forward": "drop"
}
```

### GET /firewall/port-forwards

列出端口转发规则。

### POST /firewall/port-forwards

创建端口转发。

**Request**:
```json
{
  "name": "web",
  "protocol": "tcp",
  "from_zone": "wan",
  "from_port": 8443,
  "to_ip": "192.168.21.50",
  "to_port": 443
}
```

### DELETE /firewall/port-forwards/{name}

删除端口转发。

### GET /firewall/rules

列出自定义规则。

### POST /firewall/rules

添加自定义规则。

### GET /firewall/conntrack

连接跟踪表。

**Query**: `?limit=100&filter=established`

---

## 5. 路由

### GET /routing/routes

列出路由表。

**Query**: `?table=101`

**Response**:
```json
{
  "routes": [
    {"target": "0.0.0.0/0", "via": "192.168.1.1", "dev": "enp1s0",
     "metric": 100, "table": 254, "source": "system"}
  ]
}
```

### POST /routing/static-routes

添加静态路由。

**Request**:
```json
{
  "target": "10.0.0.0/24",
  "via": "192.168.21.2",
  "metric": 100,
  "comment": "Site B"
}
```

### GET /routing/multiwan

Multi-WAN 状态。

**Response**:
```json
{
  "enabled": true,
  "strategy": "failover",
  "wans": [
    {"name": "wan0", "device": "enp1s0", "gateway": "192.168.1.1",
     "health": "healthy", "latency_ms": 5.2, "failover_count": 0},
    {"name": "wan1", "device": "enp2s0", "gateway": "10.0.0.1",
     "health": "healthy", "latency_ms": 8.1}
  ],
  "active_wan": "wan0"
}
```

### POST /routing/multiwan/switch

手动切换活跃 WAN。

**Request**:
```json
{
  "to": "wan1"
}
```

---

## 6. DHCP

### GET /dhcp/leases

DHCP 租约列表。

**Query**: `?pool=br-lan&status=active`

**Response**:
```json
{
  "leases": [
    {"mac": "aa:bb:cc:11:22:33", "ip": "192.168.21.100",
     "hostname": "tv", "expires": "2026-04-26T10:00:00Z", "online": true}
  ],
  "stats": {"total": 15, "active": 12, "static": 3}
}
```

### POST /dhcp/static-leases

添加静态租约。

**Request**:
```json
{
  "mac": "aa:bb:cc:11:22:33",
  "ip": "192.168.21.100",
  "hostname": "tv"
}
```

### DELETE /dhcp/leases?mac=aa:bb:cc:11:22:33

释放租约。

---

## 7. DNS

### GET /dns/status

DNS 状态和统计。

**Response**:
```json
{
  "mode": "forward",
  "upstream": ["223.5.5.5", "119.29.29.29"],
  "cache_size": 10000,
  "stats": {
    "queries_total": 100000,
    "cached_hits": 75000,
    "blocked": 5000
  },
  "dnssec": true
}
```

### POST /dns/flush-cache

清空 DNS 缓存。

### GET /dns/query-log

DNS 查询日志。

**Query**: `?limit=50&device=tv&domain=netflix`

### POST /dns/rewrites

添加 DNS 重写。

**Request**:
```json
{
  "domain": "nas.lan",
  "ip": "192.168.21.50"
}
```

### POST /dns/forwarders

添加域名分流。

**Request**:
```json
{
  "domain": "*.google.com",
  "servers": ["8.8.8.8", "1.1.1.1"],
  "doh": true
}
```

---

## 8. VPN / 通道

### GET /vpn/tunnels

列出所有可用通道。

**Response**:
```json
{
  "tunnels": [
    {"id": "direct", "name": "直连", "type": "direct", "status": "connected",
     "is_exit_node": true},
    {"id": "ts-exit-us", "name": "Tailscale 美国", "type": "tailscale",
     "status": "connected", "latency_ms": 32, "location": "Los Angeles",
     "is_exit_node": true},
    {"id": "oc-us", "name": "Clash 美国", "type": "clash",
     "status": "connected", "latency_ms": 180, "location": "US"},
    {"id": "wg-home", "name": "WireGuard 回家", "type": "wireguard",
     "status": "connected", "latency_ms": 15,
     "traffic_rx": 1000000, "traffic_tx": 2000000}
  ]
}
```

### GET /vpn/tunnels/{id}/test

测试通道延迟。

### GET /vpn/wireguard/peers

WireGuard Peer 列表。

### POST /vpn/wireguard/peers

添加 WireGuard Peer。

**Request**:
```json
{
  "name": "phone",
  "public_key": "xxx",
  "allowed_ips": ["10.0.1.2/32", "192.168.21.0/24"],
  "persistent_keepalive": 25
}
```

### POST /vpn/wireguard/config

生成客户端配置文件。

**Request**:
```json
{
  "peer_name": "phone",
  "format": "conf"
}
```

**Response**:
```json
{
  "config": "[Interface]\nPrivateKey = ...",
  "qrcode": "data:image/png;base64,..."
}
```

### GET /vpn/tailscale/status

Tailscale 状态。

### GET /vpn/clash/status

Clash 状态。

### GET /vpn/clash/proxies

Clash 代理列表。

### PUT /vpn/clash/proxies/{group}

切换 Clash 代理组。

**Request**:
```json
{
  "name": "US 01"
}
```

---

## 9. 流量编排

### GET /orchestrator/devices

设备列表。

**Response**:
```json
{
  "devices": [
    {"id": "aa:bb:cc:11:22:33", "name": "电视", "vendor": "Xiaomi",
     "ip": "192.168.21.100", "online": true,
     "detected_apps": ["netflix", "youtube"],
     "traffic_rx": 1000000000, "traffic_tx": 500000000}
  ]
}
```

### PUT /orchestrator/devices/{mac}

重命名设备。

**Request**:
```json
{
  "name": "客厅电视"
}
```

### GET /orchestrator/apps

应用列表（来自特征库）。

**Response**:
```json
{
  "apps": [
    {"id": "netflix", "name": "Netflix", "category": "video",
     "domains": ["*.netflix.com", "*.nflxvideo.net"]}
  ]
}
```

### GET /orchestrator/rules

编排规则列表。

**Response**:
```json
{
  "rules": [
    {"id": "rule_1", "device": "aa:bb:cc:11:22:33", "app": "netflix",
     "tunnel_primary": "ts-exit-us", "tunnel_backup": "oc-us",
     "priority": 1, "enabled": true, "hits": 1234}
  ]
}
```

### POST /orchestrator/rules

创建编排规则。

**Request**:
```json
{
  "device_mac": "aa:bb:cc:11:22:33",
  "app": "netflix",
  "tunnel_primary": "ts-exit-us",
  "tunnel_backup": "oc-us",
  "priority": 1
}
```

### DELETE /orchestrator/rules/{id}

删除编排规则。

### GET /orchestrator/stats

流量统计。

**Query**: `?device=aa:bb:cc:11:22:33&period=24h`

**Response**:
```json
{
  "by_device": [...],
  "by_tunnel": [...],
  "by_app": [...],
  "total_rx": 500000000000,
  "total_tx": 200000000000
}
```

---

## 10. 应用市场

### GET /appstore/apps

应用市场列表。

**Query**: `?category=smart-home&search=home`

**Response**:
```json
{
  "apps": [
    {"id": "homeassistant", "name": "Home Assistant", "category": "smart-home",
     "type": "container", "version": "2024.1.0", "installed": true,
     "status": "running", "icon": "/appstore/icons/homeassistant.png"}
  ],
  "categories": ["smart-home", "media", "network", "tools", "virtual-system"]
}
```

### GET /appstore/apps/{id}

应用详情。

**Response**:
```json
{
  "id": "homeassistant",
  "name": "Home Assistant",
  "version": "2024.1.0",
  "description": "开源智能家居平台",
  "type": "container",
  "category": "smart-home",
  "screenshots": [...],
  "install_params": {
    "env": [{"key": "TZ", "default": "Asia/Shanghai"}],
    "ports": [{"container": 8123, "host": 8123}],
    "volumes": [...]
  },
  "links": {"website": "https://www.home-assistant.io"},
  "installed": false
}
```

### POST /appstore/apps/{id}/install

安装应用。

**Request**:
```json
{
  "env": {"TZ": "Asia/Shanghai"},
  "ports": [{"host": 8123}],
  "volumes": [{"host_path": "/data/ha"}]
}
```

**Response (202)**:
```json
{
  "task_id": "task_xxx",
  "status": "installing"
}
```

### POST /appstore/apps/{id}/update

更新应用。

### POST /appstore/apps/{id}/uninstall

卸载应用。

**Request**:
```json
{
  "remove_data": false,
  "remove_volumes": false
}
```

### GET /appstore/installed

已安装应用列表。

**Response**:
```json
{
  "apps": [
    {"id": "homeassistant", "name": "Home Assistant", "type": "docker",
     "status": "running", "uptime": "12d",
     "cpu": 2.3, "memory_mb": 128,
     "rx_bytes": 1000000000, "tx_bytes": 2000000000,
     "web_url": "http://192.168.21.50:8123"}
  ]
}
```

### POST /appstore/repos

添加第三方应用源。

**Request**:
```json
{
  "url": "https://github.com/user/ubunturouter-apps",
  "name": "My Apps"
}
```

### DELETE /appstore/repos/{id}

移除应用源。

---

## 11. 虚拟机

### GET /vm/vms

VM 列表。

**Response**:
```json
{
  "vms": [
    {"name": "openwrt", "status": "running", "vcpu": 2, "memory_mb": 512,
     "disk_gb": 2, "console_url": "/vm/vnc/openwrt",
     "rx_bytes": 1000000, "tx_bytes": 2000000}
  ]
}
```

### POST /vm/vms

创建 VM。

### POST /vm/vms/{name}/start|stop|restart

VM 生命周期。

### GET /vm/vms/{name}/console

VM noVNC 控制台 WebSocket URL。

**Response**:
```json
{
  "url": "ws://192.168.21.1:8080/vm/vnc/openwrt"
}
```

### GET /vm/templates

VM 模板列表。

---

## 12. 容器

### GET /containers

容器列表。

**Response**:
```json
{
  "containers": [
    {"id": "homeassistant", "image": "ghcr.io/home-assistant/home-assistant:stable",
     "status": "running", "ports": ["8123:8123"],
     "created": "2026-04-13T10:00:00Z", "uptime": "12d"}
  ]
}
```

### POST /containers/{id}/start|stop|restart

容器生命周期。

### GET /containers/{id}/logs

容器日志。

**Query**: `?follow=true&tail=100`

### GET /containers/{id}/terminal

容器 Web 终端 URL。

**Response**:
```json
{
  "url": "ws://192.168.21.1:8080/containers/homeassistant/terminal"
}
```

---

## 13. 系统

### GET /system/status

系统状态。

### GET /system/logs

系统日志。

**Query**: `?service=ubunturouter-engine&level=error&since=2026-04-25T00:00:00Z`

### POST /system/backup

创建配置备份。

**Response**:
```json
{
  "file": "ubunturouter-backup-20260425.tar.gz",
  "size": 1234567
}
```

### POST /system/restore

恢复配置。

### GET /system/snapshots

配置快照列表。

### POST /system/snapshots/{id}/rollback

回滚到指定快照。

### POST /system/upgrade

系统升级。

### GET /system/terminal

Web 终端 URL。

**Response**:
```json
{
  "url": "ws://192.168.21.1:8080/system/terminal"
}
```

---

## 14. 配置 Apply

### POST /config/apply

应用当前配置。

**Response**:
```json
{
  "task_id": "task_xxx",
  "status": "applying",
  "estimated_seconds": 5
}
```

### GET /config/apply/{task_id}/status

查询 Apply 状态。

**Response**:
```json
{
  "task_id": "task_xxx",
  "status": "success",
  "snapshot_id": "20260425_120000_abc123",
  "services_reloaded": ["networking", "nftables", "dnsmasq"],
  "execution_time_ms": 3210
}
```

### POST /config/rollback/{snapshot_id}

回滚到快照。

---

## 15. WebSocket Endpoints 汇总

| 端点 | 推送内容 | 频率 |
|------|----------|------|
| `WS /ws/dashboard` | 流量/隧道/系统/应用状态 | 2-30s |
| `WS /ws/containers/{id}/logs` | 容器日志流 | 实时 |
| `WS /ws/containers/{id}/terminal` | 容器终端 | 交互式 |
| `WS /ws/vm/{name}/console` | VM noVNC | 交互式 |
| `WS /ws/system/terminal` | 系统终端 | 交互式 |
