import logging
from pathlib import Path
from typing import Optional

import colorlog

# 导入 配置文件
from config.settings import settings

class LoggerManager:

    # 二者结合，实现单例模式
    _instance: Optional['LoggerManager'] = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._setup_log_directory()
    def _setup_log_directory(self):
        log_file = Path(settings.LOG_FILE)
        log_file.parent.mkdir(parents=True, exist_ok=True)

    _loggers: dict = {}
    def get_logger(self, name: str) -> logging.Logger:
        if name in self._loggers:
            return self._loggers[name]
        # 创建日志记录器
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)

        if logger.handlers:
            return logger
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        # 创建控制台格式化器
        console_formatter = colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
        console_handler.setFormatter(console_formatter)

        # 创建文件处理器
        file_handler = logging.FileHandler(
            settings.LOG_FILE,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)

        # 创建文件格式化器
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )
        file_handler.setFormatter(file_formatter)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

        self._loggers[name] = logger
        return logger

# 全局日志管理器实例
logger_manager = LoggerManager()

# 获取 日志对象
def get_logger(name: str) -> logging.Logger:
    return logger_manager.get_logger(name)
