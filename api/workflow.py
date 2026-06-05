from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from api.deps import get_current_uid
from api.models import WorkflowRequest
from core.logger import get_logger

router = APIRouter(tags=["工作流"])

logger = get_logger(__name__)


@router.post("/process", summary="执行工作流（SSE 流式响应）")
async def process_workflow(body: WorkflowRequest, request: Request):
    """
    提交工作流任务并以 Server-Sent Events 流式返回执行进度与最终结果。

    事件类型:
    - **status**:  节点状态变更
    - **answer**:  LLM 流式文本输出
    - **done**:    工作流完成（含 video_url / session_id / intent）
    - **error**:   执行异常
    """
    # 复用 lifespan 中已初始化的 Workflow 单例（含 MCP 长连接 + 共享 Agent + 已编译的图）
    workflow = request.app.state.workflow

    async def event_stream():
        try:
            await workflow._prepare_agents(body.uid)

            async for chunk in workflow.run_stream(body.model_dump()):
                yield chunk
        except Exception as exc:
            logger.error(f"工作流执行异常: {exc}")
            payload = json.dumps({"type": "error", "content": str(exc)}, ensure_ascii=False)
            yield f"data: {payload}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/status", summary="检查工作流服务状态")
async def workflow_status(request: Request):
    """返回 MCP 连接与工作流就绪状态"""
    mcp_ready = getattr(request.app.state, "mcp_adapter", None) is not None
    return {
        "workflow": "online",
        "mcp_connected": mcp_ready,
    }
