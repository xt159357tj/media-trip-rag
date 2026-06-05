# settings.py  统一的 配置管理
import os
from pathlib import Path
from typing import ClassVar

from dotenv import load_dotenv
# 注意这里新增了 SettingsConfigDict 的导入
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    # LLM 配置
    DASHSCOPE_API_KEY: str
    DASHSCOPE_BASE_URL: str
    DASHSCOPE_MODEL: str

    # deepseek 配置
    DEEPSEEK_API_KEY: str
    DEEPSEEK_BASE_URL: str
    DEEPSEEK_MODEL: str

    # TAVILY 配置
    TAVILY_API_KEY: str
    TAVILY_MAX_RESULTS: int = 3

    # LANGSMITH 配置
    LANGSMITH_API_KEY:str
    LANGCHAIN_TRACING_V2 :bool
    LANGCHAIN_ENDPOINT:str
    LANGCHAIN_PROJECT :str

    # 日志配置
    LOG_LEVEL: str = "INFO"  # 文件级日志的级别
    # 日志文件位置：
    LOG_FILE: str = os.path.join((os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs/app.log")

    # MCP 配置
    MCP_SERVER_URI: str = r"http://127.0.0.1:9090/mcp"
    MCP_SERVER_NAME: str = "content_generation_mcp"

    GAODE_URL: str
    T12306_URL: str

    # 获取当前脚本所在的文件夹绝对路径
    BASE_DIR: ClassVar[Path] = Path(__file__).resolve().parent.parent

    # 初始视频拷贝路径
    ORIGINAL_VIDEO_PATH: str = str(BASE_DIR / "data" / "original_videos")
    # 音频路径配置
    AUDIO_PATH: str = str(BASE_DIR / "data" / "audios")
    # WhisperModel 配置
    WHISPER_MODEL_PATH: str = str(BASE_DIR / "data" / "models" / "asr_models" / "large-v3")
    # 初始字幕路径配置
    ORIGINAL_SRT_PATH: str = str(BASE_DIR / "data"/ "original_srts")
    # 修改后字幕路径配置
    FINAL_SRT_PATH: str = str(BASE_DIR / "data" / "final_srts")
    # 最终合成视频路径
    FINAL_VIDEO_PATH: str = str(BASE_DIR / "data" / "final_videos")

    # 向量模型配置
    EMBEDDING_HOME_PATH: str = str(BASE_DIR / "data" / "models" / "embedding_models")

    # 新版 Pydantic v2 指定配置来源的方式
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


# 实例配置类对象，以备调用
settings = Settings()