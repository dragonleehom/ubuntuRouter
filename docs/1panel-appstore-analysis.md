# 1Panel AppStore — 数据模型与架构分析

> 日期: 2026-04-28
> 来源: https://github.com/1Panel-dev/appstore (dev 分支)
> 用途: UbuntuRouter AppStore 对标参考

---

## 1. 仓库整体结构

```
appstore/
├── apps/                          # 应用定义目录
│   ├── ai/                        # AI 分类
│   ├── database/                  # 数据库
│   ├── devtool/                   # 开发工具
│   ├── runtime/                   # 运行环境
│   ├── server/                    # Web服务器
│   ├── storage/                   # 云存储
│   ├── tool/                      # 实用工具
│   ├── website/                   # 建站
│   └── ...                        # 其他分类
├── data.yaml                      # 根分类定义(标签体系)
├── logo.png
├── README.md / README_zh.md
└── .github/workflows/             # CI/CD
```

---

## 2. 分类体系 (根级 data.yaml)

```
标签 ID         | 中文名         | 排序
────────────────|----------------|─────
AI              | AI             | 5
Website         | 建站            | 10
Database        | 数据库          | 20
Server          | Web服务器       | 30
Runtime         | 运行环境        | 40
Tool            | 实用工具        | 50
Storage         | 云存储          | 60
BI              | BI             | 80
CRM             | CRM            | 85
Security        | 安全            | 90
DevTool         | 开发工具        | 100
DevOps          | DevOps         | 110
Middleware      | 中间件          | 120
Media           | 多媒体          | 130
Email           | 邮件服务        | 140
Game            | 休闲游戏        | 150
Local           | 本地            | 9999
```

---

## 3. 单个 App 目录结构

```
apps/<category>/<app-name>/
├── data.yml                       # App 顶层元数据 (名称/描述/分类/链接)
├── logo.png                       # App 图标
├── README.md / README_en.md       # 使用文档
├── <version>/                     # 版本目录 (如 8.0.46/)
│   ├── data.yml                   # 版本表单定义 (环境变量/端口/参数)
│   ├── docker-compose.yml         # Docker 编排模板
│   ├── conf/                      # 配置文件模板
│   │   ├── nginx.conf             # (可选) 配置文件
│   │   └── ...
│   └── scripts/                   # (可选) 安装/升级脚本
│       └── upgrade.sh
└── ...
```

---

## 4. 顶层 data.yml 字段定义 (App 元数据)

```yaml
name: nginx                              # App 唯一标识 (目录名)
tags: [Web服务器]                          # 分类标签 (中文)
title: nginx                              # 显示标题
description: Nginx 是一个高性能的 Web 服务器  # 中文描述

additionalProperties:
  key: nginx                              # 唯一键 (同 name)
  name: Nginx                             # 英文名称
  tags: [Server]                          # 标签 (英文 ID)

  shortDescZh: 高性能 Web 服务器            # 简短中文描述
  shortDescEn: High-performance Web Server # 简短英文描述

  description:                             # 多语言完整描述
    zh: Nginx 是一个高性能的 HTTP 和反向代理 Web 服务器
    en: Nginx is a high-performance HTTP and reverse proxy web server
    ja: Nginxは高性能なHTTPおよびリバースプロキシウェブサーバーです
    # ... 支持 10+ 语言

  type: website                           # 类型: website / runtime
  crossVersionUpdate: false               # 是否支持跨版本升级
  limit: 0                                # 安装数量限制 (0=不限制)
  recommend: 5                            # 推荐评分 (1-5)
  batchInstallSupport: false              # 是否支持批量安装

  website: https://nginx.org              # 官网
  github: https://github.com/nginx/nginx  # GitHub 地址
  document: https://nginx.org/docs        # 文档地址
  
  architectures:                          # 支持的架构
    - amd64
    - arm64
    
  gpuSupport: false                       # 是否需要 GPU (可选)
  memoryRequired: 256                     # 最小内存 (MB) (可选)
```

---

## 5. 版本级 data.yml 字段定义 (表单参数)

