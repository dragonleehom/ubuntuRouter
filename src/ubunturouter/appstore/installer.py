"""App Store 安装编排 — 预检 → 部署 → 健康检查 → 失败回滚"""

import os
import shutil
import socket
import subprocess
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


def _check_port_available(host_port: int) -> bool:
    """检查端口是否可用"""
    if not host_port or host_port <= 0:
        return True
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(("127.0.0.1", host_port))
        sock.close()
        return result != 0
    except Exception:
        return True


def precheck(manifest: AppManifest) -> Dict:
    """安装前预检"""
    issues = []

    # 检查是否已安装
    installed_dir = _get_compose_dir(manifest.id)
    if installed_dir.exists():
        issues.append(f"应用 '{manifest.id}' 已安装")

    # 检查 Docker 是否可用
    try:
        r = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode != 0:
            issues.append("Docker 不可用或未运行")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        issues.append("Docker 不可用或未运行")

    # 检查端口冲突
    for port_cfg in manifest.ports:
        host_port = port_cfg.get("host_port", 0)
        if not _check_port_available(host_port):
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


class InstallRollback:
    """安装回滚上下文管理器

    记录安装过程中的每步操作，失败时按逆序清理。
    """

    def __init__(self, app_id: str):
        self.app_id = app_id
        self._steps: list = []  # [(description, cleanup_callable), ...]

    def record(self, description: str, cleanup: Optional[Callable] = None):
        """记录一个步骤，可选清理函数"""
        self._steps.append((description, cleanup))

    def rollback(self):
        """逆序执行所有清理操作"""
        for desc, cleanup in reversed(self._steps):
            if cleanup:
                try:
                    cleanup()
                except Exception as e:
                    print(f"  [回滚警告] {desc}: {e}")


def install(manifest: AppManifest, env_override: Optional[Dict] = None,
            progress_callback: Optional[Callable] = None) -> Dict:
    """安装应用 — 带完整回滚

    安装流程:
    0. 预检 → 1. 创建目录 → 2. 写 .env → 3. 创建数据目录
    → 4. pre_install 脚本 → 5. docker compose pull → 6. docker compose up
    → 7. post_install 脚本 → 8. 健康检查

    任意步骤失败 → 逆序回滚清理
    """
    app_id = manifest.id
    source_dir = Path(manifest.path)
    rollback = InstallRollback(app_id)

    if not source_dir.exists():
        return {"success": False, "error": f"应用源目录不存在: {source_dir}"}

    def progress(step, msg):
        if progress_callback:
            progress_callback({"app_id": app_id, "step": step, "message": msg})

    try:
        progress(0, "开始安装...")

        # ── 第 0 步: 预检 ──
        check = precheck(manifest)
        if not check["passed"]:
            return {
                "success": False,
                "error": f"预检未通过: {'; '.join(check['issues'])}",
                "issues": check["issues"],
            }
        progress(10, "预检通过")

        # ── 第 1 步: 创建安装目录（软链接到源） ──
        INSTALLED_DIR.mkdir(parents=True, exist_ok=True)
        target_dir = INSTALLED_DIR / app_id

        if not target_dir.exists():
            os.symlink(str(source_dir), str(target_dir))
            rollback.record("创建安装目录", lambda: target_dir.unlink() if target_dir.is_symlink() else None)
        elif not target_dir.is_symlink() and not target_dir.is_dir():
            return {"success": False, "error": f"安装路径 '{target_dir}' 已存在且非目录"}
        progress(20, "目录已创建")

        # ── 第 2 步: 写入 .env 文件（含默认值 + 用户覆盖 + 自动补全） ──
        env_path = target_dir / ".env"

        # 2a. 先从 manifest.env_vars 提取默认值
        env_defaults = {}
        for var in manifest.env_vars:
            key = var.get("name", "")
            default = var.get("default", "")
            if key:
                env_defaults[key] = default

        # 2b. 用户覆盖值
        if env_override:
            env_defaults.update(env_override)

        # 2c. 自动补全 1Panel 的 CONTAINER_NAME（docker-compose.yml 中必用）
        if "CONTAINER_NAME" not in env_defaults:
            env_defaults["CONTAINER_NAME"] = f"ubunturouter-{app_id}"

        # 2d. 扫描 compose 中引用的所有变量，自动生成未提供的 PANEL_* 和默认值
        compose_path = source_dir / manifest.compose_file
        if compose_path.exists():
            _auto_fill_required_env(compose_path, env_defaults, app_id)

        # 2e. 写入 .env
        if env_defaults:
            env_lines = []
            for key, value in env_defaults.items():
                env_lines.append(f"{key}={value}")
            env_path.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
            rollback.record("写入 .env", lambda: env_path.unlink() if env_path.exists() else None)
            progress(30, "环境变量已配置")

        # ── 第 3 步: 创建数据目录 ──
        data_dir = _get_data_dir(app_id)
        rollback.record("创建数据目录", lambda: shutil.rmtree(data_dir, ignore_errors=True) if data_dir.exists() else None)
        progress(40, "数据目录已创建")

        # ── 第 4 步: 执行 pre_install 脚本 ──
        if manifest.pre_install:
            script_path = source_dir / manifest.pre_install
            if script_path.exists():
                r = subprocess.run(
                    ["bash", str(script_path)],
                    capture_output=True, text=True, timeout=120,
                    env={**os.environ, "APP_DATA_DIR": str(data_dir)},
                )
                if r.returncode != 0:
                    raise RuntimeError(f"pre-install 脚本失败: {r.stderr[:500]}")
            progress(50, "预安装脚本完成")

        # ── 第 5 步: docker compose pull ──
        progress(60, "拉取镜像...")
        pull_result = ComposeManager.pull(str(source_dir))
        if not pull_result["success"]:
            error_msg = pull_result.get("error", "")
            # "not found" 可能是网络问题或镜像不存在
            progress(65, f"镜像拉取警告: {error_msg[:100]}")
        progress(70, "镜像就绪")

        # ── 第 6 步: docker compose up -d ──
        progress(80, "启动应用...")
        up_result = ComposeManager.up(str(source_dir))
        if not up_result["success"]:
            raise RuntimeError(f"部署失败: {up_result.get('error', '')}")

        # 记录: 如果回滚则 docker compose down
        def _compose_down():
            ComposeManager.down(str(source_dir), volumes=False)
        rollback.record("docker compose up", _compose_down)
        progress(90, "应用已启动")

        # ── 第 7 步: 执行 post_install 脚本 ──
        if manifest.post_install:
            script_path = source_dir / manifest.post_install
            if script_path.exists():
                r = subprocess.run(
                    ["bash", str(script_path)],
                    capture_output=True, text=True, timeout=120,
                    env={**os.environ, "APP_DATA_DIR": str(data_dir)},
                )
                if r.returncode != 0:
                    progress(95, f"post-install 脚本警告: {r.stderr[:200]}")
            progress(95, "后安装脚本完成")

        # ── 第 8 步: 健康检查 ──
        progress(96, "健康检查...")
        health_check_result = _health_check(manifest, target_dir)
        if not health_check_result.get("healthy", True):
            raise RuntimeError(f"健康检查失败: {health_check_result.get('error', '')}")
        progress(98, "健康检查通过")

        progress(100, "安装完成")

        return {
            "success": True,
            "app_id": app_id,
            "version": manifest.version,
            "message": f"应用 '{manifest.name}' 安装成功",
        }

    except Exception as e:
        error_msg = str(e)

        # ── 回滚所有已执行步骤 ──
        rollback.rollback()

        # 清理目标目录 symlink（如果 rollback 未处理）
        target_dir = INSTALLED_DIR / app_id
        if target_dir.is_symlink():
            try:
                target_dir.unlink()
            except OSError:
                pass

        return {
            "success": False,
            "error": error_msg,
        }


