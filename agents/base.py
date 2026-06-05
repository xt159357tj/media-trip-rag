from typing import List, Dict, Optional
from langchain_core.tools import Tool
from abc import ABC
from mcp_integration.tool_adapter import MCPAdapter

from core.llm_client import LLMClientFactory
from core.logger import get_logger

class BaseAgent(ABC):

    def __init__(self, mcp_tools: List[Tool], mcp_adapter: MCPAdapter, agent_type: str):
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

        self.llm = self._create_llm(agent_type)

        self.mcp_tools: Dict[str, Tool] = {tool.name: tool for tool in mcp_tools}

        self.mcp_adapter = mcp_adapter

        self.logger.info(f"{self.__class__.__name__} 初始化完成 (Type: {agent_type})")

    @staticmethod
    def _create_llm(agent_type: str):
        """内部 LLM 工厂调用映射"""
        # mapping 字典：存储的是函数对象本身（注意，如：写的是 LLMClientFactory.create_researcher，后面没有括号）
        mapping = {
            "rewriter":LLMClientFactory.create_rewriter,
            "reviewer": LLMClientFactory.create_reviewer,
            "chat":LLMClientFactory.create_chat
        }
        # 变量 creator 指向具体的函数
        # 如当 agent_type 是 "researcher" 时，creator 等于 LLMClientFactory.create_researcher
        creator = mapping.get(agent_type.lower())
        if not creator:
            raise ValueError(f"未定义的 Agent 类型: {agent_type}")

        # 这里的括号是真正的执行动作
        # 等同调用 LLMClientFactory.create_researcher() 并返回生成的 LLMClient 实例
        return creator()

    def get_tool(self, tool_name: str) -> Optional[Tool]:
        """安全获取工具方法"""
        tool = self.mcp_tools.get(tool_name)
        if not tool:
            self.logger.warning(f"⚠️ 工具 '{tool_name}' 在当前 MCP 环境中未找到")
        return tool