#!/usr/bin/env bash
# ============================================================================
# UbuntuRouter 部署脚本
#
# 架构: 编码机 (ARM) ↔ NAS 共享目录 ↔ 测试机 (x86)
#       三方通过同一个 NFS/Samba 共享访问同一份代码
#
# 关键约束:
#   - 编码机 ARM (aarch64) / 测试机 x86_64
#   - node_modules 平台相关: 必须在目标架构上 npm install
#   - Python 纯代码无二进制依赖: 源码直接可用
#   - 前端构建 (npm run build) 必须在 x86 测试机上完成
#
# 用法:
#   ./deploy.sh                    # 默认: 在测试机构建+部署
#   ./deploy.sh --skip-build       # 跳过 npm build，直接重启服务
#   ./deploy.sh --full             # 跑完整 install.sh（含 pip install + npm install）
#   ./deploy.sh --status           # 查看当前服务状态
#   ./deploy.sh --logs             # 查看最近日志
# ============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'
log_info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ─── 配置 ─────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VM_USER="ihermes"
VM_HOST="192.168.100.194"
VM_SHARE_PATH="/home/ihermes/ubuntu-router"   # 测试机上共享目录的挂载点
VM_SSH="sshpass -p dragon88 ssh -o StrictHostKeyChecking=no ihermes@$VM_HOST"
VM_SCP="sshpass -p dragon88 scp -o StrictHostKeyChecking=no"

HOST_ARCH=$(uname -m)
VM_ARCH="x86_64"

# ─── 第 1 步: 在测试机上构建前端 ──────────────────────────────────────────
# 原因: ARM→x86 跨架构，node_modules 必须在 x86 上 npm install
# 共享目录的特性: 本机和测试机看到的是同一份文件，所以 npm run build
# 的产物（web/dist/）在本机也能看到
build_frontend_on_vm() {
    log_info "在测试机 ($VM_HOST, x86_64) 上构建前端..."
    log_info "  (共享目录 CIFS 不支持 symlink，复制 web/源码到本地构建)"

    $VM_SSH <<'REMOTE'
        set -e
        SHARE=/home/ihermes/ubuntu-router
        CACHE=/tmp/ubunturouter-web-cache
        BUILD=/tmp/ubunturouter-web-build

        echo "  → 准备本地构建目录..."
        rm -rf "$BUILD"

        # 从共享目录复制 web 源码（不含 node_modules，这个在本地）
        mkdir -p "$BUILD"
        rsync -a --exclude='node_modules' --exclude='dist' "$SHARE/web/" "$BUILD/"

        # 复用缓存的 node_modules（如果 project.json 没变就不用重新 install）
        if [ -d "$CACHE/node_modules" ]; then
            echo "  → 使用缓存的 node_modules..."
            cp -r "$CACHE/node_modules" "$BUILD/"
        else
            cd "$BUILD"
            echo "  → npm install (本地磁盘, x86_64)..."
            npm install --no-audit --no-fund
            echo "  → 缓存 node_modules 以便下次加速..."
            mkdir -p "$CACHE"
            cp -r "$BUILD/node_modules" "$CACHE/"
        fi

        echo "  → 构建前端..."
        cd "$BUILD" && npm run build

        echo "  → 将构建产物复制回共享目录..."
        mkdir -p "$SHARE/web/dist"
        cp -r "$BUILD/dist/"* "$SHARE/web/dist/"
        rm -rf "$BUILD"
        echo "  → 前端构建完成"
REMOTE
    log_ok "前端构建完成 (x86_64 原生编译)"
}

# ─── 第 2 步: 复制代码到 /opt/ubunturouter ────────────────────────────────
# 使用共享目录的特性: 直接从测试机的挂载点复制到安装目录
deploy_code() {
    log_info "部署代码到 /opt/ubunturouter ..."
    $VM_SSH <<'REMOTE'
        set -e
        SRC=/home/ihermes/ubuntu-router
        DST=/opt/ubunturouter

        # Python 代码
        sudo rm -rf "$DST/ubunturouter"
        sudo cp -r "$SRC/src/ubunturouter" "$DST/ubunturouter"
        sudo find "$DST/ubunturouter" -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true

        # 前端静态文件
        sudo rm -rf "$DST/web/dist"
        sudo cp -r "$SRC/web/dist" "$DST/web/dist"

        # install.sh 备份
        sudo cp "$SRC/install.sh" "$DST/"

        echo "DONE: 代码已部署"
REMOTE
    log_ok "代码已部署到 /opt/ubunturouter"
}

# ─── 第 3 步: 重启服务 ─────────────────────────────────────────────────────
restart_service() {
    log_info "重启 ubunturouter 服务..."
    $VM_SSH "sudo systemctl restart ubunturouter && sleep 2 && sudo systemctl status ubunturouter --no-pager -l | head -8"
    log_ok "服务已重启"
}

# ─── 完整安装（首次部署用） ────────────────────────────────────────────
full_install() {
    log_info "执行完整安装 (install.sh)..."
    $VM_SSH "cd /home/ihermes/ubuntu-router && sudo bash install.sh"
    log_ok "完整安装完成"
}

# ─── 状态/日志 ────────────────────────────────────────────────────────────
show_status() {
    log_info "服务状态:"
    $VM_SSH "systemctl status ubunturouter --no-pager -l | head -20"
    echo ""
    log_info "nftables 状态:"
    $VM_SSH "sudo nft list table inet ubunturouter 2>/dev/null || echo '(表不存在)'"
}

show_logs() {
    log_info "最近日志 (20行):"
    $VM_SSH "journalctl -u ubunturouter --no-pager -n 20 --no-hostname"
}

# ─── 主流程 ────────────────────────────────────────────────────────────────
main() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  UbuntuRouter 部署脚本${NC}"
    echo -e "${CYAN}  编码机: ${HOST_ARCH}  →  测试机: ${VM_ARCH}${NC}"
    echo -e "${CYAN}  共享目录: ${VM_SHARE_PATH}${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════${NC}"
    echo ""

    case "${1:-}" in
        --full)
            full_install
            restart_service
            ;;
        --skip-build)
            deploy_code
            restart_service
            ;;
        --status)
            show_status
            exit 0
            ;;
        --logs)
            show_logs
            exit 0
            ;;
        --help|-h)
            echo "用法: $0 [选项]"
            echo ""
            echo "  无参数 / --quick   在测试机构建前端 + 部署 + 重启"
            echo "  --skip-build       仅部署代码 + 重启 (跳过 npm build)"
            echo "  --full             完整安装 (install.sh, 含 pip/npm install)"
            echo "  --status           查看服务状态"
            echo "  --logs             查看最近日志"
            exit 0
            ;;
        --quick|*)
            build_frontend_on_vm
            deploy_code
            restart_service
            ;;
    esac

    echo ""
    log_ok "部署完成！"
    echo "  Web GUI: http://$VM_HOST:8080/"
    echo ""
}

main "$@"
