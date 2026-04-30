"""MinIO storage service for test artifacts."""

import asyncio
import logging
from datetime import timedelta
from io import BytesIO

from minio import Minio

from app.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Async wrapper around sync MinIO client."""

    def __init__(self) -> None:
        self._client: Minio | None = None

    def _get_client(self) -> Minio:
        if self._client is None:
            self._client = Minio(
                endpoint=settings.minio_endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key.get_secret_value(),
                secure=settings.minio_secure,
            )
        return self._client

    async def upload(self, bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Upload file to MinIO. Returns the object key."""
        client = self._get_client()

        await asyncio.to_thread(self._ensure_bucket, client, bucket)

        data_stream = BytesIO(data)
        await asyncio.to_thread(
            client.put_object,
            bucket, key, data_stream, len(data),
            content_type=content_type,
        )
        logger.info(f"Uploaded {key} to {bucket}")
        return key

    async def download(self, bucket: str, key: str) -> bytes:
        """Download file from MinIO. Returns bytes."""
        client = self._get_client()
        response = await asyncio.to_thread(client.get_object, bucket, key)
        try:
            data = response.read()
        finally:
            response.close()
            response.release_conn()
        return data

    async def presigned_url(self, bucket: str, key: str, expires_hours: int = 2) -> str:
        """Generate a presigned download URL."""
        client = self._get_client()
        url = await asyncio.to_thread(
            client.presigned_get_object,
            bucket, key,
            expires=timedelta(hours=expires_hours),
        )
        return url

    def _ensure_bucket(self, client: Minio, bucket: str) -> None:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)