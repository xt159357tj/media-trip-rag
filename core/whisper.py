import os
from faster_whisper import WhisperModel
from datetime import timedelta

from config.settings import settings

def format_srt_timestamp(seconds: float) -> str:
    """
    将秒数转换为 SRT 标准时间戳格式: HH:MM:SS,mmm
    """
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int(td.microseconds / 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

WHISPER_CONFIG = {
    "model_size": "large-v3",
    "device": "cpu",
    "compute_type": "int8",              # 使用 int8 量化，显著提升 CPU 效率
    "download_root": settings.WHISPER_MODEL_PATH    # 模型存储路径
}

class WhisperManager:
    _instance = None

    @classmethod
    def get_model(cls):
        """获取或初始化 Whisper 模型单例"""
        if cls._instance is None:
            # 1. 确保模型存放目录存在
            if not os.path.exists(WHISPER_CONFIG["download_root"]):
                os.makedirs(WHISPER_CONFIG["download_root"])

            # 2. 初始化模型
            # 即使不手动指定线程数，int8 量化也能在 CPU 上获得很好的性能
            cls._instance = WhisperModel(
                model_size_or_path=WHISPER_CONFIG["model_size"],
                device=WHISPER_CONFIG["device"],
                compute_type=WHISPER_CONFIG["compute_type"],
                download_root=WHISPER_CONFIG["download_root"]
            )

        return cls._instance


# 获取全局唯一的模型实例
def get_whisper():
    return WhisperManager.get_model()