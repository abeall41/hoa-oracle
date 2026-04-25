import io
import logging

from minio import Minio
from minio.error import S3Error

from app.config import settings

logger = logging.getLogger(__name__)

_client: Minio | None = None


def get_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=False,
        )
    return _client


def build_object_path(tier_type: str, tier_slug: str, filename: str) -> str:
    """Canonical MinIO path: {tier_type}/{tier_slug}/{filename}"""
    return f"{tier_type}/{tier_slug}/{filename}"


async def upload_document(
    tier_type: str,
    tier_slug: str,
    filename: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> str:
    """Upload a document to MinIO. Returns the object path."""
    import asyncio
    client = get_client()
    object_path = build_object_path(tier_type, tier_slug, filename)

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: client.put_object(
            settings.minio_bucket,
            object_path,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        ),
    )
    logger.info("Uploaded %s to MinIO (%d bytes)", object_path, len(data))
    return object_path


async def download_document(object_path: str) -> bytes:
    """Download a document from MinIO by object path."""
    import asyncio
    client = get_client()

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.get_object(settings.minio_bucket, object_path),
    )
    data = response.read()
    response.close()
    return data
