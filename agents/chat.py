import asyncio
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, BaseMessage

from agents.base import BaseAgent
from mcp_integration.tool_adapter import MCPAdapter

from core.memory_manager import HybridMemoryManager
from core.mysql_history import UserMySQLHistoryManager


class Chat(BaseAgent):
    def __init__(self, mcp_tools, mcp_adapter: MCPAdapter, uid: str):
        super().__init__(mcp_tools, mcp_adapter, "chat")

        self.web_search_tool = self.get_tool("web_search")
        self.get_time_tool = self.get_tool("get_time")

        self.history_manager = UserMySQLHistoryManager(uid=uid)
        self.memory_manager = HybridMemoryManager(llm=self.llm)

        self.logger.info(f"Chat智能体初始化完成（已挂载LLM Client及用户 {uid} 的记忆管理器）")

    async def chat(self, user_input: str, session_id: str = None):
        """开始对话 — 手动 ReAct 循环实现 token 级流式输出"""

        raw_history = self.history_manager.load(session_id)
        compressed_history = await self.memory_manager.get_compressed_history(raw_history)
        chat_history_str = self.memory_manager.format_for_prompt(compressed_history)

        tool_descriptions = "\n".join(
            f"- {t.name}: {t.description}" for t in (self.web_search_tool, self.get_time_tool) if t
        )

        system_prompt = f"""你是一个全能的智能助手。尽你所能回答用户的问题。
你可以使用以下工具：

{tool_descriptions}

【历史对话记录（含长期记忆背景）】
{chat_history_str}

执行规则：
1. 时间第一：在回答任何涉及"现任"、"目前"、"年龄"的问题前，必须先调用 `get_time` 工具确认今天的日期。
2. 严禁假设：必须以工具返回的日期为准进行计算。
3. 事实核查：对于涉及人物职务、实时新闻、具体数值，你必须使用 `web_search` 工具进行核实，严禁编造。
4. 链式执行：获取时间 -> 搜索事实。
5. 对话连贯：请结合上方的【历史对话记录】上下文来理解用户的当前意图。"""

        messages: list[BaseMessage] = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_input),
        ]

        formatted_tools = [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": self.web_search_tool.description if self.web_search_tool else "搜索网页信息的工具",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "要搜索的关键词"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_time",
                    "description": self.get_time_tool.description if self.get_time_tool else "获取当前系统时间的工具",
                    "parameters": {
                        "type": "object",
                        "properties": {},  # 明确告知大模型不需要传入任何参数
                        "required": []
                    }
                }
            }
        ]

        max_iterations = 10
        for _ in range(max_iterations):
            response_chunks = []

            # 3. 将手动定义好的 Schema 传给底层模型
            async for chunk in self.llm.astream(messages, tools=formatted_tools):
                response_chunks.append(chunk)

                # 如果 chunk 包含文本内容，通过 yield 流式抛出
                if chunk.content:
                    yield chunk.content

            # 如果没有收集到任何返回值则退出
            if not response_chunks:
                break

            # 合并 chunks 获取完整回复
            response_message = response_chunks[0]
            for chunk in response_chunks[1:]:
                response_message += chunk

            # 记录完整的模型回复
            messages.append(response_message)

            # 4. 检查模型是否决定调用工具
            if getattr(response_message, "tool_calls", None):
                for tool_call in response_message.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    tool_call_id = tool_call.get("id", "")

                    self.logger.info(f"[工具调用]: 准备调用 {tool_name}，参数: {tool_args}")

                    # 5. 从 mcp_tools 字典中查找可执行的工具对象
                    tool = self.mcp_tools.get(tool_name)
                    if tool and hasattr(tool, 'coroutine'):
                        try:
                            # 执行原生 MCP 的异步函数，传入大模型生成的合法参数
                            result = await tool.coroutine(**tool_args)
                            tool_result_str = str(result)
                            self.logger.info(f"[调用完成]: {tool_name} 返回成功")
                        except Exception as e:
                            tool_result_str = f"Error: {str(e)}"
                            self.logger.error(f"[调用失败]: {tool_name} - {str(e)}")
                    else:
                        tool_result_str = f"Error: Tool {tool_name} not found or not executable."

                    messages.append(ToolMessage(
                        content=tool_result_str,
                        tool_call_id=tool_call_id
                    ))
            else:
                # 模型没有工具调用请求时，结束 ReAct 循环
                break


if __name__ == '__main__':
    async def main():
        async with MCPAdapter() as mcp_adapter:
            mcp_tools = await mcp_adapter.get_langgraph_tools()

            test_uid = "user_9527"
            current_session = "session_2024_05_08_test1"

            chat_agent = Chat(mcp_tools, mcp_adapter, uid=test_uid)

            print("--- 对话测试 ---")
            query_1 = "现任美国总统是谁？"
            async for response in chat_agent.chat(query_1, session_id=current_session):
                print(response, end="", flush=True)
            print()


    asyncio.run(main())