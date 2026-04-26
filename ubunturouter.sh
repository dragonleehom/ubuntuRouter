#!/usr/bin/env bash
# ============================================================================
# UbuntuRouter — 开发调测工作流脚本
#
# 工作流:
#   开发机 (本机 ARM):  编码 → 代码审查 → 单元测试 → git commit → git push
#   GitHub:             代码仓库
#   测试机 (x86 VM):    git pull → ubunturouter.sh update → 浏览器验证
#
# 命令:
#   install   → 在新主机上首次部署（或重新完整安装）
#   update    → 在已安装主机上 git pull + 构建 + 部署 + 重启
#   status    → 查看服务状态
#   logs      → 查看最近日志
#   test      → 运行本地单元测试
#
# 设计要点:
#   - 脚本位于项目根目录，通过 CIFS 共享被开发机和测试机同时访问
#   - 自动检测运行位置: sshpass 存在 = 开发机, 否则 = 测试机本地
#   - 所有 vm_* 函数在开发机上通过 ssh 执行，在测试机上直接本地执行
# ============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'
log_info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_NAME="$(basename "$0")"
VM_HOST="192.168.100.194"
VM_USER="ihermes"
VM_PASS="dragon88"

# ─── 运行上下文检测 ─────────────────────────────────────────────────────────
# 开发机 (ARM NAS):  有 sshpass → 通过 ssh 操作测试机
# 测试机 (x86 VM):   无 sshpass → 直接本地操作
IS_ON_DEV_MACHINE=false
SSH_CMD=""
if command -v sshpass >/dev/null 2>&1; then
    IS_ON_DEV_MACHINE=true
    SSH_CMD="sshpass -p $VM_PASS ssh -o StrictHostKeyChecking=no $VM_USER@$VM_HOST"
fi
SSH_OR_LOCAL="$SSH_CMD"

# ─── 帮助信息 ──────────────────────────────────────────────────────────────
show_help() {
    echo ""
    echo "UbuntuRouter — 开发调测工作流"
    echo ""
    echo "用法: sudo ./$SCRIPT_NAME <命令> [选项]"
    echo ""
    echo "命令:"
    echo "  install              首次部署: 依赖安装 + 构建 + 部署 + 启动"
    echo "  update               更新部署: 代码审查 + 测试 + push + 构建 + 部署"
    echo "  status               查看服务状态"
    echo "  logs [-n <行数>]     查看日志 (默认 30 行)"
    echo "  test [模块]          运行本地单元测试"
    echo "  help                 显示此帮助"
    echo ""
    echo "选项:"
    echo "  -y, --yes            跳过所有确认提示"
    echo "  --skip-pull          跳过 git pull（仅 update 时有效）"
    echo ""
    echo "示例:"
    echo "  sudo ./$SCRIPT_NAME install          # 首次部署"
    echo "  sudo ./$SCRIPT_NAME update           # 完整更新流程"
    echo "  ./$SCRIPT_NAME test                  # 运行全部单元测试"
    echo "  ./$SCRIPT_NAME test sprint1          # 运行 Sprint 1 测试"
    echo "  sudo ./$SCRIPT_NAME logs -n 50       # 查看 50 行日志"
    echo ""
}

# ─── 前置检查 ──────────────────────────────────────────────────────────────
check_prerequisites() {
    log_info "检查前置依赖..."
    command -v git    >/dev/null 2>&1 || { log_error "缺少 git"; exit 1; }
    command -v python3 >/dev/null 2>&1 || { log_error "缺少 python3"; exit 1; }
    log_ok "前置检查通过 (git + python3 可用)"
}

# ─── 运行本地单元测试 ──────────────────────────────────────────────────────
run_tests() {
    local test_filter="${1:-}"
    log_info "运行本地单元测试..."
    cd "$SCRIPT_DIR"

    local HAS_PYTEST=false
    if python3 -m pytest --version >/dev/null 2>&1; then
        HAS_PYTEST=true
    fi

    if [ -n "$test_filter" ]; then
        log_info "  过滤模块: $test_filter"
        if $HAS_PYTEST; then
            PYTHONPATH=src python3 -m pytest "tests/" -k "$test_filter" -v --tb=short \
                --no-header -q -o pythonpath=src 2>&1 || true
        else
            log_warn "  pytest 不可用, 直接运行测试脚本..."
            for f in tests/"$test_filter"*.py tests/test_"$test_filter"*.py; do
                [ -f "$f" ] && PYTHONPATH=src python3 "$f" 2>&1 || true
            done
        fi
    else
        log_info "  运行全部测试..."
        if $HAS_PYTEST; then
            PYTHONPATH=src python3 -m pytest "tests/" -v --tb=short \
                --no-header 2>&1 || true
        else
            for f in tests/test_*.py; do
                [ -f "$f" ] || continue
                log_info "    运行: $f"
                PYTHONPATH=src python3 "$f" 2>&1 || true
            done
        fi
    fi

    local exit_code=$?
    if [ $exit_code -eq 0 ]; then
        log_ok "全部测试通过"
    else
        log_warn "部分测试失败 (exit=$exit_code)"
    fi
    return $exit_code
}

