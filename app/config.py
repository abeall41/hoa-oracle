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
    max_tokens_customer_service: int = 800   # homeowner responses — concise, warm
    max_tokens_board_response: int = 2000    # board responses — full citations, detailed
    max_tokens_ocr_cleanup: int = 500

    # OCR
    ocr_confidence_threshold: float = 0.70

    # Query decomposition — max sub-queries to run in parallel.
    # Each search spawns a subprocess that loads the embedding model (~500MB RAM).
    # On a 4GB VM, 2 is safe; raise to 3 only if memory headroom is confirmed.
    max_concurrent_searches: int = 2

    # Accuracy pipeline — Gate 1: retrieval confidence threshold.
    # Cosine distance; lower = more similar. Results whose best chunk score exceeds
    # this value indicate the index has no reliable match for the query. Synthesis
    # is skipped and a canned "could not find" response is returned.
    # Tune by monitoring query_log: scores 0.35-0.44 = good, 0.45+ = unreliable.
    retrieval_gate_threshold: float = 0.46


settings = Settings()
