import logging

from app.config import settings

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    """Lazy-load the embedding model and assert version matches settings."""
    global _model
    if _model is not None:
        return _model

    import sentence_transformers

    running_version = sentence_transformers.__version__
    if running_version != settings.embedding_model_version:
        logger.warning(
            "Embedding model version mismatch: running %s, expected %s. "
            "Halting ingestion — re-embedding required.",
            running_version,
            settings.embedding_model_version,
        )
        raise RuntimeError(
            f"Embedding model version mismatch: {running_version} != "
            f"{settings.embedding_model_version}"
        )

    from sentence_transformers import SentenceTransformer
    # trust_remote_code=True is required by nomic-ai/nomic-embed-text-v1.5
    _model = SentenceTransformer(settings.embedding_model, trust_remote_code=True)
    return _model


async def embed(text: str) -> list[float]:
    """Generate a single embedding vector for the given text."""
    model = _get_model()
    # SentenceTransformer.encode is synchronous — run in thread pool for async contexts
    import asyncio
    loop = asyncio.get_event_loop()
    vector = await loop.run_in_executor(None, lambda: model.encode(text).tolist())
    return vector


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts."""
    model = _get_model()
    import asyncio
    loop = asyncio.get_event_loop()
    vectors = await loop.run_in_executor(None, lambda: model.encode(texts).tolist())
    return vectors
