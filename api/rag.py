from __future__ import annotations

import os
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from api.deps import get_current_uid
from api.models import APIResponse
from config.settings import settings
from core.logger import get_logger
from rag.spliter import SingleDocumentProcessor
from rag.chroma_connector import ChromaDBConnector

router = APIRouter(tags=["知识库"])

logger = get_logger(__name__)

ALLOWED_DOC_TYPES: set[str] = {
    ".pdf", ".docx", ".doc", ".txt", ".md", ".markdown", ".html", ".htm",
}
MAX_DOC_SIZE: int = 50 * 1024 * 1024  # 50 MiB


@router.post("/rag/upload", response_model=APIResponse)
async def upload_document(
    uid: Annotated[str, Depends(get_current_uid)],
    file: UploadFile = File(...),
):
    """上传文档到用户专属知识库，自动解析、切分并写入向量库"""
    ext = os.path.splitext(file.filename or "doc.txt")[1].lower()
    if ext not in ALLOWED_DOC_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 400, "message": f"不支持的文件类型: {ext}"},
        )

    tmp_dir = os.path.join(settings.BASE_DIR, "data", "tmp_uploads")
    os.makedirs(tmp_dir, exist_ok=True)

    name, ext = os.path.splitext(file.filename)
    safe_name = f"{name}_{uuid.uuid4().hex}{ext}"
    tmp_path = os.path.join(tmp_dir, safe_name)

    try:
        total = 0
        with open(tmp_path, "wb") as f:
            while chunk := await file.read(8 * 1024 * 1024):
                total += len(chunk)
                if total > MAX_DOC_SIZE:
                    f.close()
                    os.remove(tmp_path)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail={"code": 413, "message": "文件大小超过 50MB 限制"},
                    )
                f.write(chunk)
    except HTTPException:
        raise
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": 500, "message": "文件写入失败"},
        )

    try:
        processor = SingleDocumentProcessor(
            input_file=tmp_path,
            collection_name=uid,
            chunk_size=1000,
            chunk_overlap=200,
            uid=uid,
            original_filename=file.filename,
        )

        texts = processor._parse_to_text()
        if not texts:
            return APIResponse(code=400, message="无法解析该文件，请检查文件格式。")

        chunks = processor.split_texts(texts)
        if not chunks:
            return APIResponse(code=400, message="文件内容为空，无法切分。")

        processor.save_to_vector_db(chunks)

        logger.info(f"文档入库成功: {file.filename} → 集合 {uid} ({len(chunks)} chunks)")
        return APIResponse(message=f"文档 '{file.filename}' 已成功添加到知识库（{len(chunks)} 个片段）")
    except Exception as e:
        logger.error(f"文档处理失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": 500, "message": f"文档处理失败: {e}"},
        )
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.get("/rag/documents", response_model=APIResponse)
async def list_documents(uid: Annotated[str, Depends(get_current_uid)]):
    """列出当前用户知识库中的所有文档"""
    db = ChromaDBConnector(collection_name=uid)
    docs = db.list_documents()
    return APIResponse(data={"documents": docs, "total": len(docs)})


@router.delete("/rag/documents/{source_name}", response_model=APIResponse)
async def delete_document(
    source_name: str,
    uid: Annotated[str, Depends(get_current_uid)],
):
    """从知识库中删除指定文档及其中间文件"""
    db = ChromaDBConnector(collection_name=uid)
    db.delete_by_source(source_name)

    return APIResponse(message=f"文档 '{source_name}' 已从知识库删除")


@router.delete("/rag/documents", response_model=APIResponse)
async def clear_knowledge_base(uid: Annotated[str, Depends(get_current_uid)]):
    """清空当前用户的全部知识库"""
    db = ChromaDBConnector(collection_name=uid)
    db.collection.delete(where={})
    return APIResponse(message="知识库已清空")
