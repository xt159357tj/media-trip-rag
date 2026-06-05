from contextlib import asynccontextmanager
from typing import Optional, List, Any, Dict
from fastmcp.client import StreamableHttpTransport
from fastmcp import Client

from core.logger import get_logger
logger = get_logger(__name__)

class MCPClient:
    def __init__(self, mcp_server_uri: str):
        self.transport = StreamableHttpTransport(url=mcp_server_uri)
        # 声明 fastmcp 中的 mcp client
        self.client: Optional[Client] = None
        # 声明 cache
        self._tools_cache = None
        self._prompts_cache = None
        self._resources_cache = None
        # logger
        logger.info(f"Initializing MCP Client : {self.transport}...")

    # 获取连接：异步 + Python 上下文管理器
    @asynccontextmanager
    async def connect(self):
        try:
            logger.info("Connecting to MCP Server...")
            # 获取 client 连接实例对象
            self.client = Client(
                self.transport,
            )

            async with self.client:
                # 进入此 代码块 后，执行相关 client 操作，离开此 代码块，自动关闭|释放 过程中的资源和连接
                await self.client.ping()
                logger.info("Init MCP Success. Connected to MCP Server...")

                # 转发 当前 类实例 中的资源（属性+方法 this方式提交）
                yield self

                # 结束之前，logger
                logger.info("disconnecting from MCP Server...")

        except Exception as e:
            logger.error(f"Connecting to MCP Server Error: {str(e)}")
            raise

    # 获取所有的工具
    async def list_tools(self) -> List[Any]:
        # cache 机制
        if self._tools_cache is not None:
            logger.debug("use tools cache...")
            return self._tools_cache
        try:
            logger.info(f"listing tools...{self.client}")
            tools = await self.client.list_tools()
            self._tools_cache = tools
            logger.info(f"get tools... len: {len(self._tools_cache)}")
            return self._tools_cache

        except Exception as e:
            logger.error(f"listing tools ERROR: {str(e)}")
            return []

    # 获取所有的提示词
    async def list_prompts(self) -> List[Any]:
        if self._prompts_cache is not None:
            logger.debug("use prompts cache...")
            return self._prompts_cache

        try:
            logger.info(f"listing prompts...{self.client}")
            prompts = await self.client.list_prompts()
            self._prompts_cache = prompts
            logger.info(f"get prompts... len: {len(self._prompts_cache)}")
            return self._prompts_cache
        except Exception as e:
            logger.error(f"listing prompts ERROR: {str(e)}")
            return []

    # 获取所有的资源
    async def list_resources(self) -> List[Any]:
        if self._resources_cache is not None:
            logger.debug("use resources cache...")
            return self._resources_cache
        try:
            logger.info(f"listing resources...{self.client}")
            resources = await self.client.list_resources()
            self._resources_cache = resources
            logger.info(f"get resources... len: {len(self._resources_cache)}")
            return self._resources_cache
        except Exception as e:
            logger.error(f"listing resources ERROR: {str(e)}")
            return []

    # 调用工具
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        调用 MCP 工具（异步）

        Args:
            tool_name: 工具名称
            arguments: 工具参数
        Returns:
             工具执行的结果
        """
        try:
            logger.info(f"calling tool: {tool_name}")
            logger.debug(f"arguments: {arguments}")

            responses = await self.client.call_tool(tool_name, arguments)
            logger.info(f"tool {tool_name} call success.")
            logger.debug(f"responses: {responses}")
            return responses
        except Exception as e:
            logger.error(f"tool {tool_name} call ERROR: {str(e)}")
            raise

    # 获取指定的提示词 (部分的完成了 for langchain/langgraph llm call 提示词适配)
    async def get_prompt(self, prompt_name: str, arguments: Dict[str, Any] = None) -> str:
        """
        获取提示词内容（异步）

        Args:
            prompt_name: 提示词名称
            arguments: 提示词参数
        Returns:
             渲染之后的提示词
        """
        try:
            logger.info(f"getting prompt: {prompt_name}")
            logger.debug(f"arguments: {arguments}")

            if arguments is None:
                arguments = {}

            responses = await self.client.get_prompt(prompt_name, arguments)
            # 提取 response 中的 提示词文本
            # 防御性编程方式
            if hasattr(responses, "messages") and responses.messages:
                content = responses.messages[0].content.text \
                    if hasattr(responses.messages[0], "text") \
                    else str(responses.messages[0].content)
                logger.info(f"get prompt success: {prompt_name}")
                return content
            return ""

        except Exception as e:
            logger.error(f"get prompt ERROR: {str(e)}")
            return ""

    # 读取指定的资源
    async def read_resource(self, resource_uri: str) -> str:
        """
        读取资源内容（异步）

        Args:
            resource_uri: 资源URI
        Returns:
             资源内容
        """
        try:
            logger.info(f"reading resource: {resource_uri}")
            resource = await self.client.read_resource(resource_uri)
            logger.info(f"read resource: {resource_uri}")
            return resource
        except Exception as e:
            logger.error(f"read resource ERROR: {str(e)}")
            return ""

# 全局实例
_client_instance: Optional[MCPClient] = None

def get_mcp_client(mcp_server_uri: str) -> MCPClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = MCPClient(mcp_server_uri)
    return _client_instance