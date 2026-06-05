from __future__ import annotations

import os
import time

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager, AsyncExitStack

from api.auth import router as auth_router
from api.files import router as files_router
from api.health import router as health_router
from api.history import router as history_router
from api.rag import router as rag_router
from api.workflow import router as workflow_router
from config.settings import settings
from core.mysql_history import UserManager, DB_CONFIG
from mcp_integration.tool_adapter import get_mcp_adapter


# ============================================================
# 生命周期
# ============================================================

def _init_database():
    """启动时自动创建数据库和用户表"""
    import pymysql
    try:
        conn = pymysql.connect(
            host=DB_CONFIG["host"], user=DB_CONFIG["user"],
            password=DB_CONFIG["password"], charset="utf8mb4",
        )
        with conn.cursor() as cur:
            cur.execute("CREATE DATABASE IF NOT EXISTS chat_history_db DEFAULT CHARSET utf8mb4")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[WARN] 无法创建数据库: {e}")
        return
    UserManager.init_users_table()
    print("Database & users table ready")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """管理全局资源：MCP 连接与目录准备"""
    _init_database()
    os.makedirs(settings.FINAL_VIDEO_PATH, exist_ok=True)
    os.makedirs(settings.ORIGINAL_VIDEO_PATH, exist_ok=True)
    os.makedirs(settings.ORIGINAL_SRT_PATH, exist_ok=True)
    os.makedirs(settings.FINAL_SRT_PATH, exist_ok=True)

    from workflow.graph import SubtitleGenerationWorkflow

    mcp_adapter = get_mcp_adapter(settings.MCP_SERVER_URI)
    async with AsyncExitStack() as stack:
        if hasattr(mcp_adapter, "__aenter__"):
            await stack.enter_async_context(mcp_adapter)
        app.state.mcp_adapter = mcp_adapter
        print("MCP adapter ready")

        # Workflow 单例，整个应用生命周期内复用，避免每次请求重建 Agent 和图
        app.state.workflow = SubtitleGenerationWorkflow(mcp_adapter)
        await app.state.workflow._ensure_ready()
        print("Workflow ready")

        yield

    print("MCP resources released")


# ============================================================
# 应用实例
# ============================================================

app = FastAPI(
    title="Media Trip RAG API",
    description="视频字幕生成、出行规划、RAG 知识库检索一体化后端",
    version="1.0.0",
    lifespan=lifespan,
)

# ============================================================
# 中间件
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录每个请求的方法、路径、耗时与状态码"""
    t0 = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"{request.method} {request.url.path}  ->  {response.status_code}  ({elapsed:.0f}ms)")
    return response


# ============================================================
# 全局异常处理
# ============================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"code": 500, "message": f"服务器内部错误: {exc}"},
    )


# ============================================================
# 静态文件
# ============================================================

app.mount("/static_videos", StaticFiles(directory=settings.FINAL_VIDEO_PATH), name="outputs")
app.mount("/static_uploads", StaticFiles(directory=settings.ORIGINAL_VIDEO_PATH), name="uploads")

# ============================================================
# 路由注册
# ============================================================

app.include_router(auth_router, prefix="/api")
app.include_router(workflow_router, prefix="/api")
app.include_router(history_router, prefix="/api")
app.include_router(files_router, prefix="/api")
app.include_router(health_router, prefix="/api")
app.include_router(rag_router, prefix="/api")


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
