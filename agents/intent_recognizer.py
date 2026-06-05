"""
意图识别智能体 - 异步版本
核心任务：分析用户的 user_input，输出 WorkflowState 中定义的 intent（chat 或 workflow）
"""
from langchain_core.messages import BaseMessage, SystemMessage

from core.llm_client import LLMClientFactory
from core.logger import get_logger
from workflow.state import AgentResponse

logger = get_logger(__name__)


class IntentRecognizer:
    """意图识别智能体：负责判断用户意图是普通对话还是工作流任务"""

    def __init__(self):
        """初始化意图识别器"""
        # 使用工厂模式创建专门用于意图识别的客户端（低温度系数，保证稳定性，即：尽量保证每次AI回答一致。）
        self.llm = LLMClientFactory.create_intent_recognizer()
        logger.info("初始化意图识别智能体")

    # 异步方法：高并发设计的核心，允许同时处理多个用户输入，提高系统响应能力。
    # 在生产环境中，当多个用户同时访问时，异步处理可以避免线程阻塞，提高响应速度。
    async def recognize(self, user_input: str) -> AgentResponse:
        """
        识别用户意图（异步）

        Args:
            user_input: 用户输入

        Returns:
            意图识别结果
        """
        try:
            logger.info(f"识别用户意图: {user_input[:50]}...")

            prompt = """请分析用户输入，判断用户的意图是什么。

            用户输入: {user_input}

            请回答以下问题：
            1. 用户的意图是什么？(chat/workflow/route-plan/rag)
               - chat: 普通对话(包含联网搜索功能)
               - workflow: 视频字幕生成工作流
               - route_plan: 路线规划，旅游攻略，天气状况，查询火车、高铁票相关问题
               - rag: 用户输入中提到使用知识库回答问题时才考虑
            2. 置信度是多少？(0-1)

            格式：
            意图: [intent]
            置信度: [confidence]"""

            messages: list[BaseMessage] = [SystemMessage(content=prompt.format(user_input=user_input))]

            # 获取 llm 响应
            response_text = await self.llm.ainvoke(messages)

            # 解析响应
            # Default State，兜底策略：网络请求或 LLM 输出是不稳定的，默认意图是 chat，默认置信度是 0.5。
            # 先设定 intent = "chat" 是一种保守策略：如果 AI 的回答混乱，宁愿理解为普通聊天，也不要在没有足够信息的情况下错误地启动复杂的工作流。
            intent = "chat"
            confidence = 0.5

            # 响应解析逻辑 (Parser): 通过简单的字符串搜索来确定意图和置信度。
            if "workflow" in response_text.lower():     # 鲁棒性（Robustness）处理，即便 LLM 输出较多，只要包含关键词就能识别。
                intent = "workflow"
            elif "route-plan" in response_text.lower() or "route_plan" in response_text.lower():
                intent = "route_plan"
            elif "rag" in response_text.lower():
                intent = "RAG"
            if "置信度:" in response_text or "confidence:" in response_text.lower():
                try:
                    # 第一步 split("置信度:")[-1]：横向切割，拿掉标签左边的内容
                    # 第二步 split("\n")[0]：纵向切割，拿掉数据下方的噪音
                    parts = response_text.split("置信度:")[-1].split("\n")[0]    # 去除 末尾 \n
                    confidence = float(parts.strip())                           # 清除残留空格
                except Exception as e:
                    # 防御性编程：当解析失败时（except 分支），给出一个保底的置信度，系统解析不出就给出一个默认值。
                    confidence = 0.7 if intent != "chat" else 0.5

            logger.info(f"✓ 意图识别完成: {intent} (置信度: {confidence})")

            # 封装 Angent 响应
            return AgentResponse(
                success=True,
                content={
                    "intent": intent,
                    "confidence": confidence
                },
                metadata={"user_input": user_input[:50]}
            )

        except Exception as e:
            logger.error(f"意图识别失败: {str(e)}")
            return AgentResponse(
                success=False,
                error=str(e),
                content={"intent": "chat", "confidence": 0.5}
            )

r"""拓展： 为什么 Agent 不使用 state(WorkflowState)，而使用 其中的 user_input
1. 职责边界 (Single Responsibility)
    IntentRecognizer 的任务单一：识别用户输入，给出判断和置信度。
    不需要知道 WorkflowState 里的其他信息（比如 search_results 或 review_count）。
    直接传入 user_input 字符串，这个类容易进行单元测试，而不必去构造一个复杂的 WorkflowState 字典。
2. “窄接口”原则 (Narrow Interface)
    软件项目中，接口越窄（输入越少），模块间的耦合度就越低。
    优势：如果将来想在另一个完全不同的项目里复用这个意图识别器，只需要传入字符串就行了，而不需要搬运整个项目的 WorkflowState 定义。
3. 编排权在 graph.py
    真正的执行逻辑：在 workflow/graph.py 中，会有代码类似：
        # 逻辑模拟
        response = await intent_recognizer.recognize(state["user_input"])
        # 然后在 graph 节点中统一更新 state
        return {"intent": response.content["intent"]}
高级的“计算与状态分离”的设计：Agent 负责逻辑计算，Graph 负责状态读写。
"""