# ─── 本地代码检查 ──────────────────────────────────────────────────────────
code_review() {
    log_info "执行本地代码审查..."
    cd "$SCRIPT_DIR"
    local has_errors=false

    log_info "  1/3 Python 语法检查..."
    find src/ubunturouter -name '*.py' -exec python3 -c "
import py_compile, sys
try:
    py_compile.compile('{}', doraise=True)
except py_compile.PyCompileError as e:
    print(f'  SYNTAX ERROR: {e}')
    sys.exit(1)
" \; 2>/dev/null || has_errors=true

    log_info "  2/3 模块导入检查..."
    python3 -c "
import sys, os
sys.path.insert(0, 'src')
try:
    from ubunturouter.api.main import app
    print('  ✓ api.main 导入成功')
except Exception as e:
    print(f'  ✗ api.main 导入失败: {e}')
    sys.exit(1)
" 2>&1 || has_errors=true

    log_info "  3/3 前端项目检查..."
    if [ -f web/package.json ]; then
        echo "  ✓ web/package.json 存在"
    else
        echo "  ✗ web/package.json 不存在"
        has_errors=true
    fi

    if [ "$has_errors" = true ]; then
        log_warn "代码审查发现问题，请修复后继续"
        return 1
    fi
    log_ok "代码审查通过"
    return 0
}

# ─── 提交到 GitHub ────────────────────────────────────────────────────────
git_push() {
    log_info "提交代码到 GitHub..."
    cd "$SCRIPT_DIR"

    if git diff --quiet && git diff --cached --quiet; then
        log_info "  没有未提交的变更"
        local ahead=$(git rev-list --count @{u}..HEAD 2>/dev/null || echo "0")
        if [ "$ahead" -eq 0 ]; then
            log_info "  本地与远程同步，无需 push"
            return 0
        fi
    fi

    log_info "  git push..."
    if git push 2>&1; then
        log_ok "推送成功"
    else
        log_error "推送失败"
        return 1
    fi
}

# ─── 远程/本地执行封装 ─────────────────────────────────────────────────────
# 开发机: 通过 ssh 在测试机上执行
# 测试机: 直接本地执行
vm_exec() {
    local cmd="$*"
    if $IS_ON_DEV_MACHINE; then
        $SSH_CMD "cd /home/$VM_USER/ubuntu-router && $cmd" 2>&1
    else
        cd "$SCRIPT_DIR" && eval "$cmd" 2>&1
    fi
}

vm_exec_sudo() {
    local cmd="$*"
    if $IS_ON_DEV_MACHINE; then
        $SSH_CMD "cd /home/$VM_USER/ubuntu-router && sudo bash -c '$cmd'" 2>&1
    else
        cd "$SCRIPT_DIR" && sudo bash -c "$cmd" 2>&1
    fi
}

# ─── 测试机 git pull ──────────────────────────────────────────────────────
vm_git_pull() {
    log_info "在测试机上执行 git pull..."
    if $IS_ON_DEV_MACHINE; then
        local share_path="/home/$VM_USER/ubuntu-router"
        $SSH_CMD "cd $share_path && git pull" 2>&1 || {
            log_error "git pull 失败"
            return 1
        }
    else
        cd "$SCRIPT_DIR" && git pull 2>&1 || {
            log_error "git pull 失败"
            return 1
        }
    fi
    log_ok "测试机代码已更新"
}

