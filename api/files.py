from __future__ import annotations

import os
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from api.deps import get_current_uid
from api.models import APIResponse, FileItem, FileUploadResult
from config.settings import settings
from core.logger import get_logger

router = APIRouter(tags=["文件管理"])

logger = get_logger(__name__)

ALLOWED_EXTENSIONS: set[str] = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".wmv"}
MAX_UPLOAD_SIZE: int = 500 * 1024 * 1024  # 500 MiB


@router.post("/upload/video", response_model=APIResponse)
async def upload_video(
    uid: Annotated[str, Depends(get_current_uid)],
    file: UploadFile = File(...),
):
    """上传视频文件，返回存储路径供后续工作流使用"""
    ext = os.path.splitext(file.filename or "video.mp4")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 400, "message": f"不支持的文件类型: {ext}，仅允许: {', '.join(ALLOWED_EXTENSIONS)}"},
        )

    os.makedirs(settings.ORIGINAL_VIDEO_PATH, exist_ok=True)

    safe_name = f"{uuid.uuid4().hex}_{file.filename}"
    dest_path = os.path.join(settings.ORIGINAL_VIDEO_PATH, safe_name)

    total = 0
    try:
        with open(dest_path, "wb") as f:
            while chunk := await file.read(8 * 1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_SIZE:
                    f.close()
                    os.remove(dest_path)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail={"code": 413, "message": "文件大小超过 500MB 限制"},
                    )
                f.write(chunk)
    except HTTPException:
        raise
    except Exception:
        if os.path.exists(dest_path):
            os.remove(dest_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": 500, "message": "文件写入失败"},
        )

    url = f"/static_uploads/{safe_name}"
    result = FileUploadResult(filename=safe_name, file_path=dest_path, url=url, size=total)
    logger.info(f"文件上传成功: {safe_name} ({total} bytes)")
    return APIResponse(data=result)


@router.get("/videos", response_model=APIResponse)
async def list_videos(uid: Annotated[str, Depends(get_current_uid)]):
    """列出已上传的视频文件"""
    video_dir = settings.ORIGINAL_VIDEO_PATH
    if not os.path.isdir(video_dir):
        return APIResponse(data={"files": [], "total": 0})

    files: list[FileItem] = []
    for entry in sorted(os.scandir(video_dir), key=lambda e: e.stat().st_mtime, reverse=True):
        if entry.is_file():
            stat = entry.stat()
            files.append(
                FileItem(
                    filename=entry.name,
                    file_path=entry.path,
                    url=f"/static_uploads/{entry.name}",
                    size=stat.st_size,
                    created_at="",
                )
            )

    return APIResponse(data={"files": files, "total": len(files)})
