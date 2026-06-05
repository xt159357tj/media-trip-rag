import jieba
from typing import List, Optional
from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage

# ===== 导入你的自定义模块 =====
from rag.chroma_connector import ChromaDBConnector
from rag.mymodels import get_reranker
from core.llm_client import LLMClientFactory
from core.logger import get_logger
from core.mysql_history import UserMySQLHistoryManager
from core.memory_manager import HybridMemoryManager

logger = get_logger(__name__)

class RAGPipeline:
    def __init__(self, collection_name: str = "metadata_collection", uid: Optional[str] = None):
        logger.info("正在初始化 RAG Pipeline...")

        # 1. 初始化 LLM 客户端 (调用专属 RAG 模型)
        self.llm_client = LLMClientFactory.create_rag_model()

        # 2. 初始化向量数据库连接器 (用于向量检索)
        self.db_connector = ChromaDBConnector(collection_name=collection_name)

        # 3. 全局加载 Reranker 模型 (避免反复加载导致爆内存)
        self.reranker = get_reranker()

        # 4. 初始化 BM25 检索器相关属性
        self.bm25_retriever = None
        self.all_docs = []
        self._init_bm25()

        # 5. 初始化记忆管理器
        self.uid = uid
        if uid:
            self.history_manager = UserMySQLHistoryManager(uid=uid)
            self.memory_manager = HybridMemoryManager(llm=self.llm_client)
            logger.info(f"RAG 记忆管理器已就绪 (uid={uid})")
        else:
            self.history_manager = None
            self.memory_manager = None

    @staticmethod
    def jieba_tokenize(text: str) -> List[str]:
        """自定义分词函数"""
        return list(jieba.cut(text))

    def _init_bm25(self):
        """预加载 BM25 索引，避免每次检索时重复加载引发卡顿"""
        logger.info("正在构建全局 BM25 索引...")
        try:
            # 从 ChromaDB 集合中取出所有落盘的数据
            all_data = self.db_connector.collection.get()
            documents = all_data.get('documents', [])
            metadatas = all_data.get('metadatas', [])

            if not documents:
                logger.error("警告：向量数据库中没有文档，BM25 索引为空！")
                return

            self.all_docs = [
                Document(page_content=t, metadata=m if m else {})
                for t, m in zip(documents, metadatas) if t
            ]

            # 建立 BM25 内存索引
            self.bm25_retriever = BM25Retriever.from_documents(
                self.all_docs,
                preprocess_func=self.jieba_tokenize
            )
            logger.info("BM25 索引构建完成，共加载 %d 条文档。", len(self.all_docs))
        except Exception as e:
            logger.error(f"BM25 索引构建失败: {e}")

    def _rrf_dedup(self, list_of_lists: List[List[str]], k: int = 60) -> List[str]:
        """
        使用 RRF (Reciprocal Rank Fusion) 算法合并多路结果并进行精准去重
        """
        rrf_scores = {}
        for doc_list in list_of_lists:
            for rank, doc in enumerate(doc_list, start=1):
                clean_text = doc.strip()
                if not clean_text:
                    continue

                if clean_text not in rrf_scores:
                    rrf_scores[clean_text] = 0.0

                # 累加得分实现去重与重算权重
                rrf_scores[clean_text] += 1.0 / (k + rank)

        # 根据累加后的 RRF 得分降序排序
        sorted_docs = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        return [doc for doc, score in sorted_docs]

    def retrieve_and_rerank(self, query: str, top_k: int = 5) -> List[str]:
        """
        执行完整检索链路：多路召回 -> 去重粗排 -> Rerank精排
        """
        # 设置召回层数量（为精排提供足够的候选集，通常为 top_k 的 2 倍以上）
        recall_k = max(10, top_k * 2)

        # ================= 1. 多路召回 =================
        # 1.1 数据库检索 (稠密向量匹配)
        vector_results = self.db_connector.search(query, top_k=recall_k)
        vector_docs = vector_results.get('documents', [[]])[0] if vector_results and vector_results.get(
            'documents') else []

        # 1.2 关键词检索 (BM25 稀疏匹配)
        bm25_docs = []
        if self.bm25_retriever:
            tokenized_query = self.jieba_tokenize(query)
            all_bm25_scores = self.bm25_retriever.vectorizer.get_scores(tokenized_query)

            # 获取得分最高的前 recall_k 个索引
            bm25_top_indices = sorted(
                range(len(all_bm25_scores)),
                key=lambda i: all_bm25_scores[i],
                reverse=True
            )[:recall_k]

            for idx in bm25_top_indices:
                if all_bm25_scores[idx] > 0:
                    bm25_docs.append(self.all_docs[idx].page_content)

        # ================= 2. 去重与粗排 =================
        # 将两路召回结果送入 RRF 算法打分并实现自动去重
        unique_candidates = self._rrf_dedup([vector_docs, bm25_docs])

        if not unique_candidates:
            return []

        # 截取前 recall_k 个有效结果进入精排阶段
        candidates_for_rerank = unique_candidates[:recall_k]

        # ================= 3. Rerank 精排 =================
        # 构建交叉打分 Pair
        pairs = [(query, t) for t in candidates_for_rerank]

        # 调用 Reranker 模型计算相似度得分
        scores = list(self.reranker.score(pairs))

        # 关联得分、排序并截取最终的 Top-K 结果
        scored_texts = sorted(
            zip(candidates_for_rerank, scores),
            key=lambda x: x[1],
            reverse=True
        )

        final_results = [text for text, _ in scored_texts][:top_k]

        return final_results

    async def generate_answer(self, query: str, top_k: int = 5, session_id: Optional[str] = None):
        """
        组装最终答案（含上下文记忆）
        """
        logger.info(f"正在处理查询: {query}")

        # 0. 加载并压缩历史对话，作为上下文记忆
        chat_history_str = "暂无历史对话。"
        if self.history_manager and session_id:
            try:
                raw_history = self.history_manager.load(session_id)
                compressed_history = await self.memory_manager.get_compressed_history(raw_history)
                chat_history_str = self.memory_manager.format_for_prompt(compressed_history)
                logger.info(f"[RAG] 已加载 session {session_id} 的历史记忆")
            except Exception as e:
                logger.warning(f"[RAG] 加载历史记忆失败: {e}")

        # 1. 执行核心的检索与重排动作
        context_docs = self.retrieve_and_rerank(query, top_k=top_k)

        if not context_docs:
            yield "抱歉，知识库中没有检索到相关的参考信息，无法回答该问题。"
            return

        # 2. 组装 Prompt（含历史记忆上下文）
        context_str = "\n\n---\n\n".join(context_docs)
        prompt = (
            f"【历史对话记录】\n{chat_history_str}\n\n"
            f"请基于以下已知内容，结合历史对话上下文回答问题，适当总结归纳。"
            f"如果已知内容无法回答该问题，请直接回答'根据已知信息无法回答该问题'，不要编造。\n\n"
            f"已知内容:\n{context_str}\n\n"
            "请结合以上信息回答问题"
        )

        messages: list[BaseMessage] = [SystemMessage(content=prompt), HumanMessage(content=query)]

        # 3. 调用 LLM 客户端生成回答
        logger.info("[RAG] 正在调用 LLM 生成回答...")

        async for chunk in self.llm_client.astream(messages):
            yield chunk.content

        logger.info("\n[RAG] 回答生成完成。")


# ==========================================
# 调试入口
# ==========================================
if __name__ == "__main__":
    import asyncio


    async def main():
        # 初始化 RAG 系统
        rag = RAGPipeline(collection_name="test", uid="test_user")

        test_query = "怎么安装cuda"

        print("\n================= 生成回答 =================")
        # 必须在 async 环境下使用 async for
        async for chunk in rag.generate_answer(query=test_query, top_k=3):
            print(chunk, end="", flush=True)
            pass

        print("\n===========================================")


    # 启动异步事件循环
    asyncio.run(main())


