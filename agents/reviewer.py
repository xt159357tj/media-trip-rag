import base64
import os
from typing import List
from langchain_core.tools import Tool
from workflow.state import AgentResponse
from mcp_integration.tool_adapter import MCPAdapter
from agents.base import BaseAgent

class SubtitleReviewer(BaseAgent):
    def __init__(self, mcp_tools: List[Tool], mcp_adapter: MCPAdapter):
        # 映射至 LLMClientFactory.create_reviewer
        super().__init__(mcp_tools, mcp_adapter, agent_type="reviewer")

    async def review(self, srt_path: str, audio_path: str, prompt_name: str, review_feedback: str = "") -> AgentResponse:
        try:
            self.logger.info(f"开始全模态审核任务: {srt_path}")

            # 1. 获取字幕资源 (Resource)
            srt_uri = f"mcp://file/subtitle/{srt_path}"
            srt_content = await self.mcp_adapter.read_resource(srt_uri)
            if not srt_content:
                return AgentResponse(
                    success=False,
                    content="",
                    error="无法读取字幕资源内容"
                )

            # 2. 获取审核 Prompt
            prompt_args = {"content": srt_content}
            if review_feedback:
                prompt_args["review_feedback"] = review_feedback

            review_prompt_data = await self.mcp_adapter.get_prompt(
                prompt_name,
                arguments=prompt_args
            )

            # 3. 准备音频多模态数据
            if not os.path.exists(audio_path):
                return AgentResponse(
                    success=False,
                    content="",
                    error=f"找不到音频文件: {audio_path}"
                )

            with open(audio_path, "rb") as f:
                audio_b64 = base64.b64encode(f.read()).decode("utf-8")

            # 4. 构造全模态消息 (Dashscope Qwen 格式)
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"text": review_prompt_data},
                        {"audio": f"data:audio/mp3;base64,{audio_b64}"},
                    ]
                }
            ]

            # 5. 调用模型并封装响应
            response = await self.llm.ainvoke(messages)
            review_feedback = response

            return AgentResponse(
                success=True,
                content=review_feedback,
                metadata={
                    "srt_path": srt_path,
                    "audio_path": audio_path,
                }
            )

        except Exception as e:
            self.logger.error(f"审核 Agent 运行异常: {str(e)}")
            return AgentResponse(
                success=False,
                content="",
                error=str(e)
            )