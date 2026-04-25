from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # LLM provider: 'ollama' for dev, 'claude' for prod
    llm_provider: str = "ollama"

    # Ollama (Gaasp, GPU-backed)
    ollama_base_url: str = "http://192.168.169.110:11434"
    ollama_model: str = "gemma3:4b"

    # Anthropic
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"

    # Database
    database_url: str = "postgresql+asyncpg://hoa:password@localhost:5432/hoa_intelligence"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "hoa-documents"

    # FastAPI
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Embedding model — both ingest and query time must match
    embedding_model: str = "nomic-embed-text"
    embedding_model_version: str = "1.5"

    # Token budgets
    max_tokens_governance: int = 1500
    max_tokens_customer_service: int = 800
    max_tokens_ocr_cleanup: int = 500

    # OCR
    ocr_confidence_threshold: float = 0.70


settings = Settings()
