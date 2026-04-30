import uuid

import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_search_with_query_returns_200(test_client):
    with patch("app.controllers.search.SearchService") as mock_service_class:
        mock_instance = AsyncMock()
        mock_instance.search.return_value = [
            {"result_id": "id1", "test_name": "Test A", "status": "failed"},
            {"result_id": "id2", "test_name": "Test B", "status": "passed"},
        ]
        mock_service_class.return_value = mock_instance

        response = await test_client.get("/api/v1/search?q=test")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        mock_instance.search.assert_called_once_with(query="test", status=None, run_id=None)


@pytest.mark.asyncio
async def test_search_without_query_returns_empty_list(test_client):
    response = await test_client.get("/api/v1/search")
    assert response.status_code == 200
    data = response.json()
    assert data == []


@pytest.mark.asyncio
async def test_search_with_status_filter(test_client):
    with patch("app.controllers.search.SearchService") as mock_service_class:
        mock_instance = AsyncMock()
        mock_instance.search.return_value = [
            {"result_id": "id1", "test_name": "Test A", "status": "failed"},
        ]
        mock_service_class.return_value = mock_instance

        response = await test_client.get("/api/v1/search?q=error&status=failed")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        mock_instance.search.assert_called_once_with(query="error", status="failed", run_id=None)


@pytest.mark.asyncio
async def test_upload_attachment_success(test_client):
    run_id = uuid.uuid4()
    payload = {
        "filename": "test.txt",
        "content_type": "text/plain",
        "data": "SGVsbG8gV29ybGQ=",
    }

    with patch("app.services.storage.StorageService") as mock_service_class:
        mock_instance = AsyncMock()
        mock_instance.upload.return_value = f"runs/{run_id}/test.txt"
        mock_service_class.return_value = mock_instance

        response = await test_client.post(f"/api/v1/runs/{run_id}/attachments", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "ok"
        assert data["key"] == f"runs/{run_id}/test.txt"
        assert data["size"] == 11


@pytest.mark.asyncio
async def test_upload_attachment_invalid_base64(test_client):
    run_id = uuid.uuid4()
    payload = {
        "filename": "test.txt",
        "content_type": "text/plain",
        "data": "not-valid-base64!!!",
    }

    response = await test_client.post(f"/api/v1/runs/{run_id}/attachments", json=payload)
    assert response.status_code == 500