from typing import List
from langchain_core.tools import Tool
from workflow.state import AgentResponse
from mcp_integration.tool_adapter import MCPAdapter
from agents.base import BaseAgent


class SubtitleEditor(BaseAgent):
    def __init__(self, mcp_tools: List[Tool], mcp_adapter: MCPAdapter):
        # 映射至 LLMClientFactory.create_rewriter
        super().__init__(mcp_tools, mcp_adapter, agent_type="rewriter")

    async def rewrite(self, srt_path: str, review_feedback: str) -> AgentResponse:
        try:
            self.logger.info(f"开始执行字幕修正: {srt_path}")

            # 1. 读取原始资源
            srt_uri = f"mcp://file/subtitle/{srt_path}"
            original_srt = await self.mcp_adapter.read_resource(srt_uri)

            # 2. 构造重写 Prompt
            rewrite_prompt = await self.mcp_adapter.get_prompt(
                "rewrite_subtitle_prompt",
                arguments={
                    "content": original_srt,
                    "review_feedback": review_feedback
                }
            )

            # 3. LLM 生成新字幕
            response = await self.llm.ainvoke(rewrite_prompt)
            refined_srt = response

            # 4. 调用工具进行物理保存 (Tool)
            save_tool = self.get_tool("save_subtitle_tool")
            final_save_path = ""

            if save_tool:
                # 显式使用 coroutine 异步执行
                final_save_path = await save_tool.coroutine(
                    file_path=srt_path,
                    content=refined_srt
                )
            else:
                self.logger.warning("未找到保存工具，仅返回文本内容")

            # 5. 返回封装后的响应
            return AgentResponse(
                success=True,
                content=refined_srt,
                metadata={
                    "srt_path": srt_path,
                    "final_path": final_save_path,
                    "is_modified": True
                }
            )

        except Exception as e:
            self.logger.error(f"修正 Agent 运行异常: {str(e)}")
            return AgentResponse(
                success=False,
                content="",
                error=str(e)
            )