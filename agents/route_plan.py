from typing import AsyncGenerator
from config.settings import settings
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, BaseMessage

# --- 修改点 1: 移除底层 mcp 库，引入 fastmcp 依赖 ---
from fastmcp.client import SSETransport
from fastmcp import Client

from core.logger import get_logger
from core.memory_manager import HybridMemoryManager
from core.mysql_history import UserMySQLHistoryManager
from core.llm_client import LLMClientFactory

logger = get_logger(__name__)


class RoutePlannerAgent:
    """
    出行规划 Agent 类，封装了 MCP 服务器的调用与大模型流式对话。
    （已重构为基于 fastmcp 的高级客户端实现）
    """

    def __init__(self, uid: str):
        # 初始化 LLM 客户端
        self.llm_client = LLMClientFactory().route_plan()
        # MCP Server 链接配置
        self.gaode_url = settings.GAODE_URL
        self.t12306_url = settings.T12306_URL

        self.history_manager = UserMySQLHistoryManager(uid=uid)
        self.memory_manager = HybridMemoryManager(llm=self.llm_client)

    async def stream_plan(self, user_query: str, session_id: str) -> AsyncGenerator[str, None]:
        """
        接收用户查询，调用大模型和相关工具，以流式生成器返回对话内容。
        """
        raw_history = self.history_manager.load(session_id)
        compressed_history = await self.memory_manager.get_compressed_history(raw_history)
        chat_history_str = self.memory_manager.format_for_prompt(compressed_history)

        # --- 修改点 2: 实例化 fastmcp 的传输层 ---
        gaode_transport = SSETransport(url=self.gaode_url)
        t12306_transport = SSETransport(url=self.t12306_url)

        # --- 修改点 3: 直接进入 fastmcp Client 上下文，它会自动处理底层流和 initialize 握手 ---
        async with Client(gaode_transport) as gaode_session, \
                Client(t12306_transport) as t12306_session:

            # 获取可用工具
            gaode_tools_res = await gaode_session.list_tools()
            t12306_tools_res = await t12306_session.list_tools()

            # 防御性编程：兼容不同 fastmcp/mcp 版本的返回格式（可能是对象包含.tools属性，也可能是直接返回列表）
            gaode_tools_list = getattr(gaode_tools_res, 'tools', gaode_tools_res)
            t12306_tools_list = getattr(t12306_tools_res, 'tools', t12306_tools_res)

            tool_session_map = {}
            llm_tools = []

            # 挂载高德工具
            for tool in gaode_tools_list:
                tool_session_map[tool.name] = gaode_session
                llm_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": getattr(tool, "inputSchema", getattr(tool, "input_schema", {}))
                    }
                })

            # 挂载 12306 工具
            for tool in t12306_tools_list:
                tool_session_map[tool.name] = t12306_session
                llm_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": getattr(tool, "inputSchema", getattr(tool, "input_schema", {}))
                    }
                })

            messages: list[BaseMessage] = [
                SystemMessage(content=f"你是一个专业的出行规划助手。请一步一步思考，合理调用工具来规划路线。"
                                      f"【历史对话记录（含长期记忆背景）】{chat_history_str}"),
                HumanMessage(content=user_query)
            ]

            logger.info(f"Agent initialized with tools: {[tool['function']['name'] for tool in llm_tools]}")
            logger.info(f"User: {user_query}\n" + "-" * 40)

            while True:
                logger.info("[思考中...] 等待大模型返回...")
                response_chunks = []

                async for chunk in self.llm_client.astream(messages, tools=llm_tools):
                    response_chunks.append(chunk)
                    if chunk.content:
                        yield chunk.content

                # 合并工具调用产生的多个 chunks
                response_message = response_chunks[0]
                for chunk in response_chunks[1:]:
                    response_message += chunk

                messages.append(response_message)

                if getattr(response_message, "tool_calls", None):
                    for tool_call in response_message.tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]
                        tool_call_id = tool_call["id"]

                        logger.info(f"[工具调用]: 准备调用 {tool_name}，参数: {tool_args}")

                        session = tool_session_map.get(tool_name)
                        if session:
                            try:
                                # --- 修改点 4: 调用方式保持一致，fastmcp 的 call_tool 签名和底层基本一样 ---
                                result = await session.call_tool(tool_name, arguments=tool_args)

                                # 兼容不同版本的返回解析
                                if hasattr(result, 'content') and result.content:
                                    tool_result_str = str(result.content[0].text) if hasattr(result.content[0],
                                                                                             'text') else str(
                                        result.content)
                                else:
                                    tool_result_str = str(result)

                                logger.info(f"[调用完成]: {tool_name} 返回成功")
                            except Exception as e:
                                tool_result_str = f"Error: {str(e)}"
                                logger.info(f"[调用失败]: {tool_name} - {str(e)}")
                        else:
                            tool_result_str = f"Error: Tool {tool_name} not found."

                        messages.append(ToolMessage(
                            tool_call_id=tool_call_id,
                            name=tool_name,
                            content=tool_result_str
                        ))
                else:
                    break

if __name__ == '__main__':
    import asyncio

    async def test_agent():
        agent = RoutePlannerAgent(uid="test_user")
        async for chunk in agent.stream_plan("帮我规划一下从北京到上海的出行路线。", session_id="test_session"):
            print(chunk, end="", flush=True)

    asyncio.run(test_agent())