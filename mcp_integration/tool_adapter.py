from typing import Callable, List, Optional
from contextlib import AsyncExitStack
from langchain_core.tools import Tool
from mcp_integration.client import get_mcp_client
from core.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)


class MCPAdapter:
    """
    MCP 适配器 - 核心转换类（异步长连接版）
    server_script_uri: MCP服务端地址
    """

    def __init__(self, mcp_server_uri: str = settings.MCP_SERVER_URI):
        self.mcp_client = get_mcp_client(mcp_server_uri)
        self.tools_cache = {}
        self.prompts_cache = {}
        self.resources_cache = {}

        # 用于管理连接状态
        self._exit_stack = AsyncExitStack()
        self._session = None  # 就是MCPClient对象

        logger.info("初始化 MCP 适配器实例")

    # ============ 生命周期管理 ============
    async def __aenter__(self):
        """进入上下文：建立连接"""
        logger.info("正在建立 MCP 长连接...")
        try:
            # 进入 mcp_client.connect() 的上下文，并保持住
            self._session = await self._exit_stack.enter_async_context(
                self.mcp_client.connect()
            )
            logger.info("✓ MCP 长连接已建立")
            return self
        except Exception as e:
            logger.error(f"建立连接失败: {e}")
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出上下文：断开连接"""
        try:
            logger.info("正在断开 MCP 长连接...")
            await self._exit_stack.aclose()
        finally:
            self._session = None
            logger.info("✓ MCP 连接已断开")

    @property
    def session(self):
        """获取当前活跃的 session，如果未连接则报错"""
        if self._session is None:
            raise RuntimeError(
                "MCPAdapter 未连接! 请在 'async with adapter:' 代码块中使用。"
            )
        return self._session

    # ============ Tools 相关 ============

    async def get_langgraph_tools(self) -> List[Tool]:
        """获取转换后的 LangGraph 工具列表"""
        try:
            # 直接使用 self.session (复用连接)
            mcp_tools = await self.session.list_tools()  # 真正获取MCP工具

            langgraph_tools = []
            for mcp_tool in mcp_tools:
                tool = Tool(
                    name=mcp_tool.name,
                    description=mcp_tool.description or f"MCP 工具: {mcp_tool.name}",
                    func=None,  # 同步程序去使用
                    coroutine=self._create_tool_function(mcp_tool.name)  # 异步程序
                )
                langgraph_tools.append(tool)
                self.tools_cache[mcp_tool.name] = mcp_tool

            logger.info(f"✓ 已加载 {len(langgraph_tools)} 个工具")
            return langgraph_tools
        except Exception as e:
            logger.error(f"工具转换失败: {str(e)}")
            raise


    def _create_tool_function(self, tool_name: str) -> Callable:
        """创建工具执行函数 (闭包中复用 session)"""

        # 签名增加 *args，允许接收 LangChain 传过来的位置参数
        async def tool_func(*args, **kwargs) -> str:
            try:
                # 智能提取参数。将大模型的输入整理成 MCP 需要的字典
                arguments = {}

                # 如果有关键字参数，合并进去
                if kwargs:
                    arguments.update(kwargs)

                # 处理 LangChain 最常见的位置参数行为
                if args:
                    first_arg = args[0]
                    if isinstance(first_arg, dict):
                        # 1. 大模型/Agent 直接传了字典
                        arguments.update(first_arg)

                result = await self.session.call_tool(tool_name, arguments)

                if hasattr(result, 'content') and result.content:
                    return str(result.content[0].text)
                return str(result)

            except Exception as e:
                error_msg = f"工具 {tool_name} 执行失败: {str(e)}"
                logger.error(error_msg)
                return error_msg

        return tool_func

    async def get_prompt(self, prompt_name: str, **kwargs) -> str:
        """
        获取提示词内容 (高级接口)
        """
        try:
            # return await self.session.get_prompt(prompt_name, arguments=arguments)
            # 智能处理参数，使其同时兼容 arguments={'key': 'value'} 和 key='value' 两种调用方式
            final_arguments = kwargs.get('arguments', kwargs)
            # 复用连接
            return await self.session.get_prompt(prompt_name, arguments=final_arguments)
        except Exception as e:
            logger.error(f"获取提示词失败: {e}")
            return ""

    # ============ Resources 相关 (新添加) ============ #
    async def read_resource(self, resource_uri: str) -> str:
        """
        读取资源内容 (高级接口)
        """
        try:
            # 复用连接
            return await self.session.read_resource(resource_uri)
        except Exception as e:
            logger.error(f"读取资源失败: {e}")
            return ""

# 单例模式

_adapter: Optional[MCPAdapter] = None


def get_mcp_adapter(mcp_server_uri: str) -> MCPAdapter:
    global _adapter
    if _adapter is None:
        _adapter = MCPAdapter(mcp_server_uri)
    return _adapter