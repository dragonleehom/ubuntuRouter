"""自定义应用生命周期管理器 — 支持4种部署类型

部署类型:
  - docker: 单容器 (docker run)
  - docker-compose: 多容器编排 (docker-compose.yml)
  - apt: 系统软件包 (apt-get)
  - script: 自定义脚本 (bash/python/二进制)

自启动: 为每个应用生成 systemd .service 文件
"""
import json
import logging
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Tuple

logger = logging.getLogger("ubunturouter.appstore.lifecycle")

CUSTOM_APPS_DB = Path("/opt/ubunturouter/data/custom_apps.json")
SYSTEMD_DIR = Path("/etc/systemd/system")
INSTALLED_DIR = Path("/opt/ubunturouter/apps/installed")


@dataclass
class AppDefinition:
    """自定义应用定义"""
    id: str                          # 唯一 ID (自动生成)
    name: str                        # 显示名称
    deploy_type: str = "docker"      # docker / docker-compose / apt / script

    # Docker 参数
    image: str = ""
    container_name: str = ""
    ports: List[str] = field(default_factory=list)       # ["8080:80"]
    volumes: List[str] = field(default_factory=list)     # ["./data:/data"]
    environment: List[str] = field(default_factory=list) # ["KEY=VAL"]
    restart_policy: str = "always"
    network: str = "bridge"
    depends_on: List[str] = field(default_factory=list)

    # Docker Compose
    compose_content: str = ""

    # APT
    apt_packages: List[str] = field(default_factory=list)
    ppa: str = ""

    # Script
    install_script: str = ""
    uninstall_script: str = ""
    start_command: str = ""
    stop_command: str = ""
    status_command: str = ""

    # 系统
    startup_delay: int = 0            # 启动延时（秒）
    enabled: bool = True
    created_at: str = ""


