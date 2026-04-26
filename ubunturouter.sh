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

# ─── 帮助信息 ──────────────────────────────────────────────────────────────
show_help() {
    echo ""
    echo "UbuntuRouter — 开发调测工作流"
    echo ""
    echo "用法: sudo ./$SCRIPT_NAME <命令> [选项]"
    echo ""
    echo "命令:"
    echo "  install              首次部署: 依赖安装 + 构建 + 部署 + 启动"
    echo "  update               更新部署: git pull + 构建 + 部署 + 重启"
    echo "  status               查看服务状态"
    echo "  logs [-n <行数>]     查看日志 (默认 30 行)"
    echo "  test [模块]          运行本地单元测试 (pytest)"
    echo "  help                 显示此帮助"
    echo ""
    echo "选项:"
    echo "  -y, --yes            跳过所有确认提示"
    echo "  --skip-pull          跳过 git pull（仅 update 时有效）"
    echo ""
    echo "示例:"
    echo "  sudo ./$SCRIPT_NAME install          # 首次部署"
    echo "  sudo ./$SCRIPT_NAME update           # 更新并部署"
    echo "  ./$SCRIPT_NAME test                  # 运行全部单元测试"
    echo "  ./$SCRIPT_NAME test firewall         # 运行防火墙模块测试"
    echo "  sudo ./$SCRIPT_NAME logs -n 50       # 查看 50 行日志"
    echo ""
}

