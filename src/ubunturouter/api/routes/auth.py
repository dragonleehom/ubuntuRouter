"""Auth API 端点: login/logout/refresh/me"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional

from ..auth import (
    pam_authenticate, get_user_groups,
    create_token, verify_token, refresh_access_token,
    record_fail, record_success, is_locked, remaining_attempts,
)


router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


def get_client_ip(request: Request) -> str:
    """获取客户端 IP"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/login")
async def login(req: LoginRequest, request: Request):
    """登录"""
    ip = get_client_ip(request)

    # 检查锁定
    if is_locked(ip):
        remain = remaining_attempts(ip)
        raise HTTPException(
            status_code=429,
            detail={"error": "IP 已被锁定", "remaining_seconds": 300}
        )

    # PAM 认证
    if not pam_authenticate(req.username, req.password):
        count = record_fail(ip)
        remain = remaining_attempts(ip)
        raise HTTPException(
            status_code=401,
            detail={"error": "用户名或密码错误", "remaining_attempts": remain}
        )

    # 成功
    record_success(ip)
    groups = get_user_groups(req.username)

    access_token = create_token(req.username, "access", groups)
    refresh_token = create_token(req.username, "refresh", groups)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh")
async def refresh(req: RefreshRequest):
    """刷新 access token"""
    new_token = refresh_access_token(req.refresh_token)
    if not new_token:
        raise HTTPException(status_code=401, detail="refresh token 无效或已过期")
    return {"access_token": new_token, "token_type": "bearer"}


@router.get("/me")
async def me(request: Request):
    """获取当前用户信息"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")

    payload = verify_token(auth[7:])
    if not payload:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")

    return {
        "username": payload.sub,
        "groups": payload.groups or [],
        "expires_at": payload.exp,
    }
