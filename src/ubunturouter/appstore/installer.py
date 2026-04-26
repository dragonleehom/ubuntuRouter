"""App Store 安装编排 — 预检 → 部署 → 健康检查"""

import os
import shutil
import json
import time
from pathlib import Path
from typing import Optional, Dict, Callable

from .engine import (
    AppManifest, INSTALLED_DIR, DATA_DIR, parse_manifest
)
from ..container import ContainerManager, ComposeManager


def _get_compose_dir(app_id: str) -> Path:
    """获取已安装应用的 compose 目录"""
    return INSTALLED_DIR / app_id


def _get_data_dir(app_id: str) -> Path:
    """获取应用数据持久化目录"""
    data_dir = DATA_DIR / app_id
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def precheck(manifest: AppManifest) -> Dict:
    """安装前预检"""
    issues = []

    # 检查是否已安装
    installed_dir = _get_compose_dir(manifest.id)
    if installed_dir.exists():
        issues.append(f"应用 '{manifest.id}' 已安装")

    # 检查端口冲突
    import socket
    for port_cfg in manifest.ports:
        host_port = port_cfg.get("host_port", 0)
        if host_port and host_port > 0:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(("127.0.0.1", host_port))
            sock.close()
            if result == 0:
                issues.append(f"端口 {host_port} 已被占用")

    # 检查依赖
    for dep in manifest.requires:
        dep_dir = _get_compose_dir(dep)
        if not dep_dir.exists():
            issues.append(f"依赖应用 '{dep}' 未安装")

    return {
        "app_id": manifest.id,
        "passed": len(issues) == 0,
        "issues": issues,
    }


def install(manifest: AppManifest, env_override: Optional[Dict] = None,
            progress_callback: Optional[Callable] = None) -> Dict:
    """安装应用"""
    app_id = manifest.id
    source_dir = Path(manifest.path)

    if not source_dir.exists():
        return {"success": False, "error": f"应用源目录不存在: {source_dir}"}

    def progress(step, msg):
        if progress_callback:
            progress_callback({"app_id": app_id, "step": step, "message": msg})

    try:
        progress(0, "开始安装...")

        # 第 1 步: 预检
        check = precheck(manifest)
        if not check["passed"]:
            return {
                "success": False,
                "error": f"预检未通过: {'; '.join(check['issues'])}",
                "issues": check["issues"],
            }
        progress(10, "预检通过")

        # 第 2 步: 创建应用目录（软链接到安装目录）
        INSTALLED_DIR.mkdir(parents=True, exist_ok=True)
        target_dir = INSTALLED_DIR / app_id

        if not target_dir.exists():
            os.symlink(str(source_dir), str(target_dir))
        progress(20, "目录已创建")

        # 第 3 步: 写入 .env 文件（用户自定义环境变量）
        env_path = target_dir / ".env"
        if env_override:
            env_lines = []
            for key, value in env_override.items():
                env_lines.append(f"{key}={value}")
            env_path.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
            progress(30, "环境变量已配置")

        # 第 4 步: 创建数据目录
        _get_data_dir(app_id)
        progress(40, "数据目录已创建")

        # 第 5 步: 执行 pre_install 脚本
        if manifest.pre_install:
            import subprocess
            script_path = target_dir / manifest.pre_install
            if script_path.exists():
                r = subprocess.run(
                    ["bash", str(script_path)],
                    capture_output=True, text=True, timeout=120,
                    env={**os.environ, "APP_DATA_DIR": str(_get_data_dir(app_id))},
                )
                if r.returncode != 0:
                    raise RuntimeError(f"pre-install 脚本失败: {r.stderr}")
            progress(50, "预安装脚本完成")

        # 第 6 步: docker compose pull (拉取镜像)
        progress(60, "拉取镜像...")
        pull_result = ComposeManager.pull(str(target_dir))
        if not pull_result["success"] and "not found" not in pull_result.get("error", "").lower():
            # 镜像拉取失败但可能是网络问题，继续尝试
            progress(65, "镜像拉取中（部分失败，继续尝试）")

        # 第 7 步: docker compose up -d
        progress(80, "启动应用...")
        up_result = ComposeManager.up(str(target_dir))
        if not up_result["success"]:
            # 清理
            if target_dir.is_symlink():
                target_dir.unlink()
            return {
                "success": False,
                "error": f"部署失败: {up_result.get('error', '')}",
                "output": up_result.get("output", ""),
            }
        progress(90, "应用已启动")

        # 第 8 步: 执行 post_install 脚本
        if manifest.post_install:
            import subprocess
            script_path = target_dir / manifest.post_install
            if script_path.exists():
                r = subprocess.run(
                    ["bash", str(script_path)],
                    capture_output=True, text=True, timeout=120,
                    env={**os.environ, "APP_DATA_DIR": str(_get_data_dir(app_id))},
                )
                if r.returncode != 0:
                    # 不阻塞安装流程
                    progress(95, f"post-install 脚本警告: {r.stderr}")
            progress(95, "后安装脚本完成")

        progress(100, "安装完成")

        return {
            "success": True,
            "app_id": app_id,
            "version": manifest.version,
            "message": f"应用 '{manifest.name}' 安装成功",
        }

    except Exception as e:
        # 安装失败时清理
        target_dir = INSTALLED_DIR / app_id
        if target_dir.is_symlink():
            try:
                target_dir.unlink()
            except OSError:
                pass
        return {
            "success": False,
            "error": str(e),
        }
