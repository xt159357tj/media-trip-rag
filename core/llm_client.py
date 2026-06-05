from typing import Optional
import asyncio
import dashscope
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage

from config.settings import settings
from core.logger import get_logger

# 获取 单例的 logger 对象，指向|指定 当前模块名称
logger = get_logger(__name__)


class LLMClient:
    def __init__(
            self,
            model_name: str = None,
            temperature: float = 0.7,
            # 兼顾成本，指定最多输出的 token 数，防止模型无限输出
            max_tokens: Optional[int] = None,
    ):
        self.temperature = temperature
        self.max_tokens = max_tokens

        self.model_name = model_name
        if self.model_name == 'deepseek':
            self.llm = ChatOpenAI(
                model=settings.DEEPSEEK_MODEL,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
            )
        elif self.model_name == 'qwen':
            # 配置 Dashscope API Key
            dashscope.api_key = settings.DASHSCOPE_API_KEY
            self.omni_model = settings.DASHSCOPE_MODEL

        logger.info(f"LLM client initialized with model: {self.model_name}")


    @staticmethod
    def _summary(prompt) -> str:
        s = str(prompt)
        return s[:120] + f"...({len(s)} chars)" if len(s) > 120 else s

    # 异步调用方式
    async def ainvoke(self, prompt, audio_url: Optional[str] = None) -> str:
        try:
            logger.info(f"AInvoke: {self._summary(prompt)}")
            logger.debug(f"LLM Model: {self.model_name}")

            if self.model_name == 'qwen':
                if isinstance(prompt, list) and all(isinstance(m, dict) for m in prompt):
                    messages = prompt
                else:
                    content_list = []
                    if audio_url:
                        content_list.append({"audio": audio_url})
                    content_list.append({"text": prompt})
                    messages = [{"role": "user", "content": content_list}]

                response = await asyncio.to_thread(
                    dashscope.MultiModalConversation.call,
                    model=self.omni_model,
                    messages=messages,
                    result_format="message"
                )

                if response.status_code == 200:
                    result_message = response.output.choices[0].message
                    if isinstance(result_message.content, list):
                        res_text = " ".join([c.get("text", "") for c in result_message.content if "text" in c])
                    else:
                        res_text = result_message.content
                    return res_text
                else:
                    error_msg = f"调用失败: 错误码 {response.code} - 错误信息 {response.message}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
            else:
                response = await self.llm.ainvoke(prompt)
                content = response.content
                logger.debug(f"LLM response length: {len(content)}")
                return content
        except Exception as e:
            logger.error(f"LLM async invocation failed with error: {e}")
            raise e

    # 流式调用
    async def astream(self, prompt: list[BaseMessage], **kwargs):
        """
        :param prompt: 用户的文本提示词
        :param kwargs: 支持传入 audio_url="path/to/audio.wav"
        """
        try:
            logger.debug(f"LLM Model: {self.model_name}")

            if self.model_name == 'qwen':
                # 1. 准备音频参数
                audio_url = kwargs.get('audio_url')

                # 2. 将 prompt 和音频构建为 Dashscope 多模态格式
                content_list = []

                # 如果传入了音频，则作为用户消息的第一个内容块加入
                if audio_url:
                    content_list.append({"audio": audio_url})

                # 加入文本提示词
                content_list.append({"text": prompt})

                dashscope_messages = [
                    {"role": "user", "content": content_list}
                ]

                # 3. 调用 Dashscope 的流式接口
                responses = dashscope.MultiModalConversation.call(
                    model=self.omni_model,
                    messages=dashscope_messages,
                    result_format="message",
                    stream=True  # 开启流式
                )

                for response in responses:
                    if response.status_code == 200:
                        # 提取文本片段
                        chunk = response.output.choices[0].message.content
                        if isinstance(chunk, list):
                            for item in chunk:
                                if "text" in item:
                                    yield item["text"]
                        elif isinstance(chunk, str):
                            yield chunk
                    else:
                        raise Exception(f"流式调用失败: {response.message}")

            else:
                # 传统的 LangChain 文本模型流式逻辑
                # 大多数 LangChain 的模型 astream 方法都直接支持传入字符串 prompt
                async for chunk in self.llm.astream(prompt, **kwargs):
                    # 【修改这里】直接 yield 完整的 chunk 对象，保留工具调用的元数据
                    yield chunk
        except Exception as e:
            logger.error(f"LLM streaming invocation failed with error: {e}")
            raise e


# 是生成 LLMClient 实例 的工厂（方法，应均为静态的类方法）
# 可是给 不同的 Agent 指定不同的 model（族、子模型）
class LLMClientFactory:
    @staticmethod
    def create_chat():
        return LLMClient(
            model_name="deepseek",
            temperature=0.7,
            max_tokens=500,
        )

    @staticmethod
    def route_plan() -> LLMClient:
        return LLMClient(
            model_name="deepseek",
            temperature=0.1,
            max_tokens=1000,
        )

    @staticmethod
    def create_reviewer() -> LLMClient:
        return LLMClient(
            model_name="qwen",
            temperature=0.2,
            max_tokens=3000,
        )

    @staticmethod
    def create_rewriter() -> LLMClient:
        return LLMClient(
            model_name="deepseek",
            temperature=0.1,
            max_tokens=3000,
        )

    @staticmethod
    def create_intent_recognizer() -> LLMClient:
        return LLMClient(
            model_name="deepseek",
            temperature=0.0,
            max_tokens=200,
        )

    @staticmethod
    def create_rag_model() -> LLMClient:
        return LLMClient(
            model_name="deepseek",
            temperature=0.3,
            max_tokens=2000,
        )
