"""JWT Token 签发/验证/刷新"""

import time
import hmac
import base64
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


JWT_SECRET_PATH = Path("/etc/ubunturouter/jwt_secret")
ACCESS_TOKEN_TTL = 3600       # 1 小时
REFRESH_TOKEN_TTL = 2592000   # 30 天


@dataclass
class TokenPayload:
    sub: str       # username
    exp: int       # 过期时间
    iat: int       # 签发时间
    typ: str = "access"  # access / refresh
    groups: list = None


def _get_secret() -> str:
    """获取 JWT 密钥（持久化存储）"""
    if JWT_SECRET_PATH.exists():
        return JWT_SECRET_PATH.read_text().strip()
    # 首次运行生成随机密钥
    import secrets
    secret = secrets.token_hex(32)
    JWT_SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
    JWT_SECRET_PATH.write_text(secret)
    JWT_SECRET_PATH.chmod(0o600)
    return secret


def _b64_encode(data: bytes) -> str:
    """Base64 URL-safe 编码（无 padding）"""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64_decode(s: str) -> bytes:
    """Base64 URL-safe 解码（补 padding）"""
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def _hmac_sign(payload_b64: str) -> str:
    """HMAC-SHA256 签名"""
    secret = _get_secret()
    signer = hmac.new(secret.encode(), payload_b64.encode(), "sha256")
    return _b64_encode(signer.digest())


def create_token(username: str, token_type: str = "access",
                 groups: list = None) -> str:
    """签发 JWT"""
    now = int(time.time())
    ttl = ACCESS_TOKEN_TTL if token_type == "access" else REFRESH_TOKEN_TTL
    payload = TokenPayload(
        sub=username,
        exp=now + ttl,
        iat=now,
        typ=token_type,
        groups=groups or [],
    )
    # JWT 格式: header.payload.signature
    header = _b64_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload_b64 = _b64_encode(json.dumps(payload.__dict__).encode())
    signature = _hmac_sign(f"{header}.{payload_b64}")
    return f"{header}.{payload_b64}.{signature}"


def verify_token(token: str) -> Optional[TokenPayload]:
    """验证 JWT，返回 payload 或 None"""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        header_b64, payload_b64, signature = parts

        # 验证签名
        expected_sig = _hmac_sign(f"{header_b64}.{payload_b64}")
        if not hmac.compare_digest(signature, expected_sig):
            return None

        # 解码 payload
        payload_data = json.loads(_b64_decode(payload_b64))
        payload = TokenPayload(**payload_data)

        # 检查过期
        if time.time() > payload.exp:
            return None

        return payload
    except Exception:
        return None


def refresh_access_token(refresh_token: str) -> Optional[str]:
    """用 refresh token 刷新 access token"""
    payload = verify_token(refresh_token)
    if not payload or payload.typ != "refresh":
        return None
    return create_token(payload.sub, "access", payload.groups)