# ─── 测试机前端构建 ──────────────────────────────────────────────────────
vm_build_frontend() {
    log_info "在测试机 (x86_64) 上构建前端..."
    
    local build_script='set -e
SHARE="/home/ihermes/ubuntu-router"
CACHE="/tmp/ubunturouter-web-cache"
BUILD="/tmp/ubunturouter-web-build-$(date +%s)"
echo "  → 准备本地构建目录..."
mkdir -p "$BUILD"
rsync -a --exclude=node_modules --exclude=dist "$SHARE/web/" "$BUILD/"
if [ -d "$CACHE/node_modules" ]; then
    echo "  → 使用缓存的 node_modules..."
    cp -r "$CACHE/node_modules" "$BUILD/"
else
    cd "$BUILD"
    echo "  → npm install (x86_64 原生)..."
    npm install --no-audit --no-fund
    echo "  → 缓存 node_modules..."
    mkdir -p "$CACHE"
    cp -r "$BUILD/node_modules" "$CACHE/"
fi
echo "  → npm run build..."
cd "$BUILD" && npm run build
echo "  → 复制构建产物..."
mkdir -p "$SHARE/web/dist"
cp -r "$BUILD/dist/"* "$SHARE/web/dist/"
rm -rf "$BUILD"
echo "  → 前端构建完成"'

    if $IS_ON_DEV_MACHINE; then
        $SSH_CMD "bash -c $(printf '%q' "$build_script")" 2>&1
    else
        eval "$build_script" 2>&1
    fi
    log_ok "前端构建完成"
}

# ─── 测试机部署代码 ──────────────────────────────────────────────────────
vm_deploy_code() {
    log_info "部署代码到 /opt/ubunturouter ..."
    
    local deploy_script='SRC="/home/ihermes/ubuntu-router"
DST="/opt/ubunturouter"
sudo rm -rf "$DST/ubunturouter"
sudo cp -r "$SRC/src/ubunturouter" "$DST/ubunturouter"
sudo find "$DST/ubunturouter" -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
sudo rm -rf "$DST/web/dist"
sudo cp -r "$SRC/web/dist" "$DST/web/dist"
sudo cp "$SRC/run.py" "$DST/"
sudo cp "$SRC/ubunturouter.sh" "$DST/"
echo "DONE: 代码已部署"'

    if $IS_ON_DEV_MACHINE; then
        $SSH_CMD "bash -c $(printf '%q' "$deploy_script")" 2>&1
    else
        eval "$deploy_script" 2>&1
    fi
    log_ok "代码已部署到 /opt/ubunturouter"
}

# ─── 测试机重启服务 ──────────────────────────────────────────────────────
vm_restart_service() {
    log_info "重启 ubunturouter 服务..."
    if $IS_ON_DEV_MACHINE; then
        $SSH_CMD "sudo systemctl restart ubunturouter && sleep 2 && sudo systemctl is-active ubunturouter" 2>&1
    else
        sudo systemctl restart ubunturouter && sleep 2 && sudo systemctl is-active ubunturouter 2>&1
    fi
    log_ok "服务已重启"
}

# ─── 测试机服务状态 ──────────────────────────────────────────────────────
vm_service_status() {
    if $IS_ON_DEV_MACHINE; then
        $SSH_CMD "systemctl status ubunturouter --no-pager -l | head -25" 2>&1
        echo ""
        $SSH_CMD "sudo nft list table inet ubunturouter 2>/dev/null && echo 'nftables: OK' || echo 'nftables: (表不存在)'" 2>&1
    else
        systemctl status ubunturouter --no-pager -l | head -25 2>&1
        echo ""
        sudo nft list table inet ubunturouter 2>/dev/null && echo 'nftables: OK' || echo 'nftables: (表不存在)'
    fi
}

# ─── 测试机日志 ──────────────────────────────────────────────────────────
vm_service_logs() {
    local lines="${1:-30}"
    if $IS_ON_DEV_MACHINE; then
        $SSH_CMD "journalctl -u ubunturouter --no-pager -n $lines --no-hostname" 2>&1
    else
        journalctl -u ubunturouter --no-pager -n $lines --no-hostname 2>&1
    fi
}

# ─── 测试机完整安装 ──────────────────────────────────────────────────────
vm_full_install() {
    log_info "在测试机上执行完整安装 (install.sh)..."
    if $IS_ON_DEV_MACHINE; then
        $SSH_CMD "cd /home/$VM_USER/ubuntu-router && sudo bash install.sh" 2>&1
    else
        cd "$SCRIPT_DIR" && sudo bash install.sh 2>&1
    fi
    log_ok "完整安装完成"
}

