"""FastAPI 依赖项"""

from fastapi import Header, HTTPException, Request
from typing import Optional

from .auth.jwt import verify_token


async def require_auth(request: Request):
    """要求登录认证"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")

    payload = verify_token(auth[7:])
    if not payload:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")

    return payload
