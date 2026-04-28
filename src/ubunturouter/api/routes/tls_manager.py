"""HTTPS/TLS 证书管理 API 路由"""

import os
import subprocess
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

from ..deps import require_auth
from ..tls import CERT_DIR, CERT_PATH, KEY_PATH, ensure_cert, cert_exists

router = APIRouter(tags=["TLS"])


def _parse_cert_info() -> dict:
    """解析证书文件信息，返回结构化数据"""
    if not cert_exists():
        return {
            "exists": False,
            "cert_path": str(CERT_PATH),
            "key_path": str(KEY_PATH),
            "subject": None,
            "not_before": None,
            "not_after": None,
            "days_remaining": None,
            "issuer": None,
        }

    try:
        # 使用 openssl 解析证书
        result = subprocess.run(
            ["openssl", "x509", "-in", str(CERT_PATH), "-text", "-noout"],
            capture_output=True, text=True, timeout=15, check=True,
        )
        output = result.stdout

        subject = None
        issuer = None
        not_before = None
        not_after = None

        for line in output.splitlines():
            line_stripped = line.strip()
            if line_stripped.startswith("Subject:"):
                subject = line_stripped[len("Subject:"):].strip()
            elif line_stripped.startswith("Issuer:"):
                issuer = line_stripped[len("Issuer:"):].strip()
            elif "Not Before:" in line_stripped:
                parts = line_stripped.split("Not Before:")
                if len(parts) > 1:
                    not_before = parts[1].strip()
            elif "Not After :" in line_stripped:
                parts = line_stripped.split("Not After :")
                if len(parts) > 1:
                    not_after = parts[1].strip()

        # 计算剩余天数
        days_remaining = None
        if not_after:
            try:
                # openssl 日期格式: "Apr 28 06:15:00 2026 GMT"
                not_after_dt = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                not_after_dt = not_after_dt.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                delta = not_after_dt - now
                days_remaining = max(0, delta.days)
            except (ValueError, TypeError):
                days_remaining = None

        # 格式化日期为 ISO 格式
        def _format_date(date_str):
            if not date_str:
                return None
            try:
                dt = datetime.strptime(date_str, "%b %d %H:%M:%S %Y %Z")
                return dt.strftime("%Y-%m-%dT%H:%M:%S")
            except (ValueError, TypeError):
                return date_str

        https_enabled = _check_https_enabled()

        return {
            "exists": True,
            "cert_path": str(CERT_PATH),
            "key_path": str(KEY_PATH),
            "subject": subject,
            "not_before": _format_date(not_before),
            "not_after": _format_date(not_after),
            "days_remaining": days_remaining,
            "issuer": issuer,
            "https_enabled": https_enabled,
        }
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
        # fallback: 使用 cryptography 解析
        return _parse_cert_info_python()


def _parse_cert_info_python() -> dict:
    """使用 Python cryptography 解析证书"""
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization

        cert_pem = CERT_PATH.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_pem)

        def _name_to_str(name) -> str:
            if not name:
                return None
            parts = []
            for attr in name:
                parts.append(f"/{attr.oid._name}={attr.value}")
            result = "".join(parts)
            return result if result else None

        subject = _name_to_str(cert.subject)
        issuer = _name_to_str(cert.issuer)
        not_before = cert.not_valid_before_utc if hasattr(cert, 'not_valid_before_utc') else cert.not_valid_before
        not_after = cert.not_valid_after_utc if hasattr(cert, 'not_valid_after_utc') else cert.not_valid_after

        now = datetime.now(timezone.utc)
        delta = not_after - now
        days_remaining = max(0, delta.days)

        https_enabled = _check_https_enabled()

        return {
            "exists": True,
            "cert_path": str(CERT_PATH),
            "key_path": str(KEY_PATH),
            "subject": subject,
            "not_before": not_before.strftime("%Y-%m-%dT%H:%M:%S") if not_before else None,
            "not_after": not_after.strftime("%Y-%m-%dT%H:%M:%S") if not_after else None,
            "days_remaining": days_remaining,
            "issuer": issuer,
            "https_enabled": https_enabled,
        }
    except ImportError as e:
        return {
            "exists": cert_exists(),
            "cert_path": str(CERT_PATH),
            "key_path": str(KEY_PATH),
            "subject": None,
            "not_before": None,
            "not_after": None,
            "days_remaining": None,
            "issuer": None,
            "https_enabled": _check_https_enabled(),
            "error": str(e),
        }


def _check_https_enabled() -> bool:
    """检查当前进程是否以 HTTPS 模式运行"""
    try:
        # 检查 /proc/self/cmdline 中是否有 --ssl-certfile
        cmdline = Path("/proc/self/cmdline").read_text(errors="replace")
        return "--ssl-certfile" in cmdline or "--ssl-keyfile" in cmdline
    except (FileNotFoundError, OSError):
        return False