# ─── 前置检查 ──────────────────────────────────────────────────────────────
check_prerequisites() {
    log_info "检查前置依赖..."

    # 必须 root 权限（写 /opt/ubunturouter）
    if [ "$EUID" -ne 0 ]; then
        # 如果是 update/test/status/logs 且非 root，尝试提权
        case "${1:-}" in
            install|first)
                log_error "install 命令需要 root 权限，请使用 sudo"
                exit 1
                ;;
        esac
    fi

    local missing=()
    command -v git    >/dev/null 2>&1 || missing+=("git")
    command -v python3 >/dev/null 2>&1 || missing+=("python3")

    if [ ${#missing[@]} -gt 0 ]; then
        log_error "缺少系统依赖: ${missing[*]}"
        log_info "请先安装: sudo apt install -y ${missing[*]}"
        exit 1
    fi

    log_ok "前置检查通过 (git + python3 可用)"
}

# ─── 运行本地单元测试 ──────────────────────────────────────────────────────
run_tests() {
    local test_filter="${1:-}"
    log_info "运行本地单元测试..."

    cd "$SCRIPT_DIR"

    local VENV="$SCRIPT_DIR/.venv"

    # 执行策略: 如果 tests/ 下有 __init__.py 则用 pytest，否则直接 python3 运行
    local HAS_PYTEST=false
    if [ -f "$SCRIPT_DIR/tests/__init__.py" ] || [ -d "$SCRIPT_DIR/tests/__pycache__" ]; then
        # 尝试查找 pytest
        if command -v pytest >/dev/null 2>&1; then
            HAS_PYTEST=true
        elif [ -f "$VENV/bin/pytest" ]; then
            HAS_PYTEST=true
            alias pytest="$VENV/bin/pytest"
        elif python3 -m pytest --version >/dev/null 2>&1; then
            HAS_PYTEST=true
        fi
    fi

    cd "$SCRIPT_DIR"

    if [ -n "$test_filter" ]; then
        log_info "  过滤模块: $test_filter"
        if $HAS_PYTEST; then
            PYTHONPATH=src python3 -m pytest "tests/" -k "$test_filter" -v --tb=short \
                --no-header -q -o pythonpath=src 2>&1 || true
        else
            log_warn "  pytest 不可用, 尝试直接运行测试脚本..."
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
            # 没有 pytest 则直接顺序运行 test_*.py
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

# ─── 本地代码检查（提交前运行）────────────────────────────────────────────
code_review() {
    log_info "执行本地代码审查..."

    cd "$SCRIPT_DIR"
    local has_errors=false

    # 1. Python 语法检查
    log_info "  1/3 Python 语法检查..."
    find src/ubunturouter -name '*.py' -exec python3 -c "
import py_compile, sys
try:
    py_compile.compile('{}', doraise=True)
except py_compile.PyCompileError as e:
    print(f'  SYNTAX ERROR: {e}')
    sys.exit(1)
" \; 2>/dev/null || has_errors=true

    # 2. Python 导入检查（确认无环依赖）
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

    # 3. 前端项目完整性
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

# ─── 本地提交到 GitHub ────────────────────────────────────────────────────
git_push() {
    log_info "提交代码到 GitHub..."
    cd "$SCRIPT_DIR"

    # 检查是否有未提交的变更
    if git diff --quiet && git diff --cached --quiet; then
        log_info "  没有未提交的变更"
        # 检查是否有已暂存的变更
        if git diff --cached --quiet; then
            # 完全没有变更，检查是否有未 push 的 commit
            local behind=$(git rev-list --count HEAD..@{u} 2>/dev/null || echo "0")
            local ahead=$(git rev-list --count @{u}..HEAD 2>/dev/null || echo "0")
            if [ "$ahead" -eq 0 ]; then
                log_info "  本地与远程同步，无需 push"
                return 0
            fi
        fi
    fi

    # 检查是否有 stash
    if git stash list | grep -q .; then
        log_warn "  存在 stash 记录，建议先处理"
    fi

    # 自动 add + commit（如果没有暂存的变更）
    if git diff --quiet && git diff --cached --quiet; then
        log_info "  没有暂存的变更，跳过 commit"
        return 0
    fi

    # Push
    log_info "  git push..."
    if git push 2>&1; then
        log_ok "推送成功"
    else
        log_error "推送失败，请检查网络和权限"
        return 1
    fi
}

# ─── 测试机 git pull ──────────────────────────────────────────────────────
vm_git_pull() {
    local vm_host="192.168.100.194"
    local vm_user="ihermes"
    local share_path="/home/ihermes/ubuntu-router"
    local vm_ssh="sshpass -p dragon88 ssh -o StrictHostKeyChecking=no $vm_user@$vm_host"

    log_info "在测试机 ($vm_host) 上执行 git pull..."
    $vm_ssh "cd $share_path && git pull" 2>&1 || {
        log_error "git pull 失败"
        return 1
    }
    log_ok "测试机代码已更新"
}

# ─── 测试机前端构建 ──────────────────────────────────────────────────────
vm_build_frontend() {
    local vm_host="192.168.100.194"
    local vm_user="ihermes"
    local vm_ssh="sshpass -p dragon88 ssh -o StrictHostKeyChecking=no $vm_user@$vm_host"

    log_info "在测试机 (x86_64) 上构建前端..."
    $vm_ssh <<'REMOTE'
        set -e
        SHARE=/home/ihermes/ubuntu-router
        CACHE=/tmp/ubunturouter-web-cache
        BUILD=/tmp/ubunturouter-web-build-$(date +%s)

        echo "  → 准备本地构建目录..."
        mkdir -p "$BUILD"

        # 从共享目录复制 web 源码
        rsync -a --exclude='node_modules' --exclude='dist' "$SHARE/web/" "$BUILD/"

        # 复用缓存的 node_modules
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

        # 构建
        echo "  → npm run build..."
        cd "$BUILD" && npm run build

        # 产物复制回共享目录
        echo "  → 复制构建产物..."
        mkdir -p "$SHARE/web/dist"
        cp -r "$BUILD/dist/"* "$SHARE/web/dist/"
        rm -rf "$BUILD"
        echo "  → 前端构建完成"
REMOTE
    log_ok "前端构建完成"
}

# ─── 测试机部署代码 ──────────────────────────────────────────────────────
vm_deploy_code() {
    local vm_host="192.168.100.194"
    local vm_user="ihermes"
    local vm_ssh="sshpass -p dragon88 ssh -o StrictHostKeyChecking=no $vm_user@$vm_host"

    log_info "部署代码到 /opt/ubunturouter ..."
    $vm_ssh <<'REMOTE'
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

        # 脚本文件
        sudo cp "$SRC/run.py" "$DST/"
        sudo cp "$SRC/ubunturouter.sh" "$DST/"

        echo "DONE: 代码已部署"
REMOTE
    log_ok "代码已部署到 /opt/ubunturouter"
}

# ─── 测试机重启服务 ──────────────────────────────────────────────────────
vm_restart_service() {
    local vm_host="192.168.100.194"
    local vm_user="ihermes"
    local vm_ssh="sshpass -p dragon88 ssh -o StrictHostKeyChecking=no $vm_user@$vm_host"

    log_info "重启 ubunturouter 服务..."
    $vm_ssh "sudo systemctl restart ubunturouter && sleep 2 && sudo systemctl is-active ubunturouter" 2>&1
    log_ok "服务已重启"
}

# ─── 测试机服务状态 ──────────────────────────────────────────────────────
vm_service_status() {
    local vm_host="192.168.100.194"
    local vm_user="ihermes"
    local vm_ssh="sshpass -p dragon88 ssh -o StrictHostKeyChecking=no $vm_user@$vm_host"

    $vm_ssh "systemctl status ubunturouter --no-pager -l | head -25" 2>&1
    echo ""
    $vm_ssh "sudo nft list table inet ubunturouter 2>/dev/null && echo 'nftables: OK' || echo 'nftables: (表不存在)'" 2>&1
}

# ─── 测试机日志 ──────────────────────────────────────────────────────────
vm_service_logs() {
    local lines="${1:-30}"
    local vm_host="192.168.100.194"
    local vm_user="ihermes"
    local vm_ssh="sshpass -p dragon88 ssh -o StrictHostKeyChecking=no $vm_user@$vm_host"

    $vm_ssh "journalctl -u ubunturouter --no-pager -n $lines --no-hostname" 2>&1
}

# ─── 测试机完整安装（首次） ──────────────────────────────────────────────
vm_full_install() {
    local vm_host="192.168.100.194"
    local vm_user="ihermes"
    local vm_ssh="sshpass -p dragon88 ssh -o StrictHostKeyChecking=no $vm_user@$vm_host"

    log_info "在测试机上执行完整安装 (install.sh)..."
    $vm_ssh "cd /home/ihermes/ubuntu-router && sudo bash install.sh" 2>&1
    log_ok "完整安装完成"
}

# ─── WEB 浏览器验证（开发机） ────────────────────────────────────────────
# 说明：验证需在本机浏览器中手动完成，这里仅打印验证清单
print_verify_guide() {
    local vm_host="192.168.100.194"
    echo ""
    echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  Web GUI 验证清单${NC}"
    echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  浏览器打开: ${GREEN}http://$vm_host:8080/${NC}"
    echo ""
    echo "  逐模块验证（按 Sprint 顺序）:"
    echo ""
    echo "  [Sprint 1 — 基础框架]"
    echo "    ☐ 登录页: 密码认证正常"
    echo "    ☐ 仪表盘: 系统概览数据正确"
    echo "    ☐ 接口管理: 显示网口列表、角色、状态"
    echo ""
    echo "  [Sprint 2 — 网络]"
    echo "    ☐ 路由表: 显示正确"
    echo "    ☐ WAN 设置: DHCP/静态配置正常"
    echo "    ☐ VLAN 管理: 创建/删除 VLAN"
    echo ""
    echo "  [Sprint 3 — 防火墙/DHCP/通道]"
    echo "    ☐ 防火墙: Zones/端口转发规则"
    echo "    ☐ DHCP: 租约列表/静态绑定"
    echo "    ☐ 通道: WireGuard/Tailscale 状态"
    echo ""
    echo "  [Sprint 4 — 流量编排/容器]"
    echo "    ☐ 设备列表: 自动识别"
    echo "    ☐ 编排规则: 创建/编辑/删除"
    echo "    ☐ 容器管理: 列表/详情"
    echo ""
    echo "  [Sprint 5 — 应用市场/系统]"
    echo "    ☐ 应用市场: 列表/详情/安装"
    echo "    ☐ 系统设置: 主题/语言/时区"
    echo "    ☐ 系统更新: 检查更新"
    echo ""
    echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  部署成功后，请逐一勾选上述验证项。"
    echo -e "  发现 Bug → ${YELLOW}本机修改代码 → 提交 → update → 重测${NC}"
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
    echo -e "${CYAN}  项目: $SCRIPT_DIR${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
    echo ""

    case "$cmd" in
        # ── install ──────────────────────────────────────────────────
        install|first)
            check_prerequisites "$cmd"
            echo -e "${YELLOW}注意: install 将在测试机 $VM_HOST 上执行首次部署。${NC}"
            echo -e "${YELLOW}      确认测试机已就绪?${NC}"
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

            # Step 1: 本地代码检查 + 单元测试
            echo "────────────────────────────────────────────"
            log_info "Step 1/6: 本地代码审查"
            echo "────────────────────────────────────────────"
            code_review || {
                log_error "代码审查不通过，请修复后重试"
                exit 1
            }

            echo ""
            echo "────────────────────────────────────────────"
            log_info "Step 2/6: 本地单元测试"
            echo "────────────────────────────────────────────"
            run_tests || {
                log_warn "单元测试有失败项，是否继续部署?"
                read -r -p "  继续部署? [y/N] " reply
                [[ "$reply" =~ ^[Yy] ]] || exit 1
            }

            # Step 2: 提交 GitHub
            echo ""
            echo "────────────────────────────────────────────"
            log_info "Step 3/6: 提交到 GitHub"
            echo "────────────────────────────────────────────"
            git_push || {
                log_error "Git 提交失败"
                exit 1
            }

            # Step 3: 测试机 pull
            echo ""
            echo "────────────────────────────────────────────"
            log_info "Step 4/6: 测试机 git pull"
            echo "────────────────────────────────────────────"
            if [ "$skip_pull" = true ]; then
                log_info "  跳过 git pull (--skip-pull)"
            else
                vm_git_pull || {
                    log_error "测试机 git pull 失败"
                    exit 1
                }
            fi

            # Step 4: 测试机构建前端
            echo ""
            echo "────────────────────────────────────────────"
            log_info "Step 5/6: 测试机前端构建"
            echo "────────────────────────────────────────────"
            vm_build_frontend || {
                log_error "前端构建失败"
                exit 1
            }

            # Step 5: 部署 + 重启
            echo ""
            echo "────────────────────────────────────────────"
            log_info "Step 6/6: 部署 & 重启服务"
            echo "────────────────────────────────────────────"
            vm_deploy_code
            vm_restart_service

            # 完成
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
                    *) ;;
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
