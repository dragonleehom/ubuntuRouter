"""App Store 更新/卸载 — 备份 → 拉取新镜像 → 重建 / 保留数据卸载"""

import os
import shutil
import json
import subprocess
from pathlib import Path
from typing import Optional, Dict

from .engine import (
    AppManifest, INSTALLED_DIR, DATA_DIR, REPOS_DIR,
    parse_manifest,
)
from .installer import precheck
from ..container import ComposeManager


BACKUP_DIR = Path("/opt/ubunturouter/apps/backups")


def _get_data_dir(app_id: str) -> Path:
    return DATA_DIR / app_id


def _backup_data(app_id: str) -> Optional[Path]:
    """备份应用数据"""
    data_dir = _get_data_dir(app_id)
    if not data_dir.exists():
        return None

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    import time
    ts = time.strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"{app_id}_{ts}.tar.gz"

    try:
        subprocess.run(
            ["tar", "czf", str(backup_path), "-C", str(data_dir.parent), app_id],
            capture_output=True, text=True, timeout=300,
        )
        return backup_path if backup_path.exists() else None
    except Exception:
        return None


def uninstall(app_id: str, keep_data: bool = True) -> Dict:
    """卸载应用（保留数据）"""
    installed_dir = INSTALLED_DIR / app_id
    if not installed_dir.exists():
        return {"success": False, "error": f"应用 '{app_id}' 未安装"}

    try:
        # 第 1 步: 停止并移除容器
        result = ComposeManager.down(str(installed_dir), volumes=False)
        if not result["success"]:
            # 即使 down 失败也继续清理
            pass

        # 第 2 步: 备份数据
        backup = None
        if not keep_data:
            backup = _backup_data(app_id)

        # 第 3 步: 删除软链接
        if installed_dir.is_symlink():
            installed_dir.unlink()
        elif installed_dir.is_dir():
            shutil.rmtree(installed_dir)

        # 第 4 步: 如果不保留数据，删除数据目录
        if not keep_data:
            data_dir = _get_data_dir(app_id)
            if data_dir.exists():
                shutil.rmtree(data_dir)

        return {
            "success": True,
            "app_id": app_id,
            "data_backup": str(backup) if backup else None,
            "data_kept": keep_data,
            "message": f"应用 '{app_id}' 已卸载",
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"卸载失败: {str(e)}",
        }


def update(app_id: str) -> Dict:
    """更新应用 — 备份 → 拉取新镜像 → 重建"""
    installed_dir = INSTALLED_DIR / app_id
    if not installed_dir.exists():
        return {"success": False, "error": f"应用 '{app_id}' 未安装"}

    try:
        # 第 1 步: 备份当前配置和数据
        backup = _backup_data(app_id)

        # 第 2 步: 同步对应仓库（获取最新 manifest）
        repo_updated = False
        for repo_dir in REPOS_DIR.iterdir():
            if not repo_dir.is_dir():
                continue
            app_src = repo_dir / app_id
            if app_src.exists() and (app_src / "app.yaml").exists():
                # 更新软链接指向
                if installed_dir.is_symlink():
                    installed_dir.unlink()
                os.symlink(str(app_src), str(installed_dir))
                repo_updated = True
                break

        # 第 3 步: 拉取最新镜像
        pull_result = ComposeManager.pull(str(installed_dir))
        if not pull_result["success"]:
            return {
                "success": False,
                "error": f"镜像拉取失败: {pull_result.get('error', '')}",
            }

        # 第 4 步: 重建容器
        up_result = ComposeManager.up(str(installed_dir), build=True)
        if not up_result["success"]:
            return {
                "success": False,
                "error": f"重建失败: {up_result.get('error', '')}",
            }

        # 读取新版本
        manifest = parse_manifest(installed_dir / "app.yaml")
        new_version = manifest.version if manifest else "unknown"

        return {
            "success": True,
            "app_id": app_id,
            "old_version": "unknown",
            "new_version": new_version,
            "backup": str(backup) if backup else None,
            "message": f"应用 '{app_id}' 已更新到 {new_version}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"更新失败: {str(e)}",
        }