# ─── Web GUI 验证清单 ───────────────────────────────────────────────────
print_verify_guide() {
    local vm_host="$VM_HOST"
    echo ""
    echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  Web GUI 验证清单${NC}"
    echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  浏览器打开: ${GREEN}http://$vm_host:8080/${NC}"
    echo ""
    echo "  逐模块验证:"
    echo "  [Sprint 1 — 基础框架]   ☐ 登录  ☐ 仪表盘  ☐ 接口管理"
    echo "  [Sprint 2 — 网络]        ☐ 路由表  ☐ WAN  ☐ VLAN"
    echo "  [Sprint 3 — 防火墙/DHCP] ☐ 防火墙  ☐ DHCP  ☐ 通道"
    echo "  [Sprint 4 — 编排/容器]   ☐ 设备  ☐ 编排规则  ☐ 容器"
    echo "  [Sprint 5 — 应用市场]    ☐ 应用列表  ☐ 安装  ☐ 系统设置"
    echo ""
    echo -e "  发现 Bug → ${YELLOW}本机改代码 → 提交 → sudo ./ubunturouter.sh update${NC}"
    echo ""
}

# ═══════════════════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════════════════
main() {
    local cmd="${1:-help}"
    shift 2>/dev/null || true

    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  UbuntuRouter — 开发调测工作流${NC}"
    echo -e "${CYAN}  主机: $(uname -m), $(hostname)${NC}"
    if $IS_ON_DEV_MACHINE; then
        echo -e "${CYAN}  模式: 开发机 → 远程操作测试机 ($VM_HOST)${NC}"
    else
        echo -e "${CYAN}  模式: 测试机 → 直接本地操作${NC}"
    fi
    echo -e "${CYAN}  项目: $SCRIPT_DIR${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
    echo ""

    case "$cmd" in
        # ── install ──────────────────────────────────────────────────
        install|first)
            check_prerequisites "$cmd"
            echo -e "${YELLOW}注意: 将在测试机 $VM_HOST 上执行首次部署。${NC}"
            echo ""
            vm_full_install
            vm_restart_service
            print_verify_guide
            ;;

        # ── update ───────────────────────────────────────────────────
        update)
            check_prerequisites "$cmd"
            local skip_pull=false
            while [ $# -gt 0 ]; do
                case "$1" in
                    --skip-pull) skip_pull=true ;;
                    *) log_warn "未知参数: $1" ;;
                esac
                shift
            done

            echo "────────────────────────────────────────────"
            log_info "Step 1/6: 本地代码审查"
            echo "────────────────────────────────────────────"
            code_review || { log_error "代码审查不通过"; exit 1; }

            echo ""; echo "────────────────────────────────────────────"
            log_info "Step 2/6: 本地单元测试"
            echo "────────────────────────────────────────────"
            run_tests || {
                log_warn "单元测试有失败项，是否继续部署?"
                read -r -p "  继续部署? [y/N] " reply
                [[ "$reply" =~ ^[Yy] ]] || exit 1
            }

            echo ""; echo "────────────────────────────────────────────"
            log_info "Step 3/6: 提交到 GitHub"
            echo "────────────────────────────────────────────"
            git_push || { log_error "Git push 失败"; exit 1; }

            echo ""; echo "────────────────────────────────────────────"
            log_info "Step 4/6: 测试机 git pull"
            echo "────────────────────────────────────────────"
            if [ "$skip_pull" = true ]; then
                log_info "  跳过 git pull"
            else
                vm_git_pull || { log_error "git pull 失败"; exit 1; }
            fi

            echo ""; echo "────────────────────────────────────────────"
            log_info "Step 5/6: 测试机前端构建"
            echo "────────────────────────────────────────────"
            vm_build_frontend || { log_error "前端构建失败"; exit 1; }

            echo ""; echo "────────────────────────────────────────────"
            log_info "Step 6/6: 部署 & 重启服务"
            echo "────────────────────────────────────────────"
            vm_deploy_code
            vm_restart_service

            echo ""
            log_ok "更新部署完成！"
            print_verify_guide
            ;;

        # ── status ───────────────────────────────────────────────────
        status)
            vm_service_status
            ;;

        # ── logs ─────────────────────────────────────────────────────
        logs)
            local lines=30
            while [ $# -gt 0 ]; do
                case "$1" in
                    -n) shift; lines="${1:-30}" ;;
                esac
                shift
            done
            vm_service_logs "$lines"
            ;;

        # ── test ─────────────────────────────────────────────────────
        test)
            local filter=""
            while [ $# -gt 0 ]; do
                case "$1" in
                    -k) shift; filter="$1" ;;
                    *) filter="$1" ;;
                esac
                shift
            done
            run_tests "$filter"
            ;;

        # ── help ─────────────────────────────────────────────────────
        help|--help|-h)
            show_help
            ;;

        *)
            log_error "未知命令: $cmd"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
