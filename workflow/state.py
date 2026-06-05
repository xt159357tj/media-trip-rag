from typing import TypedDict, Literal, Optional, Any
from dataclasses import dataclass, field

class WorkflowState(TypedDict):
    """工作状态"""
    # --- 基础路径与标识 ---
    original_video_path: str
    audio_path: str
    original_srt_path: str
    final_srt_path: str
    final_video_path: str

    # --- 核心内容区 ---
    user_input: str
    intent: Literal["chat", "workflow", "route_plan", "RAG"]
    intent_confidence: float
    review_feedback: str
    review_passed: bool
    final_output: str
    loop_count: int
    uid: str
    session_id: str

    # --- 流程控制 ---
    execution_path: list[str]

    # --- 异常 ---
    error: Optional[str]

@dataclass
class AgentResponse:
    """智能体响应"""
    success: bool
    content: Any
    error: Optional[str] = None
    metadata: dict[str, Any] =field(default_factory=dict)