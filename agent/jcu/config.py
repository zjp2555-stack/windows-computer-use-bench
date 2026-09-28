"""集中读取 agent/.env 的配置。密钥延迟校验（用到时才报错），方便先装依赖、后填密钥。"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"缺少环境变量 {name}：请复制 agent/.env.example 为 agent/.env 并填写"
        )
    return value


class Settings:
    decision_backend = os.getenv("DECISION_BACKEND", "siliconflow").strip().lower()
    confidence_threshold = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))
    exec_dry_run = os.getenv("EXEC_DRY_RUN", "true").strip().lower() != "false"
    max_candidates = int(os.getenv("MAX_CANDIDATES", "12"))
    max_steps = int(os.getenv("MAX_STEPS", "15"))

    zhipu_api_key = os.getenv("ZHIPU_API_KEY", "").strip()
    zhipu_model = os.getenv("ZHIPU_MODEL", "glm-4.6").strip()
    siliconflow_api_key = os.getenv("SILICONFLOW_API_KEY", "").strip()
    typesafe_api_key = os.getenv("TYPESAFE_API_KEY", "").strip()


settings = Settings()


def build_llm():
    """宿主 LLM：智谱 GLM。"""
    from .llm.zhipu import ZhipuChat

    key = settings.zhipu_api_key or _require("ZHIPU_API_KEY")
    return ZhipuChat(key, settings.zhipu_model)
