import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.search import SearchService


@pytest.mark.asyncio
async def test_index_result_no_opensearch():
    """When opensearch_url is None, index_result returns False gracefully."""
    service = SearchService()
    result = await service.index_result(
        result_id="test-id",
        run_id="run-id",
        test_name="My Test",
        status="failed",
    )
    assert result is False


@pytest.mark.asyncio
async def test_search_no_opensearch():
    """When opensearch_url is None, search returns empty list."""
    service = SearchService()
    results = await service.search("error message")
    assert results == []


@pytest.mark.asyncio
async def test_index_result_success():
    service = SearchService()
    mock_client = AsyncMock()
    mock_client.index.return_value = {"result": "created"}

    with patch.object(service, "_get_client", return_value=mock_client):
        result = await service.index_result(
            result_id="id1",
            run_id="run1",
            test_name="Test",
            status="failed",
            error_message="assert failed",
        )
        assert result is True
        mock_client.index.assert_called_once()


@pytest.mark.asyncio
async def test_search_with_results():
    service = SearchService()
    mock_client = AsyncMock()
    mock_client.search.return_value = {
        "hits": {
            "hits": [
                {"_source": {"result_id": "id1", "test_name": "Test A", "status": "failed"}},
                {"_source": {"result_id": "id2", "test_name": "Test B", "status": "passed"}},
            ]
        }
    }

    with patch.object(service, "_get_client", return_value=mock_client):
        results = await service.search("assert", status="failed")
        assert len(results) == 2
        assert results[0]["test_name"] == "Test A"