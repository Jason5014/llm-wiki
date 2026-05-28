"""
配置管理模块 — 从 .env 文件和环境变量读取配置
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ===== LLM & Embedding =====
    dashscope_api_key: str = ""
    llm_model: str = "qwen-plus"
    llm_fast_model: str = "qwen-turbo"
    llm_max_model: str = "qwen-max"
    embedding_model: str = "text-embedding-v3"
    embedding_dim: int = 1024

    # ===== Milvus =====
    milvus_host: str = "localhost"
    milvus_port: int = 19530

    # ===== API =====
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # ===== 存储 =====
    kb_base_dir: Path = Path("./knowledge_bases")

    # ===== 爬虫 =====
    crawler_delay_seconds: float = 1.0
    crawler_max_concurrent: int = 5

    # ===== 处理参数 =====
    extraction_batch_size: int = 20   # 每批抽取的文档数
    llm_max_concurrent: int = 3       # LLM 最大并发数
    max_content_chars: int = 12000    # 单文档最大字符数（超出截断）
    embed_batch_size: int = 25        # 向量化批量大小（DashScope 限制）

    @property
    def dashscope_base_url(self) -> str:
        return "https://dashscope.aliyuncs.com/compatible-mode/v1"


# 全局单例
settings = Settings()
