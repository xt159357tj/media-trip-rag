from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ============================================================
# 通用响应封装
# ============================================================

class APIResponse(BaseModel):
    """统一 API 响应格式"""
    code: int = Field(default=0, description="0=成功，非0=错误码")
    message: str = Field(default="ok")
    data: Any = Field(default=None)


class PaginatedData(BaseModel):
    """分页数据"""
    items: list[Any] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


# ============================================================
# 鉴权
# ============================================================

class RegisterRequest(BaseModel):
    uname: str = Field(..., min_length=2, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=100, description="密码")


class LoginRequest(BaseModel):
    uname: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)


class AuthResult(BaseModel):
    uid: str
    uname: str


# ============================================================
# 工作流
# ============================================================

class WorkflowIntent(str, enum.Enum):
    chat = "chat"
    workflow = "workflow"
    route_plan = "route_plan"
    rag = "rag"


class WorkflowRequest(BaseModel):
    uid: str = Field(..., min_length=1, description="用户唯一ID")
    session_id: str | None = Field(default=None, description="续接已有会话时传入")
    user_input: str = Field(..., min_length=1, description="用户输入文本")
    original_video_path: str = Field(default="", description="待处理视频路径")


class SSEMessage(BaseModel):
    """单条 SSE 事件的负载结构"""
    type: Literal["status", "answer", "done", "error"]
    content: str = ""
    video_url: str | None = None
    session_id: str | None = None
    intent: str | None = None


# ============================================================
# 历史记录
# ============================================================

class QATurn(BaseModel):
    """一轮问答"""
    user: list[dict[str, Any]]
    assistant: list[dict[str, Any]]


class SessionItem(BaseModel):
    session_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    preview: str = Field(default="", description="首条用户输入截断预览")


class SessionDetail(BaseModel):
    session_id: str
    history: list[QATurn]
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ============================================================
# 文件
# ============================================================

class FileUploadResult(BaseModel):
    filename: str
    file_path: str
    url: str
    size: int


class FileItem(BaseModel):
    filename: str
    file_path: str
    url: str
    size: int
    created_at: str
