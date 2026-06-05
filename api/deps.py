from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Header, HTTPException, Request, status

if TYPE_CHECKING:
    from mcp_integration.tool_adapter import MCPAdapter


# ============================================================
# 用户身份依赖
# ============================================================

async def get_current_uid(x_uid: str | None = Header(default=None, alias="X-UID")) -> str:
    """从请求头 X-UID 提取用户ID"""
    if not x_uid or not x_uid.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 401, "message": "缺少用户身份标识，请在 Header 中提供 X-UID"},
        )
    return x_uid.strip()


async def get_optional_uid(x_uid: str | None = Header(default=None, alias="X-UID")) -> str | None:
    """可选提取用户ID，不存在时返回 None"""
    return x_uid.strip() if x_uid else None


# ============================================================
# MCP 适配器依赖
# ============================================================

def get_mcp(request: Request) -> MCPAdapter:
    """从 app.state 获取全局 MCP 适配器"""
    adapter: MCPAdapter | None = getattr(request.app.state, "mcp_adapter", None)
    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": 503, "message": "MCP 服务未就绪"},
        )
    return adapter