```yaml
additionalProperties:
  formFields:
    # ── 类型 1: 端口映射 ──
    - type: number                        # 字段类型
      envKey: PANEL_APP_PORT_HTTP         # 环境变量名 (注入 docker-compose)
      default: 18080                      # 默认值
      required: true                      # 是否必填
      edit: true                          # 是否可编辑
      label:
        en: Web UI Port
        zh: 管理页面端口
      labelEn: Web Port
      labelZh: 端口
      rule: paramPort                     # 验证规则

    # ── 类型 2: 密码 ──
    - type: password
      envKey: MYSQL_ROOT_PASSWORD
      default: ""
      required: true
      edit: true
      random: true                        # 自动生成随机密码
      label:
        en: Database Root Password
        zh: 数据库 root 密码
      labelEn: Root Password
      labelZh: root 密码
      rule: paramCommon

    # ── 类型 3: 下拉选择 ──
    - type: select
      envKey: PHP_VERSION
      default: "8.2"
      required: true
      edit: false
      label:
        en: PHP Version
        zh: PHP 版本
      labelEn: PHP Version
      labelZh: PHP 版本
      values:                              # 下拉选项
        - label: "8.2"
          value: "8.2"
        - label: "8.1"
          value: "8.1"
        - label: "8.0"
          value: "8.0"

    # ── 类型 4: 布尔开关 ──
    - type: boolean
      envKey: ENABLE_SSL
      default: false
      required: true
      edit: true
      label:
        en: Enable HTTPS
        zh: 启用 HTTPS
      labelEn: Enable HTTPS
      labelZh: 启用 HTTPS

    # ── 类型 5: 文本 ──
    - type: text
      envKey: CONTAINER_NAME
      default: "my-app"
      required: true
      edit: true
      label:
        en: Container Name
        zh: 容器名称
      labelEn: Container Name
      labelZh: 容器名称
      rule: paramCommon

    # ── 类型 6: 服务选择 (特殊) ──
    - type: service
      envKey: SERVICE_NAME
      default: ""
      required: false
      edit: true
      label:
        en: Database Service
        zh: 数据库服务
      labelEn: Database Service
      labelZh: 数据库服务

    # ── 类型 7: 应用选择 (带依赖) ──
    - type: apps
      envKey: DB_APP
      default: ""
      required: true
      edit: true
      label:
        en: Database Application
        zh: 数据库应用
      labelEn: Database App
      labelZh: 数据库应用
      values:
        - label: MySQL
          value: mysql
        - label: MariaDB
          value: mariadb
        - label: PostgreSQL
          value: postgresql
      child:                                # 子字段 (选择后动态显示)
        - type: text
          envKey: DB_USER
          default: root
          required: true
          label:
            en: Database User
            zh: 数据库用户
```

### 支持的字段类型

| type | 说明 | 渲染组件 | 可用 rule |
|------|------|---------|-----------|
| `number` | 数字输入 (端口) | el-input-number | `paramPort`, `paramCommon` |
| `password` | 密码输入 | el-input type=password | `paramCommon` |
| `select` | 下拉选择 | el-select | `paramCommon` |
| `boolean` | 布尔开关 | el-switch | - |
| `text` | 文本输入 | el-input | `paramCommon` |
| `service` | 服务选择 | 特殊选择器 | - |
| `apps` | 应用选择 (依赖) | el-select + 子表单 | - |

### 字段公共属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `type` | string | 字段类型 |
| `envKey` | string | 注入到 docker-compose 的环境变量名 |
| `default` | any | 默认值 |
| `required` | bool | 是否必填 |
| `edit` | bool | 是否可编辑 (安装后可修改) |
| `random` | bool | 是否自动生成随机值 (用于密码) |
| `rule` | string | 验证规则 (`paramPort` 端口校验, `paramCommon` 通用校验) |
| `label` | map | 多语言标签 (en/zh/ja 等) |
| `labelEn` | string | 英文短标签 (旧格式) |
| `labelZh` | string | 中文短标签 (旧格式) |
| `values` | array | 选择类型的选项列表 (label + value) |
| `child` | array | 子字段 (选择特定选项后动态显示更多表单) |

---

## 6. Docker Compose 模板规范

```yaml
version: '3'
services:
  mysql:
    image: mysql:${PANEL_VERSION}          # 使用环境变量注入版本
    container_name: ${CONTAINER_NAME}       # 容器名称
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: ${MYSQL_DATABASE}
    ports:
      - "${HOST_PORT}:3306"                 # 端口映射
    volumes:
      - ./data/mysql:/var/lib/mysql         # 数据持久化 (相对路径)
      - ./conf:/etc/mysql/conf.d
      - ./logs:/var/log/mysql
    networks:
      - 1panel-network                      # 统一外部网络
    labels:
      - createdBy=Apps                      # 标记来源

networks:
  1panel-network:
    external: true                           # 使用已存在的网络
```

