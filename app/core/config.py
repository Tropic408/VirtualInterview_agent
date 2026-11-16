from ctypes import cdll

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "dev"
    redis_url: str
    qdrant_url: str = "http://localhost:6333"
    mysql_dsn: str
    # 阿里云百炼（DashScope OpenAI 兼容模式），不再使用本地 Ollama
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen-plus"
    embedding_model: str = "text-embedding-v4"
    rerank_model: str = "gte-rerank-v2"
    dashscope_api_key: str
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
