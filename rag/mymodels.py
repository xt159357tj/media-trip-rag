# mymodels.py   工具类，用于 生成 langchain 的 model（chat_model)

import os
import torch
from modelscope import snapshot_download
from langchain_huggingface import HuggingFaceEmbeddings

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com/"
from dotenv import load_dotenv
from config.settings import settings
from langchain_community.cross_encoders import HuggingFaceCrossEncoder

from core.logger import get_logger

logger = get_logger(__name__)

# 💡 新增：模型缓存字典，用于实现单例模式，避免重复加载吃光内存/显存
_MODEL_CACHE = {}

# 在模块加载时执行一次
load_dotenv()

def get_embeddings_model_path(model_family: str, model_id: str, cache_home_dir: str) -> str:
    # 建议定义一个确定的子目录，方便后续 HuggingFaceEmbeddings 调用
    cache_dir = os.path.join(cache_home_dir, model_family)

    # 拼接出模型实际应该存在的目录
    # ModelScope 默认下载路径格式为：cache_dir/model_id
    model_dir = os.path.join(cache_dir, model_id)

    # 显式检查关键文件是否存在（如 config.json）
    if not os.path.exists(os.path.join(model_dir, "config.json")):
        logger.info(f"[*] 未发现本地 embeddings {model_family.upper()} 模型，开始从魔塔社区下载: {model_id}。路径: {model_dir}。")
        # 执行下载，此处 snapshot_download 会处理网络层面的幂等性
        model_dir = snapshot_download(
            model_id=model_id,
            cache_dir=cache_dir,
            # allow_patterns=[
            #     "*.json",
            #     "*.bin",
            #     "*.txt",
            #     "*.py",
            #     "*.safetensors",
            #     "onnx/*"  # 如果需要onnx版本可以保留，不需要可删掉
            # ],
            ignore_patterns=[".DS_Store", "imgs/*", "media/*"],
            max_workers=8  # 适当多线程提高下载速度
        )
    else:
        logger.info(f"现 {model_family.upper()} 模型，: {model_id}。路径: {model_dir}。")

    return model_dir


def get_embeddings(model_family="bge-m3",
                   model_id='BAAI/bge-m3',
                   cache_home_dir=settings.EMBEDDING_HOME_PATH):
    """
    加载本地 BGE Embedding 模型
    💡 新增：加入全局单例缓存机制，避免重复加载消耗内存
    """
    # 1. 构造唯一的缓存键名
    cache_key = f"embeddings_{model_family}_{model_id}"

    # 2. 检查缓存中是否已有该模型，如果有直接返回
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]
    logger.info(f"--- 首次将 {model_family.upper()} Embeddings 模型加载到内存 ---")

    # 3. 下载或获取本地路径
    model_dir = get_embeddings_model_path(model_family, model_id, cache_home_dir)

    # 4. 设置计算设备
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # 防止 GPU OOM 导致 机器崩溃重启，指定CPU设备
    # device = "cpu"

    # 5. 初始化 LangChain 嵌入类
    embeddings = HuggingFaceEmbeddings(
        model_name=model_dir,
        model_kwargs={'device': device},
        encode_kwargs={'normalize_embeddings': True, 'batch_size': 8},
    )

    # 6. 将初始化好的模型放入缓存
    _MODEL_CACHE[cache_key] = embeddings

    return embeddings


def get_reranker_model_path(model_family: str, model_id: str, cache_home_dir: str) -> str:
    """
    通用模型路径获取函数，支持本地检查与断点续传
    """
    cache_dir = os.path.join(cache_home_dir, model_family)
    model_dir = os.path.join(cache_dir, model_id)

    # 显式检查关键文件是否存在
    if not os.path.exists(os.path.join(model_dir, "config.json")):
        logger.info(f"[*] 未发现本地 reranker {model_family.upper()} 模型，开始下载: {model_id}...")
        model_dir = snapshot_download(
            model_id=model_id,
            cache_dir=cache_dir,
            allow_patterns=["*.json", "*.bin", "*.txt", "*.py", "*.safetensors"],
            ignore_patterns=[".DS_Store", "imgs/*", "media/*"],
            max_workers=8
        )
    else:
        logger.info(f"[*] 发现本地 reranker {model_family.upper()} 模型，路径: {model_dir}")

    return model_dir


def get_reranker(model_family="bge-m3-reranker",
                 model_id="BAAI/bge-reranker-v2-m3",
                 cache_home_dir=settings.EMBEDDING_HOME_PATH):
    """
    初始化精排模型 (Reranker)
    不再封装进 CrossEncoderReranker，直接返回 HuggingFaceCrossEncoder 实例
    💡 新增：加入全局单例缓存机制
    """
    # 1. 构造唯一的缓存键名
    cache_key = f"reranker_{model_family}_{model_id}"

    # 2. 检查缓存
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]

    logger.info(f"--- 首次将 {model_family.upper()} Reranker 模型加载到内存 ---")

    # 3. 获取模型路径
    model_dir = get_reranker_model_path(model_family, model_id, cache_home_dir)

    # 4. 设置计算设备
    device = "cpu"  # 保持你的 CPU 偏好

    # 5. 初始化 Cross-Encoder
    model = HuggingFaceCrossEncoder(
        model_name=model_dir,
        model_kwargs={'device': device}
    )

    # 6. 将模型存入缓存
    _MODEL_CACHE[cache_key] = model

    return model