### 模板变量规则
- `${CONTAINER_NAME}` — 容器名 (自动生成)
- `${PANEL_APP_PORT_*}` — 用户定义的端口
- `${PANEL_DB_ROOT_PASSWORD}` — 自动生成的密码
- `${PANEL_VERSION}` — 版本号 (从目录名)
- 自定义 envKey — 来自版本 data.yml 的 formFields

### 挂载路径约定
```
./data/     → 应用数据 (持久化)
./conf/     → 配置文件
./logs/     → 应用日志
```

---

## 7. App 数量统计

| 分类 | 数量 | 代表 App |
|------|:----:|----------|
| Database (数据库) | ~25 | mysql, mariadb, postgresql, redis, mongodb, clickhouse |
| Server (Web服务器) | ~8 | nginx, openresty, caddy, apache, tomcat |
| Website (建站) | ~8 | wordpress, halo, typecho, umami |
| Runtime (运行环境) | ~5 | php, node, python |
| Tool (实用工具) | ~40+ | alist, frp, ddns-go, portainer, netdata, glances |
| Storage (云存储) | ~6 | minio, nextcloud, seafile, syncthing |
| Middleware (中间件) | ~10 | rabbitmq, kafka, zookeeper, consul |
| Media (多媒体) | ~8 | jellyfin, plex, emby, calibre-web |
| AI | ~5 | ollama, open-webui, stable-diffusion |
| Security (安全) | ~8 | vaultwarden, crowdsec, fail2ban |
| DevTool (开发工具) | ~15 | gitlab, jenkins, sonarqube, gitea |
| DevOps | ~5 | harbor, drone, argocd |
| Email (邮件服务) | ~4 | mailserver, roundcube |
| Game (休闲游戏) | ~4 | minecraft, terraria |
| BI | ~3 | metabase, superset |
| CRM | ~2 | twenty, suitecrm |
| Local (本地) | ~2 | 本地工具 |
| **总计** | **~216** | |

---

## 8. 关键设计亮点 (UbuntuRouter 可借鉴)

### 8.1 参数表单的声明式定义
- 每个版本的 `data.yml` 自描述完整的表单参数
- 安装时前端根据 `type` 自动渲染对应表单控件
- `child` 字段实现联动（选数据库应用后显示数据库用户/密码输入框）

### 8.2 多语言支持
- 字段标签支持 `label.en/zh/ja/ru/fr/es/pt/de/tr/ko` 等 10+ 语言
- 描述字段也支持多语言

### 8.3 版本管理与升级
- 每个版本独立目录，支持不同版本的参数配置
- `crossVersionUpdate` 标记跨版本兼容性
- `scripts/upgrade.sh` 自定义升级逻辑

### 8.4 安装约束
- `limit: 0` 不限制安装数量
- `architectures` 标记支持的 CPU 架构
- `gpuSupport` 标记是否需要 GPU
- `memoryRequired` 标记最小内存要求

### 8.5 网络约定
- 统一使用外部网络 `1panel-network`
- 端口映射通过 `envKey` 注入
- 所有服务共享同一 Docker 网络

### 8.6 CI/CD 自动化
- GitHub Actions 自动检查 data.yml 格式
- 自动生成索引
- 自动合并到 `main` 分支

---

## 9. 与 UbuntuRouter 当前 AppStore 的差距

| 维度 | 1Panel | UbuntuRouter 当前 | 差距 |
|------|--------|-------------------|------|
| App 数量 | ~216 | ~20+ | ❌ 需扩充 |
| 参数表单类型 | 7种 (text/number/password/select/boolean/service/apps) | 仅 text | ❌ 需增强 |
| 参数验证规则 | paramPort/paramCommon | 无 | ❌ 需增加 |
| 自动随机密码 | `random: true` | 无 | ❌ 需增加 |
| 多语言支持 | 10+ 语言 | 仅中英文(刚实现) | ⚠️ 起步阶段 |
| 子表单联动 | child 字段 | 无 | ❌ 需增加 |
| 安装约束 | architectures/gpuSupport/memoryRequired | 无 | ❌ 需增加 |
| 版本管理 | 多版本目录 | 单一版本 | ❌ 需增加 |
| 脚本支持 | install/upgrade 脚本 | 仅有 Docker Compose | ❌ 需增加 |
| 跨版本升级 | crossVersionUpdate | 无 | ❌ 需增加 |

---

*本报告基于 1Panel-dev/appstore 仓库 (dev 分支) 源码分析，覆盖 216 个应用的目录结构分析。*
