from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_current_uid
from api.models import APIResponse, SessionItem
from core.logger import get_logger
from core.mysql_history import UserMySQLHistoryManager

router = APIRouter(tags=["历史记录"])

logger = get_logger(__name__)


@router.get("/sessions", response_model=APIResponse)
async def list_sessions(uid: Annotated[str, Depends(get_current_uid)]):
    """获取当前用户的所有历史会话列表"""
    manager = UserMySQLHistoryManager(uid=uid)
    session_ids = manager.get_all_sessions()

    items: list[SessionItem] = []
    for sid in session_ids:
        history = manager.load(sid)
        preview = ""
        if history:
            first_turn = history[0]
            user_msgs = first_turn.get("user", [])
            if user_msgs:
                first_msg = user_msgs[0]
                text = first_msg.get("content", "") if isinstance(first_msg, dict) else str(first_msg)
                preview = text[:80] + ("..." if len(text) > 80 else "")
        items.append(SessionItem(session_id=sid, preview=preview))

    return APIResponse(data={"sessions": items, "total": len(items)})


@router.get("/sessions/{session_id}", response_model=APIResponse)
async def get_session(session_id: str, uid: Annotated[str, Depends(get_current_uid)]):
    """获取指定会话的完整历史记录"""
    manager = UserMySQLHistoryManager(uid=uid)
    history = manager.load(session_id)

    if not history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 404, "message": f"会话 {session_id} 不存在"},
        )

    return APIResponse(data={"session_id": session_id, "history": history})


@router.delete("/sessions/{session_id}", response_model=APIResponse)
async def delete_session(session_id: str, uid: Annotated[str, Depends(get_current_uid)]):
    """删除指定会话及其关联的知识库文档"""
    manager = UserMySQLHistoryManager(uid=uid)
    ok = manager.delete_session(session_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": 500, "message": "删除会话失败"},
        )
    return APIResponse(message=f"会话 {session_id} 已删除")