class AppLifecycleManager:
    """自定义应用生命周期管理器"""

    def __init__(self):
        self._db_path = CUSTOM_APPS_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_db()

    # ── 安装 ──────────────────────────────────────────────

    def install(self, app_def: AppDefinition) -> Tuple[bool, str]:
        """安装自定义应用"""
        if not app_def.id:
            app_def.id = f"custom-{uuid.uuid4().hex[:8]}"
        app_def.created_at = time.strftime("%Y-%m-%dT%H:%M:%S")

        try:
            if app_def.deploy_type == "docker":
                success, msg = self._install_docker(app_def)
            elif app_def.deploy_type == "docker-compose":
                success, msg = self._install_compose(app_def)
            elif app_def.deploy_type == "apt":
                success, msg = self._install_apt(app_def)
            elif app_def.deploy_type == "script":
                success, msg = self._install_script(app_def)
            else:
                return False, f"不支持的部署类型: {app_def.deploy_type}"

            if not success:
                return False, msg

            # 创建 systemd 服务
            self._create_systemd_service(app_def)

            # 保存到数据库
            self._save_app(app_def)

            return True, f"应用 {app_def.name} 安装成功"
        except Exception as e:
            # 回滚
            self._rollback(app_def)
            return False, f"安装失败 (已回滚): {str(e)}"

    def _install_docker(self, app: AppDefinition) -> Tuple[bool, str]:
        """安装 Docker 单容器应用"""
        cmd = ["docker", "run", "-d"]
        if app.container_name:
            cmd += ["--name", app.container_name]
        else:
            cmd += ["--name", app.id]

        cmd += ["--restart", app.restart_policy]

        for p in app.ports:
            cmd += ["-p", p]
        for v in app.volumes:
            cmd += ["-v", v]
        for e in app.environment:
            cmd += ["-e", e]

        if app.network and app.network != "bridge":
            cmd += ["--network", app.network]

        cmd.append(app.image)

        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            return False, r.stderr.strip()
        return True, r.stdout.strip()

    def _install_compose(self, app: AppDefinition) -> Tuple[bool, str]:
        """安装 Docker Compose 应用"""
        app_dir = INSTALLED_DIR / app.id
        app_dir.mkdir(parents=True, exist_ok=True)
        compose_path = app_dir / "docker-compose.yml"
        compose_path.write_text(app.compose_content)
        r = subprocess.run(
            ["docker", "compose", "-f", str(compose_path), "up", "-d"],
            capture_output=True, text=True, timeout=120
        )
        if r.returncode != 0:
            return False, r.stderr.strip()
        return True, "Docker Compose 已启动"

    def _install_apt(self, app: AppDefinition) -> Tuple[bool, str]:
        """安装 APT 包应用"""
        if app.ppa:
            r = subprocess.run(
                ["add-apt-repository", "-y", app.ppa],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode != 0:
                logger.warning("PPA 添加失败: %s", r.stderr.strip())

        r = subprocess.run(
            ["apt-get", "update", "-qq"],
            capture_output=True, text=True, timeout=60
        )
        cmd = ["apt-get", "install", "-y", "-qq"] + app.apt_packages
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            return False, r.stderr.strip()
        return True, f"APT 包 {' '.join(app.apt_packages)} 已安装"

    def _install_script(self, app: AppDefinition) -> Tuple[bool, str]:
        """安装脚本应用"""
        if not app.install_script:
            return True, "无安装脚本，跳过"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh",
                                          delete=False) as f:
            f.write(app.install_script)
            script_path = f.name
        os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IEXEC)
        try:
            r = subprocess.run(
                ["bash", script_path],
                capture_output=True, text=True, timeout=300
            )
            if r.returncode != 0:
                return False, r.stderr.strip()
            return True, "脚本安装完成"
        finally:
            Path(script_path).unlink(missing_ok=True)

    # ── 卸载 ──────────────────────────────────────────────

    def uninstall(self, app_id: str) -> Tuple[bool, str]:
        """卸载应用"""
        app = self._load_app(app_id)
        if not app:
            return False, f"应用 {app_id} 未找到"

        try:
            if app.deploy_type in ("docker", "docker-compose"):
                self._stop_docker(app)
                self._remove_docker(app)
            elif app.deploy_type == "apt":
                cmd = ["apt-get", "remove", "-y", "-qq"] + app.apt_packages
                subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            elif app.deploy_type == "script" and app.uninstall_script:
                with tempfile.NamedTemporaryFile(mode="w", suffix=".sh",
                                                  delete=False) as f:
                    f.write(app.uninstall_script)
                    script_path = f.name
                os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IEXEC)
                subprocess.run(["bash", script_path],
                               capture_output=True, text=True, timeout=300)
                Path(script_path).unlink(missing_ok=True)

            # 删除 systemd 服务
            self._remove_systemd_service(app_id)

            # 删除 Compose 目录
            app_dir = INSTALLED_DIR / app_id
            if app_dir.exists():
                shutil.rmtree(app_dir)

            # 从数据库删除
            self._remove_app(app_id)

            return True, f"应用 {app.name or app_id} 已卸载"
        except Exception as e:
            return False, f"卸载失败: {str(e)}"

    # ── 启停 ──────────────────────────────────────────────

    def start(self, app_id: str) -> Tuple[bool, str]:
        """启动应用"""
        app = self._load_app(app_id)
        if not app:
            return False, f"应用 {app_id} 未找到"
        try:
            if app.deploy_type == "docker":
                name = app.container_name or app.id
                r = subprocess.run(["docker", "start", name],
                                   capture_output=True, text=True, timeout=30)
                if r.returncode != 0:
                    return False, r.stderr.strip()
            elif app.deploy_type == "docker-compose":
                compose_path = INSTALLED_DIR / app.id / "docker-compose.yml"
                if compose_path.exists():
                    subprocess.run(["docker", "compose", "-f", str(compose_path),
                                    "up", "-d"], capture_output=True, text=True, timeout=60)
            elif app.deploy_type == "script" and app.start_command:
                subprocess.run(["systemctl", "start", app.start_command.lstrip("systemctl ").strip()],
                               capture_output=True, text=True, timeout=30)
            # 通过 systemd 启动
            subprocess.run(["systemctl", "start", f"ubunturouter-app-{app_id}.service"],
                           capture_output=True, text=True, timeout=15)
            return True, f"应用 {app_id} 已启动"
        except Exception as e:
            return False, f"启动失败: {str(e)}"

    def stop(self, app_id: str) -> Tuple[bool, str]:
        """停止应用"""
        try:
            if Path(f"/etc/systemd/system/ubunturouter-app-{app_id}.service").exists():
                subprocess.run(["systemctl", "stop", f"ubunturouter-app-{app_id}.service"],
                               capture_output=True, text=True, timeout=15)
            else:
                app = self._load_app(app_id)
                if app and app.deploy_type in ("docker", "docker-compose"):
                    self._stop_docker(app)
            return True, f"应用 {app_id} 已停止"
        except Exception as e:
            return False, f"停止失败: {str(e)}"

    def restart(self, app_id: str) -> Tuple[bool, str]:
        """重启应用"""
        self.stop(app_id)
        time.sleep(1)
        return self.start(app_id)

    def status(self, app_id: str) -> Dict:
        """获取应用运行状态"""
        result = {"id": app_id, "running": False, "status": "unknown"}
        app = self._load_app(app_id)
        if not app:
            result["status"] = "not_found"
            return result

        try:
            if app.deploy_type == "docker":
                name = app.container_name or app.id
                r = subprocess.run(["docker", "inspect", name, "--format",
                                    "{{.State.Status}}"],
                                   capture_output=True, text=True, timeout=10)
                result["status"] = r.stdout.strip() if r.returncode == 0 else "stopped"
                result["running"] = result["status"] == "running"
            elif app.deploy_type == "docker-compose":
                compose_path = INSTALLED_DIR / app.id / "docker-compose.yml"
                if compose_path.exists():
                    r = subprocess.run(
                        ["docker", "compose", "-f", str(compose_path), "ps", "--format", "json"],
                        capture_output=True, text=True, timeout=15
                    )
                    result["running"] = "running" in r.stdout.lower()
            elif app.deploy_type == "script" and app.status_command:
                r = subprocess.run(
                    ["bash", "-c", app.status_command],
                    capture_output=True, text=True, timeout=15
                )
                result["running"] = r.returncode == 0
            else:
                # 检查 systemd
                r = subprocess.run(
                    ["systemctl", "is-active", f"ubunturouter-app-{app.id}.service"],
                    capture_output=True, text=True, timeout=10
                )
                result["running"] = r.stdout.strip() == "active"
                result["status"] = r.stdout.strip()
        except Exception as e:
            result["status"] = str(e)

        result["name"] = app.name
        result["deploy_type"] = app.deploy_type
        return result

    def get_logs(self, app_id: str, lines: int = 100) -> str:
        """获取应用日志"""
        app = self._load_app(app_id)
        if not app:
            return ""

        try:
            if app.deploy_type == "docker":
                name = app.container_name or app.id
                r = subprocess.run(
                    ["docker", "logs", "--tail", str(lines), name],
                    capture_output=True, text=True, timeout=15
                )
                return r.stdout + r.stderr
            elif app.deploy_type == "docker-compose":
                compose_path = INSTALLED_DIR / app.id / "docker-compose.yml"
                if compose_path.exists():
                    r = subprocess.run(
                        ["docker", "compose", "-f", str(compose_path), "logs",
                         "--tail", str(lines)],
                        capture_output=True, text=True, timeout=15
                    )
                    return r.stdout + r.stderr
            return "日志不可用"
        except Exception as e:
            return f"获取日志失败: {str(e)}"

    # ── systemd 服务管理 ─────────────────────────────────

    def _create_systemd_service(self, app: AppDefinition) -> None:
        """为应用创建 systemd 服务单元"""
        service_name = f"ubunturouter-app-{app.id}"
        svc_path = SYSTEMD_DIR / f"{service_name}.service"

        exec_start = self._get_exec_start(app)
        exec_stop = self._get_exec_stop(app)

        lines = ["[Unit]",
                 f"Description=UbuntuRouter Custom App - {app.name}",
                 "After=network-online.target docker.service",
                 "Wants=network-online.target",
                 "",
                 "[Service]",
                 "Type=simple",
                 f"ExecStart={exec_start}"]

        if exec_stop:
            lines.append(f"ExecStop={exec_stop}")

        if app.startup_delay > 0:
            lines.append(f"ExecStartPre=/bin/sleep {app.startup_delay}")

        lines.extend([
            "Restart=on-failure",
            "RestartSec=10",
            "User=root",
            "StandardOutput=journal",
            "StandardError=journal",
            "",
            "[Install]",
            "WantedBy=multi-user.target",
        ])

        svc_path.write_text("\n".join(lines) + "\n")
        svc_path.chmod(0o644)

        # 重载并启用
        subprocess.run(["systemctl", "daemon-reload"],
                       capture_output=True, text=True, timeout=10)
        subprocess.run(["systemctl", "enable", f"{service_name}.service"],
                       capture_output=True, text=True, timeout=10)
        logger.info("Created systemd service: %s", service_name)

    def _remove_systemd_service(self, app_id: str) -> None:
        """删除应用的 systemd 服务"""
        service_name = f"ubunturouter-app-{app_id}"
        svc_path = SYSTEMD_DIR / f"{service_name}.service"
        if svc_path.exists():
            subprocess.run(["systemctl", "stop", f"{service_name}.service"],
                           capture_output=True, text=True, timeout=10)
            subprocess.run(["systemctl", "disable", f"{service_name}.service"],
                           capture_output=True, text=True, timeout=10)
            svc_path.unlink()
            subprocess.run(["systemctl", "daemon-reload"],
                           capture_output=True, text=True, timeout=10)
            logger.info("Removed systemd service: %s", service_name)

    def _get_exec_start(self, app: AppDefinition) -> str:
        """获取启动命令"""
        if app.deploy_type == "docker":
            name = app.container_name or app.id
            return f"/usr/bin/docker start {name}"
        elif app.deploy_type == "docker-compose":
            compose_path = INSTALLED_DIR / app.id / "docker-compose.yml"
            return f"/usr/bin/docker compose -f {compose_path} up"
        elif app.deploy_type == "script" and app.start_command:
            return app.start_command
        return "/bin/true"

    def _get_exec_stop(self, app: AppDefinition) -> str:
        if app.deploy_type == "docker":
            name = app.container_name or app.id
            return f"/usr/bin/docker stop {name}"
        elif app.deploy_type == "script" and app.stop_command:
            return app.stop_command
        return ""

    def _stop_docker(self, app: AppDefinition) -> None:
        """停止 Docker 容器"""
        name = app.container_name or app.id
        subprocess.run(["docker", "stop", name],
                       capture_output=True, text=True, timeout=30)

    def _remove_docker(self, app: AppDefinition) -> None:
        """删除 Docker 容器"""
        name = app.container_name or app.id
        subprocess.run(["docker", "rm", "-f", name],
                       capture_output=True, text=True, timeout=30)

    def _rollback(self, app: AppDefinition) -> None:
        """安装失败时回滚"""
        try:
            if app.deploy_type in ("docker", "docker-compose"):
                self._stop_docker(app)
                self._remove_docker(app)
            self._remove_systemd_service(app.id)
            app_dir = INSTALLED_DIR / app.id
            if app_dir.exists():
                shutil.rmtree(app_dir)
        except Exception as e:
            logger.error("Rollback failed: %s", e)

    # ── 数据持久化 ──────────────────────────────────────

    def _ensure_db(self) -> None:
        if not self._db_path.exists():
            self._db_path.write_text("[]")

    def _save_app(self, app: AppDefinition) -> None:
        apps = self._list_all()
        existing = [a for a in apps if a["id"] == app.id]
        if existing:
            apps = [a for a in apps if a["id"] != app.id]
        apps.append(self._to_dict(app))
        self._db_path.write_text(json.dumps(apps, indent=2, ensure_ascii=False))

    def _remove_app(self, app_id: str) -> None:
        apps = self._list_all()
        apps = [a for a in apps if a["id"] != app_id]
        self._db_path.write_text(json.dumps(apps, indent=2, ensure_ascii=False))

    def _list_all(self) -> List[Dict]:
        try:
            return json.loads(self._db_path.read_text()) if self._db_path.exists() else []
        except (json.JSONDecodeError, OSError):
            return []

    def _load_app(self, app_id: str) -> Optional[AppDefinition]:
        for item in self._list_all():
            if item["id"] == app_id:
                return self._from_dict(item)
        return None

    def list_installed(self) -> List[Dict]:
        """获取所有已安装的自定义应用"""
        return self._list_all()

    @staticmethod
    def _to_dict(app: AppDefinition) -> Dict:
        return {k: v for k, v in app.__dict__.items()}

    @staticmethod
    def _from_dict(d: Dict) -> AppDefinition:
        return AppDefinition(**{k: d.get(k, v.default if hasattr(v, 'default') else "")
                                for k, v in AppDefinition.__dataclass_fields__.items()})
