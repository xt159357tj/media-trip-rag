import chromadb
import hashlib
import os
from pathlib import Path

# 导入封装好的本地离线 Embedding 引擎
from rag.mymodels import get_embeddings
from core.logger import get_logger

logger = get_logger(__name__)

class ChromaDBConnector:
    def __init__(self, collection_name: str = ""):
        # 1. 设定持久化数据库的路径
        current_file = Path(__file__).resolve()
        ROOT_DIR = current_file.parent.parent  # 根据实际项目层级调整
        self.vector_store_dir = ROOT_DIR / "data" / "chroma_db"
        os.makedirs(self.vector_store_dir, exist_ok=True)

        # 2. 创建持久化客户端
        self.client = chromadb.PersistentClient(path=str(self.vector_store_dir))

        # 3. 获取或创建集合 (Collection)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=None,  # 彻底解耦内置下载器
            metadata={"hnsw:space": "cosine"}  # 强制度量标准适配 BGE-m3
        )

    def add_chunks(self, chunks: list[str], metadatas: list[dict] = None, source_name: str = "unknown",
                   uid: str = None):
        """
        将切分好的文本块向量化并安全落盘，支持外部传入丰富的元数据。
        """
        if not chunks:
            logger.debug("警告：传入的 chunks 为空，取消落盘操作。")
            return
        logger.info(f" 正在启动本地模型，为 {len(chunks)} 个文本块生成向量...")

        # 调用离线引擎生成向量矩阵
        embedding_model = get_embeddings()

        # 2. 调用模型对象的 embed_documents 方法，将文本列表转化为向量列表
        embeddings = embedding_model.embed_documents(chunks)

        # 准备入库的载体
        ids = []
        final_metadatas = []

        # 【核心架构规则 3】：内容 Hash 法生成绝对唯一 ID
        for i, chunk in enumerate(chunks):
            chunk_hash = hashlib.md5(chunk.encode('utf-8')).hexdigest()
            ids.append(f"hash_{chunk_hash}")

            # 基础元数据
            base_meta = {
                "source": source_name,
                "chunk_length": len(chunk)
            }
            if uid:
                base_meta["uid"] = uid

            # 如果外部传入了切分器提取的元数据，进行融合
            if metadatas and i < len(metadatas) and metadatas[i]:
                # ChromaDB 要求 metadata 的 value 只能是 str, int, float, bool
                # 这里进行安全过滤，防止 LangChain 传过来复杂的嵌套对象报错
                valid_meta = {
                    k: v for k, v in metadatas[i].items()
                    if isinstance(v, (str, int, float, bool,list))
                }
                base_meta.update(valid_meta)

            final_metadatas.append(base_meta)

        logger.info(" 正在执行高速 Upsert 落盘...")
        self.collection.upsert(
            documents=chunks,
            embeddings=embeddings,
            metadatas=final_metadatas,
            ids=ids
        )
        logger.info("  落盘完毕！")

    def search(self, query: str, top_k: int = 5):
        # 1. 初始化并获取嵌入模型对象（什么参数都不用传，用默认的即可）
        embedding_model = get_embeddings()

        # 2. 调用 embed_query 将单条提问文本转为向量（注意这里是 embed_query 而不是 embed_documents）
        # 返回的是一个一维的浮点数列表 (List[float])
        query_vector = embedding_model.embed_query(query)

        # 3. 将向量传给 ChromaDB 进行查询
        results = self.collection.query(
            query_embeddings=[query_vector],  # ChromaDB 要求传入列表的列表
            n_results=top_k
            # 可以在这里预留 where={} 参数以后用于层级过滤
        )

        return results

    def delete_by_uid(self, uid: str):
        """
        删除指定 uid 的所有向量数据
        """
        self.collection.delete(where={"uid": uid})
        logger.info(f"已删除 uid={uid} 的所有向量数据。")

    def delete_by_source(self, source_name: str):
        """
        删除指定来源文档的所有向量数据
        """
        self.collection.delete(where={"source": source_name})
        logger.info(f"已删除文档 {source_name} 的所有向量数据。")

    def list_documents(self) -> list[dict]:
        """
        列出当前集合中的所有文档（按来源去重）
        """
        try:
            data = self.collection.get(include=["metadatas"])
            seen = set()
            docs = []
            for meta in (data.get("metadatas") or []):
                source = meta.get("source", "unknown") if meta else "unknown"
                if source not in seen:
                    seen.add(source)
                    docs.append({
                        "source": source,
                        "uid": (meta or {}).get("uid", ""),
                    })
            return docs
        except Exception as e:
            logger.error(f"列出文档失败: {e}")
            return []