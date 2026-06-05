# memory_manager.py
from langchain_core.messages import HumanMessage

from core.logger import get_logger

# 获取当前模块的日志记录器
logger = get_logger(__name__)


class HybridMemoryManager:
    def __init__(self, llm, summary_threshold: int = 6, window_size: int = 4):
        """
        初始化混合记忆管理器
        :param llm: 用于生成摘要的大语言模型实例
        :param summary_threshold: 触发压缩的阈值（扁平化后总条数超过此值时触发压缩）
        :param window_size: 滑动窗口大小（保留最近的 N 条原话不被压缩）
        """
        self.llm = llm
        self.summary_threshold = summary_threshold
        self.window_size = window_size

        logger.info(
            f"HybridMemoryManager 初始化完成 | summary_threshold={summary_threshold}, window_size={window_size}")

    def _normalize_history(self, raw_history: list[dict]) -> list[dict]:
        """
        预处理工具：将外部传入的新型嵌套聊天记录统一展平为标准格式。
        标准格式：[{"role": "user"/"assistant"/"system", "content": "..."}]
        """
        normalized = []
        if not raw_history:
            return normalized

        for item in raw_history:
            # 兼容已经是标准格式的情况（比如可能混入了带有前序摘要的 system role）
            if "role" in item and "content" in item:
                normalized.append(item)
            else:
                # 解析传入的新格式 {"user": [{"type": "text", "content": "..."}], "assistant": [...]}
                if "user" in item:
                    # 提取所有 type 为 text 的 content 并拼接
                    user_content = "".join(
                        [part.get("content", "") for part in item["user"] if part.get("type") == "text"])
                    if user_content:
                        normalized.append({"role": "user", "content": user_content})

                if "assistant" in item:
                    assistant_content = "".join(
                        [part.get("content", "") for part in item["assistant"] if part.get("type") == "text"])
                    if assistant_content:
                        normalized.append({"role": "assistant", "content": assistant_content})

        return normalized

    async def get_compressed_history(self, raw_history: list[dict]) -> list[dict]:
        """
        执行长短时混合记忆压缩策略（增量摘要）
        传入原始历史记录列表，返回压缩后的历史记录列表（统一为扁平化格式）。
        """
        # 0. 预处理：将传入的嵌套字典格式转换为标准的扁平格式
        standard_history = self._normalize_history(raw_history)

        history_len = len(standard_history)
        if not standard_history or history_len <= self.summary_threshold:
            logger.debug(f"当前历史记录长度 ({history_len}) 未超过阈值 ({self.summary_threshold})，跳过压缩。")
            return standard_history

        existing_summary = ""
        actual_messages = []

        # 1. 分离已有的摘要和实际对话消息
        for msg in standard_history:
            if msg.get("role") == "system" and "对话背景：" in msg.get("content", ""):
                existing_summary = msg.get("content")
            else:
                actual_messages.append(msg)

        # 如果剔除摘要后，剩下的真实对话依然没超过窗口限制，无需再压缩
        if len(actual_messages) <= self.window_size:
            logger.debug(
                f"剔除旧摘要后，真实对话数 ({len(actual_messages)}) 未超过窗口大小 ({self.window_size})，跳过压缩。")
            return standard_history

        logger.info(f"触发混合记忆压缩，处理历史消息总数：{len(actual_messages)}")

        # 2. 划分长短期记忆区域
        short_term_memory = actual_messages[-self.window_size:]
        long_term_to_summarize = actual_messages[:-self.window_size]

        # 将需要压缩的长时记忆转为纯文本，以便喂给 LLM 总结
        long_term_text = ""
        for m in long_term_to_summarize:
            role_name = "用户" if m.get("role") == "user" else "assistant"
            long_term_text += f"{role_name}: {m.get('content')}\n"

        # 3. 生成增量摘要
        summary_prompt = f"""
        现有的对话背景：{existing_summary if existing_summary else "无"}

        请将以下新增的对话内容并入上述背景中，生成一份更新后的简短摘要：
        {long_term_text}

        要求：保持客观简洁，提炼核心事实、用户意图和关键技术术语。
        """

        logger.debug(f"开始调用 LLM 生成增量摘要，待压缩长时记忆条数：{len(long_term_to_summarize)}")

        # 调用大模型生成摘要，添加异常捕获以防网络或模型调用失败
        try:
            new_summary_content = await self.llm.ainvoke([HumanMessage(content=summary_prompt)])
            logger.info("增量摘要生成成功。")
        except Exception as e:
            logger.error(f"调用 LLM 生成记忆摘要时发生异常: {str(e)}", exc_info=True)
            # 发生异常时，为了不中断对话，返回已展平的历史记录
            return standard_history

        # 4. 重构新的压缩上下文链路
        new_history = [
            {"role": "system", "content": f"对话背景：{new_summary_content}"}
        ]
        # 追加近期滑动窗口中的原话
        new_history.extend(short_term_memory)

        logger.debug(f"上下文链路重构完成，压缩后总上下文条数：{len(new_history)}")
        return new_history

    def format_for_prompt(self, compressed_history: list[dict]) -> str:
        """
        将压缩后的历史记录列表转换为最终输入 RAG Prompt 的纯文本格式
        """
        if not compressed_history:
            logger.debug("传入格式化的历史记录为空。")
            return "暂无历史对话。"

        formatted_text = ""
        for msg in compressed_history:
            role = msg.get("role")
            if role == "system":
                role_name = "【系统长期记忆】"
            elif role == "user":
                role_name = "用户"
            else:
                role_name = "AI"

            content = msg.get("content", "")
            formatted_text += f"{role_name}: {content}\n"

        return formatted_text