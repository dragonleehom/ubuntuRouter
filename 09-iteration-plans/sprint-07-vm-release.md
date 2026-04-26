# Sprint 7: VM 管理 + 发布准备

> 周期: 第 18-20 周 | 状态: **✅ 已完成** | 负责人: TBD

---

## 范围

实现虚拟机管理功能（KVM/libvirt + noVNC），完成所有已知功能的集成测试，打包发布第一个 Alpha 版本。

## 任务拆解

### Week 18: VM 管理 API

| ID | 任务 | 预估(h) | 前置 | 产出 |
|----|------|---------|------|------|
| 18.1 | libvirt Python 封装：连接/domain/network/storage | 10 | - | `ubunturouter/vm/libvirt_wrapper.py` |
| 18.2 | VM 生命周期 API：list/create/start/stop/restart/delete | 10 | 18.1 | `ubunturouter/api/routes/vm.py` |
| 18.3 | VM 模板管理：qcow2 云镜像下载 + cloud-init 注入 | 6 | 18.2 | `ubunturouter/vm/template.py` |
| 18.4 | noVNC 集成：QEMU VNC → WebSocket 代理 | 8 | 18.1 | `ubunturouter/api/vnc_proxy.py` |
| 18.5 | VFIO 网口直通检测：IOMMU 组扫描 + VFIO 驱动绑定 | 8 | 18.2 | `ubunturouter/vm/vfio.py` |
| 18.6 | VM Web 页面：列表 + 创建向导 + 控制台 + 资源监控 | 14 | 18.2-18.4 | `web/src/views/vm/` |
| 18.7 | 集成测试：VM 创建/启动/控制台 | 8 | 18.6 | `tests/integration/test_vm.sh` |

### Week 19: 集成测试 + 修复

| ID | 任务 | 预估(h) | 前置 | 产出 |
|----|------|---------|------|------|
| 19.1 | 全模块集成测试脚本（硬件验收阶段） | 16 | Sprint 1-6 | `tests/e2e/full_regression.sh` |
| 19.2 | 配置一致性大规模测试：100+ 配置变更 | 8 | 19.1 | `tests/stress/config_stress.sh` |
| 19.3 | 性能基准测试：NAT 吞吐 / WG 吞吐 / conntrack 容量 | 12 | 19.1 | `tests/performance/benchmark.sh` |
| 19.4 | 浏览器兼容性测试：Chrome/Firefox/Edge | 6 | Sprint 6 Web | `web/e2e/browser_compat.spec.ts` |
| 19.5 | 安全测试：SQL 注入 / XSS / CSRF / JWT 攻击 | 10 | 19.1 | `tests/security/` |
| 19.6 | Bug 修复 + 优化 | 20 | 19.1-19.5 | - |

### Week 20: 发布 Alpha 版本

| ID | 任务 | 预估(h) | 前置 | 产出 |
|----|------|---------|------|------|
| 20.1 | deb 包构建脚本：core/web/container/vm/appstore | 8 | Sprint 1-6 | `deploy/Makefile` |
| 20.2 | ISO 构建脚本 + ARM img 构建脚本 | 12 | 20.1 | `deploy/build-iso.sh` |
| 20.3 | qcow2/ova 镜像构建 (Packer) | 8 | 20.1 | `deploy/packer/` |
| 20.4 | 文档：安装指南 + 快速开始 | 8 | 20.2 | `docs/` |
| 20.5 | CHANGELOG + Release Notes | 4 | 所有 | `CHANGELOG.md` |
| 20.6 | PPA 发布 + 安装脚本 (get.ubunturouter.org) | 6 | 20.1 | `deploy/ppa/` |
| 20.7 | Alpha 版本发布 | 2 | 20.4-20.6 | ubunturouter-0.1.0-alpha |

## 验收标准

| # | 验收项 | 验证方式 |
|---|--------|----------|
| S7-01 | VM 创建并启动 | virsh list |
| S7-02 | noVNC 控制台可达 | 浏览器打开控制台 |
| S7-03 | VM 模板下载并创建成功 | 应用市场安装 OpenWrt VM |
| S7-04 | 全模块集成测试 0 failure | `pytest tests/` |
| S7-05 | NAT 吞吐基准（x86 4核）≥ 9.4Gbps | iperf3 |
| S7-06 | 浏览器兼容：三大浏览器均可正常使用 | Playwright 测试 |
| S7-07 | deb 包安装后系统正常 | apt install |
| S7-08 | qcow2 导入 Proxmox 后启动 | 导入验证 |
