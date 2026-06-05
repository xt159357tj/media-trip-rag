from __future__ import annotations

import platform
import time

from fastapi import APIRouter, Request

router = APIRouter(tags=["系统"])

_START_TIME = time.time()


@router.get("/health", summary="健康检查")
async def health_check(request: Request):
    """返回服务运行状态与基本诊断信息"""
    mcp_ready = getattr(request.app.state, "mcp_adapter", None) is not None

    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - _START_TIME, 2),
        "python": platform.python_version(),
        "mcp_connected": mcp_ready,
    }
