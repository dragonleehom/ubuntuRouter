#!/usr/bin/env bash
# ============================================================================
# 废弃 — 请使用 ubunturouter.sh 替代
# ============================================================================
# 
# 旧的 deploy.sh 已被 ubunturouter.sh 取代。
# 新脚本统一了 install/update/status/logs/test 所有操作。
#
# 迁移:
#   ./deploy.sh            →  sudo ./ubunturouter.sh update
#   ./deploy.sh --skip-build  →  sudo ./ubunturouter.sh update --skip-pull
#   ./deploy.sh --full        →  sudo ./ubunturouter.sh install
#   ./deploy.sh --status      →  sudo ./ubunturouter.sh status
#   ./deploy.sh --logs        →  sudo ./ubunturouter.sh logs
# ============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/ubunturouter.sh" "$@"
