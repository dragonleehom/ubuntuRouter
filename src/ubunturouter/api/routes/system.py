"""系统 API: status / logs / backup / snapshots / upgrade / reboot / shutdown"""

import subprocess
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
import os
import pwd
from pydantic import BaseModel

from ..deps import require_auth
from ...engine.engine import ConfigEngine
from ...engine.rollback import RollbackManager


router = APIRouter()

# ─── 状态 ───────────────────────────────────────────────────────────


@router.get("/status")
async def system_status(auth=Depends(require_auth)):
    """系统健康状态"""
    engine = ConfigEngine()
    initialized = engine.exists()

    # 检查服务
    services = {}
    for svc in ["dnsmasq", "nftables", "ssh", "systemd-networkd"]:
        try:
            r = subprocess.run(["systemctl", "is-active", svc], capture_output=True, text=True, timeout=5)
            r2 = subprocess.run(["systemctl", "is-enabled", svc], capture_output=True, text=True, timeout=5)
            services[svc] = {"active": r.stdout.strip() == "active", "enabled": r2.stdout.strip() == "enabled"}
        except Exception:
            services[svc] = {"active": False, "enabled": False}

    return {
        "initialized": initialized,
        "hostname": _get_hostname(),
        "os": _get_os_info(),
        "services": services,
    }