def _auto_fill_required_env(compose_path: Path, env_dict: dict, app_id: str):
    """Auto-fill missing env variables referenced in docker-compose.yml.

    1Panel apps use $PANEL_APP_PORT_HTTP, $PANEL_* variables that may not be
    defined in data.yml but are required by docker-compose.yml.
    Scans for ${VAR_NAME} references and generates reasonable defaults.
    """
    import re
    try:
        content = compose_path.read_text(encoding="utf-8")
        refs = set(re.findall(r'\$\{(\w+)\}', content))
        if not refs:
            return

        for ref in refs:
            if ref not in env_dict or env_dict[ref] == "":
                if ref == "PANEL_APP_PORT_HTTP":
                    env_dict[ref] = "8181"
                    _try_find_available_port(env_dict, ref)
                elif ref == "PANEL_TORRENTING_PORT":
                    env_dict[ref] = "48181"
                    _try_find_available_port(env_dict, ref)
                elif ref == "PANEL_APP_PORT_HTTPS":
                    env_dict[ref] = "8443"
                    _try_find_available_port(env_dict, ref)
                elif ref == "PANEL_APP_PORT_SSH":
                    env_dict[ref] = "2222"
                    _try_find_available_port(env_dict, ref)
                elif ref == "TIME_ZONE":
                    env_dict[ref] = "Asia/Shanghai"
                elif ref == "CONTAINER_NAME":
                    env_dict[ref] = f"ubunturouter-{app_id}"
                elif ref.startswith("PANEL_"):
                    env_dict[ref] = "19000"
                else:
                    env_dict[ref] = ""
    except Exception:
        pass


def _try_find_available_port(env_dict: dict, key: str):
    """Find next available port if default is in use."""
    import socket
    base = int(env_dict.get(key, 0))
    if not base:
        return
    for port in range(base, base + 100):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("127.0.0.1", port))
            sock.close()
            if result != 0:
                env_dict[key] = str(port)
                return
        except Exception:
            pass
    env_dict[key] = str(base)


def _health_check(manifest: AppManifest, install_dir: Path) -> Dict:
    """安装后健康检查

    检查策略：
    1. Docker 容器是否正在运行
    2. 容器是否通过健康检查
    3. 如果有端口映射，检查端口是否可访问
    """
    app_id = manifest.id

    # 检查容器是否运行
    try:
        # docker compose ps --format json
        r = subprocess.run(
            ["docker", "compose", "ps", "--format", "json"],
            capture_output=True, text=True, timeout=10,
            cwd=str(install_dir),
        )
        if r.returncode != 0:
            return {"healthy": False, "error": "docker compose ps 失败"}

        # 至少有一个容器在运行
        import json
        lines = [l.strip() for l in r.stdout.split("\n") if l.strip()]
        running = False
        for line in lines:
            try:
                state = json.loads(line)
                if state.get("State") == "running":
                    running = True
                    break
            except json.JSONDecodeError:
                if "running" in line.lower() or "up" in line.lower():
                    running = True
                    break

        if not running:
            return {"healthy": False, "error": "没有容器在运行"}

    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return {"healthy": False, "error": f"Docker 检查失败: {str(e)}"}

    # 端口检查（等待几秒让服务启动）
    if manifest.ports:
        time.sleep(3)
        for port_cfg in manifest.ports:
            host_port = port_cfg.get("host_port", 0)
            if host_port and host_port > 0:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                result = sock.connect_ex(("127.0.0.1", host_port))
                sock.close()
                if result != 0:
                    return {"healthy": False, "error": f"端口 {host_port} 未监听"}

    return {"healthy": True, "app_id": app_id}
