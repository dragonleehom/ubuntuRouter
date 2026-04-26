#!/usr/bin/env bash
# ============================================================================
# UbuntuRouter 一键安装脚本
# 作用: 检查依赖 → 安装 Python 包 → 构建前端 → 部署到 /opt/ubunturouter → 启动服务
# 用法: sudo bash install.sh
# ============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/ubunturouter"

# ============================================================================
# 第 1 步: sudo 检查
# ============================================================================
if [ "$(id -u)" -ne 0 ]; then
    log_error "请以 root 运行: sudo bash $0"
    exit 1
fi
log_info "UbuntuRouter 一键安装开始..."
echo ""

# ============================================================================
# 第 2 步: 系统依赖检查 & 安装
# ============================================================================
log_info "检查系统依赖..."
MISSING_PKGS=()

if ! command -v python3 &>/dev/null; then MISSING_PKGS+=(python3); fi
if ! command -v pip3   &>/dev/null; then MISSING_PKGS+=(python3-pip); fi
if ! command -v node   &>/dev/null; then MISSING_PKGS+=(nodejs); fi
if ! command -v npm    &>/dev/null; then MISSING_PKGS+=(npm); fi

# 检查 python3-venv（Debian/Ubuntu 需要额外安装）
python3 -c "import ensurepip" 2>/dev/null || MISSING_PKGS+=(python3-venv)
python3 -c "import venv" 2>/dev/null     || MISSING_PKGS+=(python3-venv)

if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
    log_warn "安装缺失系统包: ${MISSING_PKGS[*]}"
    apt-get update -qq
    apt-get install -y -qq "${MISSING_PKGS[@]}"
    log_ok "系统包安装完成"
else
    log_ok "所有系统依赖已就绪"
fi

# 确保 nftables 和 dnsmasq 已安装
INSTALL_RUNTIME=()
for pkg in nftables dnsmasq conntrack; do
    if ! dpkg -l "$pkg" &>/dev/null 2>&1; then
        INSTALL_RUNTIME+=("$pkg")
    fi
done
if [ ${#INSTALL_RUNTIME[@]} -gt 0 ]; then
    log_warn "安装运行时依赖: ${INSTALL_RUNTIME[*]}"
    apt-get install -y -qq "${INSTALL_RUNTIME[@]}"
fi

# 确保 nftables 服务启用
systemctl enable nftables 2>/dev/null || true

# 打印版本
for bin in python3 pip3 node npm; do
    if command -v "$bin" &>/dev/null; then
        log_ok "$bin: $($bin --version 2>&1 | head -1)"
    fi
done

# ============================================================================
# 第 3 步: Python 虚拟环境 & 安装依赖
# ============================================================================
log_info ""
log_info "创建 Python 虚拟环境..."

PYTHON_DEPS=(
    "fastapi>=0.100.0"
    "uvicorn[standard]>=0.22.0"
    "pydantic>=2.0.0"
    "pydantic-yaml"
    "python-multipart"
    "python-pam"
    "pyjwt"
    "psutil"
    "netifaces"
    "pyyaml"
    "websockets"
)

mkdir -p "$INSTALL_DIR"
python3 -m venv "$INSTALL_DIR/venv"
log_ok "虚拟环境已创建: $INSTALL_DIR/venv"

"$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install --quiet "${PYTHON_DEPS[@]}"
log_ok "Python 依赖安装完成"

# ============================================================================
# 第 4 步: 构建 Vue3 前端
# ============================================================================
log_info ""
log_info "构建 Vue3 前端..."

if [ -f "$SCRIPT_DIR/web/package.json" ]; then
    cd "$SCRIPT_DIR/web"
    if [ ! -d "node_modules" ]; then
        npm install --quiet 2>&1 | tail -5
    fi
    npm run build 2>&1 | tail -10
    log_ok "前端构建完成"
else
    log_error "未找到 $SCRIPT_DIR/web/package.json"
    exit 1
fi

# ============================================================================
# 第 5 步: 部署到 /opt/ubunturouter
# ============================================================================
log_info ""
log_info "部署到 $INSTALL_DIR..."

# Python 代码
mkdir -p "$INSTALL_DIR/ubunturouter"
cp -r "$SCRIPT_DIR/src/ubunturouter/"* "$INSTALL_DIR/ubunturouter/"
log_ok "Python 代码已部署"

# 前端静态文件
mkdir -p "$INSTALL_DIR/web/dist"
cp -r "$SCRIPT_DIR/web/dist/"* "$INSTALL_DIR/web/dist/"
log_ok "前端静态文件已部署"

# 复制安装脚本备份
cp "$SCRIPT_DIR/install.sh" "$INSTALL_DIR/"

# JWT 密钥目录
mkdir -p /etc/ubunturouter
chmod 750 /etc/ubunturouter
log_ok "配置目录已创建"

# ============================================================================
# 第 6 步: 创建 systemd 服务
# ============================================================================
log_info ""
log_info "创建 systemd 服务..."

cat > /etc/systemd/system/ubunturouter.service <<'SERVICEEOF'
[Unit]
Description=UbuntuRouter Service
Documentation=https://github.com/your-repo/ubuntu-router
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/ubunturouter
Environment=PYTHONPATH=/opt/ubunturouter
ExecStart=/opt/ubunturouter/venv/bin/uvicorn ubunturouter.api.main:app \
    --host 0.0.0.0 \
    --port 8080 \
    --workers 2 \
    --proxy-headers \
    --forwarded-allow-ips='*'
Restart=always
RestartSec=5
StartLimitInterval=60s
StartLimitBurst=3

[Install]
WantedBy=multi-user.target
SERVICEEOF

systemctl daemon-reload
systemctl enable ubunturouter.service
log_ok "systemd 服务已创建并启用"

# ============================================================================
# 第 7 步: 启动服务
# ============================================================================
log_info ""
log_info "启动 UbuntuRouter 服务..."

systemctl restart ubunturouter.service
sleep 3

if systemctl is-active --quiet ubunturouter.service; then
    log_ok "UbuntuRouter 服务已启动 (active)"
else
    log_warn "服务启动异常，查看日志:"
    journalctl -u ubunturouter.service --no-pager -n 20
    exit 1
fi

# ============================================================================
# 第 8 步: 验证 API 响应
# ============================================================================
log_info ""
log_info "验证 API 服务..."

sleep 2
HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/ 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    log_ok "Web GUI 可访问: http://localhost:8080/"
else
    log_warn "Web GUI 返回状态码: $HTTP_CODE"
    log_warn "检查日志: journalctl -u ubunturouter.service -f"
fi

# ============================================================================
# 完成
# ============================================================================
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  UbuntuRouter 安装完成!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "  安装路径:     $INSTALL_DIR"
echo "  服务管理:     systemctl status ubunturouter"
echo "  查看日志:     journalctl -u ubunturouter -f"
echo "  Web GUI:      http://$(hostname -I | awk '{print $1}'):8080/"
echo "  CLI 工具:     $INSTALL_DIR/venv/bin/python -m ubunturouter.cli.main"
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