@router.get("/logs")
async def system_logs(lines: int = 50, service: str = "ubunturouter", auth=Depends(require_auth)):
    """查看系统日志"""
    try:
        cmd = ["journalctl", "-n", str(lines), "--no-pager", "-o", "short-precise"]
        if service != "all":
            cmd = ["journalctl", "-u", service, "-n", str(lines), "--no-pager", "-o", "short-precise"]
        r = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=10
        )
        return {"service": service, "lines": r.stdout.split("\n")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs/kernel")
async def kernel_logs(lines: int = 50, auth=Depends(require_auth)):
    """查看内核日志 (dmesg)"""
    try:
        r = subprocess.run(
            ["dmesg", "--level=emerg,alert,crit,err,warn,notice,info", "--human", "--nopager"],
            capture_output=True, text=True, timeout=10
        )
        all_lines = r.stdout.strip().split("\n")
        return {"lines": all_lines[-lines:]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs/firewall")
async def firewall_logs(lines: int = 50, auth=Depends(require_auth)):
    """查看防火墙日志 (nftables / kernel)"""
    try:
        # Try nftables trace log first, fallback to kernel log containing nft
        r = subprocess.run(
            ["journalctl", "-k", "-n", str(lines * 2), "--no-pager", "-o", "short-precise",
             "-g", "nft|nftables|NF_TABLE"],
            capture_output=True, text=True, timeout=10
        )
        all_lines = r.stdout.strip().split("\n")
        if len(all_lines) < 3:
            # Fallback: last kernel logs
            r2 = subprocess.run(
                ["journalctl", "-k", "-n", str(lines), "--no-pager", "-o", "short-precise"],
                capture_output=True, text=True, timeout=10
            )
            all_lines = r2.stdout.strip().split("\n")
        return {"lines": all_lines[-lines:]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── 主机名/时区/NTP ─────────────────────────────────────────────


class HostnameRequest(BaseModel):
    hostname: str


@router.post("/hostname")
async def set_hostname(body: HostnameRequest, auth=Depends(require_auth)):
    """修改主机名"""
    hostname = body.hostname.strip()
    if not hostname:
        raise HTTPException(status_code=400, detail="主机名不能为空")
    try:
        # Validate hostname format
        if not all(c.isalnum() or c in "-." for c in hostname):
            raise HTTPException(status_code=400, detail="主机名包含非法字符")
        subprocess.run(["hostnamectl", "set-hostname", hostname], check=True, timeout=10)
        return {"message": f"主机名已更新为 {hostname}", "hostname": hostname}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"设置主机名失败: {e.stderr}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/timezone")
async def get_timezone(auth=Depends(require_auth)):
    """获取当前时区"""
    try:
        r = subprocess.run(["timedatectl", "show", "--property=Timezone", "--value"],
                           capture_output=True, text=True, timeout=10)
        tz = r.stdout.strip()
        # Also get list of all timezones for dropdown
        r2 = subprocess.run(["timedatectl", "list-timezones"],
                            capture_output=True, text=True, timeout=10)
        timezones = [z.strip() for z in r2.stdout.strip().split("\n") if z.strip()]
        return {"timezone": tz, "timezones": timezones}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class TimezoneRequest(BaseModel):
    timezone: str


@router.post("/timezone")
async def set_timezone(body: TimezoneRequest, auth=Depends(require_auth)):
    """设置时区"""
    tz = body.timezone.strip()
    if not tz:
        raise HTTPException(status_code=400, detail="时区不能为空")
    try:
        subprocess.run(["timedatectl", "set-timezone", tz], check=True, timeout=10)
        return {"message": f"时区已设置为 {tz}", "timezone": tz}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"设置时区失败: {e.stderr}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class NtpRequest(BaseModel):
    enabled: bool = True
    servers: str = ""


@router.post("/ntp")
async def set_ntp(body: NtpRequest, auth=Depends(require_auth)):
    """设置NTP (timedatectl)"""
    try:
        if body.enabled:
            subprocess.run(["timedatectl", "set-ntp", "true"], check=True, timeout=10)
            if body.servers.strip():
                # Set NTP servers via systemd-timesyncd config
                config = (
                    "[Time]\n"
                    f"NTP={body.servers.strip()}\n"
                )
                Path("/etc/systemd/timesyncd.conf.d/").mkdir(parents=True, exist_ok=True)
                Path("/etc/systemd/timesyncd.conf.d/99-ubunturouter.conf").write_text(config)
                subprocess.run(["systemctl", "restart", "systemd-timesyncd"], check=True, timeout=10)
            return {"message": "NTP 已启用", "enabled": True, "servers": body.servers.strip()}
        else:
            subprocess.run(["timedatectl", "set-ntp", "false"], check=True, timeout=10)
            return {"message": "NTP 已禁用", "enabled": False}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"设置NTP失败: {e.stderr}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── 密码/SSH密钥管理 ────────────────────────────────────────────


class PasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/password")
async def change_password(body: PasswordRequest, auth=Depends(require_auth)):
    """修改当前用户密码 (passwd)"""
    try:
        # Use passwd via stdin
        proc = subprocess.Popen(
            ["passwd"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = proc.communicate(
            input=f"{body.current_password}\n{body.new_password}\n{body.new_password}\n",
            timeout=10
        )
        if proc.returncode != 0:
            raise HTTPException(status_code=400, detail=f"密码修改失败: {stderr.strip()}")
        return {"message": "密码已更新"}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="passwd 超时")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ssh-keys")
async def get_ssh_keys(auth=Depends(require_auth)):
    """读取当前用户的 SSH 公钥列表"""
    try:
        username = pwd.getpwuid(os.getuid()).pw_name
        ssh_dir = Path(f"/home/{username}/.ssh")
        auth_keys = ssh_dir / "authorized_keys"

        keys = []
        if auth_keys.exists():
            content = auth_keys.read_text()
            for i, line in enumerate(content.strip().split("\n")):
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split()
                    key_type = parts[0] if len(parts) > 0 else ""
                    key_comment = parts[2] if len(parts) > 2 else ""
                    # Truncate key for display
                    key_fingerprint = parts[1][:40] + "..." if len(parts) > 1 and len(parts[1]) > 40 else (parts[1] if len(parts) > 1 else "")
                    keys.append({
                        "id": i,
                        "type": key_type,
                        "fingerprint": key_fingerprint,
                        "comment": key_comment,
                        "full_key": line,
                    })
        return {"keys": keys, "username": username}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SshKeyRequest(BaseModel):
    key: str


@router.post("/ssh-keys")
async def add_ssh_key(body: SshKeyRequest, auth=Depends(require_auth)):
    """添加 SSH 公钥"""
    key = body.key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="公钥不能为空")
    try:
        # Check if it looks like a valid SSH key
        if not any(key.startswith(prefix) for prefix in ["ssh-rsa", "ssh-ed25519", "ssh-dss", "ecdsa-sha2", "sk-"]):
            raise HTTPException(status_code=400, detail="无效的 SSH 公钥格式")
        username = pwd.getpwuid(os.getuid()).pw_name
        ssh_dir = Path(f"/home/{username}/.ssh")
        ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        auth_keys = ssh_dir / "authorized_keys"

        # Append the key (ensure newline at end)
        with open(auth_keys, "a") as f:
            if auth_keys.stat().st_size > 0:
                f.write("\n")
            f.write(key + "\n")
        auth_keys.chmod(0o600)
        return {"message": "公钥已添加"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SshKeyDeleteRequest(BaseModel):
    id: int


@router.delete("/ssh-keys")
async def delete_ssh_key(body: SshKeyDeleteRequest, auth=Depends(require_auth)):
    """删除 SSH 公钥"""
    try:
        username = pwd.getpwuid(os.getuid()).pw_name
        auth_keys = Path(f"/home/{username}/.ssh/authorized_keys")
        if not auth_keys.exists():
            raise HTTPException(status_code=404, detail="authorized_keys 文件不存在")
        content = auth_keys.read_text()
        lines = content.strip().split("\n")
        # Filter out comments and empty lines for ID mapping
        key_lines = []
        for line in lines:
            line_s = line.strip()
            if line_s and not line_s.startswith("#"):
                key_lines.append(line_s)

        if body.id < 0 or body.id >= len(key_lines):
            raise HTTPException(status_code=404, detail="密钥索引不存在")

        # Find the actual line to remove
        target = key_lines[body.id]
        new_lines = [l for l in lines if l.strip() != target]

        if len(new_lines) == len(lines):
            raise HTTPException(status_code=404, detail="未找到匹配的密钥")

        auth_keys.write_text("\n".join(new_lines) + "\n")
        return {"message": "公钥已删除"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapshots")
async def list_snapshots(auth=Depends(require_auth)):
    """列出配置快照"""
    engine = ConfigEngine()
    rollback = RollbackManager(snapshot_dir=engine.snapshot_dir)
    snaps = rollback.list_snapshots()
    return {"snapshots": snaps}

# ─── OTA 在线升级 ─────────────────────────────────────────────────


@router.get("/upgrade/check")
async def check_upgrade(auth=Depends(require_auth)):
    """检查可升级的软件包 (apt list --upgradable)"""
    result = {
        "current_version": _get_app_version(),
        "upgradable": [],
        "count": 0,
        "has_updates": False,
    }
    try:
        r = subprocess.run(
            ["apt", "list", "--upgradable", "-q"],
            capture_output=True, text=True, timeout=30,
        )
        # 解析输出: pkg/stable 1.2.3 amd64 [upgradable from: 1.2.2]
        lines = r.stdout.strip().split("\n")
        # 跳过第一行 "Listing..."
        for line in lines:
            line = line.strip()
            if not line or line.startswith("Listing") or "..." in line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                pkg_info = parts[0]
                version_info = parts[1] if len(parts) > 1 else ""
                result["upgradable"].append({
                    "package": pkg_info,
                    "version": version_info,
                })
        result["count"] = len(result["upgradable"])
        result["has_updates"] = result["count"] > 0
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="apt list --upgradable 超时")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return result


@router.post("/upgrade/run")
async def run_upgrade(auth=Depends(require_auth)):
    """执行系统升级 (apt upgrade)"""
    try:
        # 后台运行，避免长时间阻塞 HTTP 请求
        proc = subprocess.Popen(
            ["apt-get", "upgrade", "-y"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = proc.communicate(timeout=600)
        return {
            "success": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": stdout.strip().split("\n")[-50:],
            "stderr": stderr.strip().split("\n")[-20:],
        }
    except subprocess.TimeoutExpired:
        proc.kill()
        raise HTTPException(status_code=504, detail="apt upgrade 超时 (10分钟)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upgrade/dist-upgrade")
async def run_dist_upgrade(auth=Depends(require_auth)):
    """执行发行版升级 (apt dist-upgrade)"""
    try:
        proc = subprocess.Popen(
            ["apt-get", "dist-upgrade", "-y"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = proc.communicate(timeout=600)
        return {
            "success": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": stdout.strip().split("\n")[-50:],
            "stderr": stderr.strip().split("\n")[-20:],
        }
    except subprocess.TimeoutExpired:
        proc.kill()
        raise HTTPException(status_code=504, detail="apt dist-upgrade 超时 (10分钟)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upgrade/apt-update")
async def run_apt_update(auth=Depends(require_auth)):
    """刷新包索引 (apt update)"""
    try:
        r = subprocess.run(
            ["apt-get", "update", "-qq"],
            capture_output=True, text=True, timeout=300,
        )
        return {
            "success": r.returncode == 0,
            "returncode": r.returncode,
            "stdout": r.stdout.strip().split("\n")[-20:],
            "stderr": r.stderr.strip().split("\n")[-20:],
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="apt update 超时")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─── 重启 / 关机 ─────────────────────────────────────────────────


class RebootShutdownRequest(BaseModel):
    delay: int = 0  # 延迟秒数


@router.post("/reboot")
async def reboot_system(body: RebootShutdownRequest = RebootShutdownRequest(), auth=Depends(require_auth)):
    """重启系统"""
    try:
        if body.delay > 0:
            subprocess.run(
                ["shutdown", "-r", f"+{body.delay // 60}" if body.delay >= 60 else f"+{body.delay // 60}"],
                capture_output=True, text=True, timeout=10,
            )
            return {"message": f"系统将在 {body.delay} 秒后重启", "delay": body.delay}
        else:
            # 立即重启
            subprocess.Popen(["systemctl", "reboot"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"message": "系统正在重启..."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/shutdown")
async def shutdown_system(body: RebootShutdownRequest = RebootShutdownRequest(), auth=Depends(require_auth)):
    """关机"""
    try:
        if body.delay > 0:
            subprocess.run(
                ["shutdown", "-h", f"+{body.delay // 60}"],
                capture_output=True, text=True, timeout=10,
            )
            return {"message": f"系统将在 {body.delay} 秒后关机", "delay": body.delay}
        else:
            subprocess.Popen(["systemctl", "poweroff"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"message": "系统正在关机..."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─── 辅助 ──────────────────────────────────────────────────────────


def _get_app_version() -> str:
    """获取当前应用版本号"""
    version_file = Path("/opt/ubunturouter/VERSION")
    if version_file.exists():
        return version_file.read_text().strip()
    return "0.1.0"


def _get_hostname() -> str:
    try:
        return Path("/etc/hostname").read_text().strip()
    except Exception:
        try:
            r = subprocess.run(["hostname"], capture_output=True, text=True, timeout=3)
            return r.stdout.strip()
        except Exception:
            return "ubunturouter"


def _get_os_info() -> dict:
    info = {"distro": "Ubuntu"}
    os_file = Path("/etc/os-release")
    if os_file.exists():
        for line in os_file.read_text().split("\n"):
            if line.startswith("VERSION_ID="):
                info["version"] = line.split("=")[1].strip('"')
            elif line.startswith("VERSION_CODENAME="):
                info["codename"] = line.split("=")[1].strip('"')
    return info