def _verify_cert_key_match(cert_path: Path, key_path: Path) -> bool:
    """验证证书和私钥是否匹配"""
    try:
        # 获取证书公钥哈希
        cert_mod = subprocess.run(
            ["openssl", "x509", "-in", str(cert_path), "-noout", "-modulus"],
            capture_output=True, text=True, timeout=15, check=True,
        )
        key_mod = subprocess.run(
            ["openssl", "rsa", "-in", str(key_path), "-noout", "-modulus"],
            capture_output=True, text=True, timeout=15, check=True,
        )
        return cert_mod.stdout.strip() == key_mod.stdout.strip()
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        # fallback: 尝试用 Python 验证
        try:
            from cryptography import x509
            from cryptography.hazmat.primitives import serialization, hashes

            cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
            key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)

            # 签名验证
            from cryptography.hazmat.primitives.asymmetric import rsa, padding
            if isinstance(key, rsa.RSAPrivateKey):
                # 用密钥签名一段数据，然后用证书公钥验证
                test_data = b"__ubunturouter_tls_verify__"
                signature = key.sign(test_data, padding.PKCS1v15(), hashes.SHA256())
                cert.public_key().verify(signature, test_data, padding.PKCS1v15(), hashes.SHA256())
                return True
            return False
        except Exception:
            return False


@router.get("/status")
async def get_tls_status(auth=Depends(require_auth)):
    """获取 TLS 证书状态"""
    return _parse_cert_info()


@router.post("/renew")
async def renew_cert(auth=Depends(require_auth)):
    """重新生成自签证书"""
    try:
        # 删除旧证书
        if CERT_PATH.exists():
            CERT_PATH.unlink()
        if KEY_PATH.exists():
            KEY_PATH.unlink()

        ensure_cert()

        if not cert_exists():
            raise HTTPException(status_code=500, detail="证书生成失败")

        return {
            "success": True,
            "message": "自签证书已重新生成",
            "cert_info": _parse_cert_info(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"证书重新生成失败: {str(e)}")


@router.post("/upload")
async def upload_cert(
    cert: UploadFile = File(...),
    key: UploadFile = File(...),
    auth=Depends(require_auth),
):
    """上传自定义证书（cert + key）"""
    # 验证文件类型
    if not cert.filename or not key.filename:
        raise HTTPException(status_code=400, detail="请选择证书和密钥文件")

    # 保存上传文件到临时路径
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    temp_cert = CERT_DIR / "temp_cert.pem"
    temp_key = CERT_DIR / "temp_key.pem"

    try:
        cert_content = await cert.read()
        key_content = await key.read()

        # 验证内容不为空
        if not cert_content or not key_content:
            raise HTTPException(status_code=400, detail="证书或密钥文件内容为空")

        temp_cert.write_bytes(cert_content)
        temp_key.write_bytes(key_content)

        # 验证证书格式
        try:
            subprocess.run(
                ["openssl", "x509", "-in", str(temp_cert), "-noout"],
                capture_output=True, timeout=15, check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            temp_cert.unlink(missing_ok=True)
            temp_key.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="证书文件格式无效（非 PEM 格式）")

        # 验证密钥格式
        try:
            subprocess.run(
                ["openssl", "rsa", "-in", str(temp_key), "-noout"],
                capture_output=True, timeout=15, check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            # 尝试 EC 密钥
            try:
                subprocess.run(
                    ["openssl", "ec", "-in", str(temp_key), "-noout"],
                    capture_output=True, timeout=15, check=True,
                )
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                temp_cert.unlink(missing_ok=True)
                temp_key.unlink(missing_ok=True)
                raise HTTPException(status_code=400, detail="密钥文件格式无效（非 PEM 格式）")

        # 验证证书和密钥是否匹配
        if not _verify_cert_key_match(temp_cert, temp_key):
            temp_cert.unlink(missing_ok=True)
            temp_key.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="证书和密钥不匹配")

        # 写入正式路径
        temp_cert.rename(CERT_PATH)
        temp_key.rename(KEY_PATH)

        # 设置权限
        KEY_PATH.chmod(0o600)
        CERT_PATH.chmod(0o644)

        return {
            "success": True,
            "message": "证书上传成功，请重启服务以使新证书生效",
            "cert_info": _parse_cert_info(),
        }
    except HTTPException:
        raise
    except Exception as e:
        temp_cert.unlink(missing_ok=True)
        temp_key.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"证书上传失败: {str(e)}")


@router.post("/toggle")
async def toggle_https(auth=Depends(require_auth)):
    """查询 HTTPS 状态并返回切换提示"""
    https_enabled = _check_https_enabled()

    systemd_service = "ubunturouter"  # 假设的服务名

    if https_enabled:
        return {
            "https_enabled": True,
            "message": "HTTPS 已启用。如需停用 HTTPS，请编辑启动参数移除 --ssl-certfile 和 --ssl-keyfile 后重启服务。",
            "restart_command": f"sudo systemctl restart {systemd_service}",
            "service": systemd_service,
        }
    else:
        return {
            "https_enabled": False,
            "message": "HTTPS 未启用。如需启用 HTTPS，确保证书已就绪后，在启动参数中添加 --ssl-certfile 和 --ssl-keyfile 并重启服务。",
            "restart_command": f"sudo systemctl restart {systemd_service}",
            "service": systemd_service,
        }
