import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.storage import StorageService


@pytest.mark.asyncio
async def test_upload_calls_minio():
    service = StorageService()

    mock_client = MagicMock()
    mock_client.bucket_exists.return_value = False
    mock_client.make_bucket = MagicMock()
    mock_client.put_object = MagicMock()

    with patch.object(service, '_get_client', return_value=mock_client):
        key = await service.upload("test-bucket", "run1/result.txt", b"hello world")
        assert key == "run1/result.txt"
        mock_client.make_bucket.assert_called_once_with("test-bucket")


@pytest.mark.asyncio
async def test_download_calls_minio():
    service = StorageService()

    mock_response = MagicMock()
    mock_response.read.return_value = b"file content"
    mock_response.close = MagicMock()
    mock_response.release_conn = MagicMock()

    mock_client = MagicMock()
    mock_client.get_object.return_value = mock_response

    with patch.object(service, '_get_client', return_value=mock_client):
        data = await service.download("test-bucket", "run1/result.txt")
        assert data == b"file content"


@pytest.mark.asyncio
async def test_presigned_url():
    service = StorageService()

    mock_client = MagicMock()
    mock_client.presigned_get_object.return_value = "https://minio.example.com/test-bucket/run1/file?token=abc"

    with patch.object(service, '_get_client', return_value=mock_client):
        url = await service.presigned_url("test-bucket", "run1/file.txt")
        assert "minio" in url