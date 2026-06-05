from __future__ import annotations

from fastapi import APIRouter, status

from api.models import APIResponse, AuthResult, LoginRequest, RegisterRequest
from core.mysql_history import UserManager

router = APIRouter(tags=["鉴权"])


@router.post("/register", response_model=APIResponse)
async def register(body: RegisterRequest):
    """用户注册"""
    ok, payload = UserManager.register(body.uname, body.password)
    if not ok:
        return APIResponse(code=409, message=payload)
    return APIResponse(data=AuthResult(uid=payload, uname=body.uname))


@router.post("/login", response_model=APIResponse)
async def login(body: LoginRequest):
    """用户登录"""
    ok, payload = UserManager.login(body.uname, body.password)
    if not ok:
        return APIResponse(code=401, message=payload)
    return APIResponse(data=AuthResult(uid=payload, uname=body.uname))
