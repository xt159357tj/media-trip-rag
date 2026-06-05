import mimetypes
import os
import magic
from langchain_community.document_loaders import (
    UnstructuredPDFLoader,
    UnstructuredWordDocumentLoader,
    UnstructuredMarkdownLoader,
    UnstructuredHTMLLoader,
    TextLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter

# --- 新增导入 ---
from rag.chroma_connector import ChromaDBConnector
from core.logger import get_logger

logger = get_logger(__name__)

class SingleDocumentProcessor:
    def __init__(self, input_file, collection_name="default_collection", chunk_size=1000, chunk_overlap=200, uid="", original_filename=""):
        self.input_file = os.path.abspath(input_file)
        self.mime = magic.Magic(mime=True)

        self.collection_name = collection_name
        self.uid = uid
        self.original_filename = original_filename or os.path.basename(input_file)

        self.text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    separators=["\n\n", "\n", " ", ""]
                )

    def detect_file_type(self, filepath):
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, 'rb') as f:
                file_head = f.read(2048)
            return self.mime.from_buffer(file_head)
        except Exception as e:
            logger.error(f"magic 识别失败: {e}。尝试后缀名兜底...")
            mime_type, _ = mimetypes.guess_type(filepath)
            return mime_type

    def get_loader(self, filepath, mime_type):
        # DOCX 本质是 ZIP 格式，magic 会识别为 application/zip，通过后缀兜底
        if mime_type == "application/zip":
            ext = os.path.splitext(filepath)[1].lower()
            if ext in (".docx", ".doc"):
                return UnstructuredWordDocumentLoader(filepath, mode="single")

        if mime_type == "application/pdf":
            return UnstructuredPDFLoader(filepath)
        elif mime_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                           "application/msword"]:
            return UnstructuredWordDocumentLoader(filepath, mode="single")
        elif mime_type == "text/markdown":
            return UnstructuredMarkdownLoader(filepath)
        elif mime_type == "text/html":
            return UnstructuredHTMLLoader(filepath)
        elif mime_type and mime_type.startswith("text"):
            return TextLoader(filepath, encoding="utf-8")
        return None

    def _parse_to_text(self) -> list[str]:
        """
        解析文件并返回文本内容列表（不写中间文件）
        """
        logger.info(f"开始处理文件: {self.input_file}")
        if not os.path.exists(self.input_file):
            logger.error(f"错误: 文件不存在 {self.input_file}")
            return []

        mime_type = self.detect_file_type(self.input_file)
        loader = self.get_loader(self.input_file, mime_type)
        texts = []

        if loader:
            try:
                docs = loader.load()
                texts = [doc.page_content for doc in docs]
                logger.info(f"文件解析完成，共 {len(texts)} 段文本")
            except Exception as e:
                logger.error(f"解析失败 {self.input_file}: {e}")
        else:
            logger.info(f"未找到解析器，类型: {mime_type}")

        return texts

    def split_texts(self, texts: list[str]):
        """
        将文本列表切分为 Document 块
        """
        all_chunks = []
        for text in texts:
            metadatas = [{"source_file": self.original_filename}]
            chunks = self.text_splitter.create_documents([text], metadatas=metadatas)
            all_chunks.extend(chunks)
        return all_chunks

    def save_to_vector_db(self, chunks):
        """
        将切分后的 Document 对象列表保存到 ChromaDB
        """
        if not chunks:
            logger.error("错误: 没有可供保存的切块。")
            return

        texts = [doc.page_content for doc in chunks]
        metadatas = [doc.metadata for doc in chunks]

        db = ChromaDBConnector(collection_name=self.collection_name)

        logger.info(f"准备将 {len(texts)} 个切块存入向量库: {self.collection_name}...")
        db.add_chunks(
            chunks=texts,
            metadatas=metadatas,
            source_name=self.original_filename,
            uid=self.uid
        )


if __name__ == "__main__":
    target_file = "../test/人事管理流程.docx"

    processor = SingleDocumentProcessor(
        input_file=target_file,
        collection_name='test',
        chunk_size=500,
        chunk_overlap=50
    )

    # 1. 解析文件为文本（不写中间文件）
    texts = processor._parse_to_text()

    # 2. 进行切块
    if texts:
        document_chunks = processor.split_texts(texts)
        print(f"\n生成了 {len(document_chunks)} 个文本切块")
        print("\n--- 流程全部完成 ---")
    else:
        print("处理中断。")