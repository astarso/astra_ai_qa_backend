import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.services.jira_integration import JiraService, map_severity_to_jira


def test_map_severity_to_jira():
    assert map_severity_to_jira(1) == "Highest"
    assert map_severity_to_jira(3) == "Medium"
    assert map_severity_to_jira(5) == "Lowest"
    assert map_severity_to_jira(99) == "Medium"


@pytest.mark.asyncio
async def test_create_bug_not_configured():
    service = JiraService()
    service._base_url = None
    service._token = None
    result = await service.create_bug("PROJ", "Test Bug", "Description")
    assert result is None


@pytest.mark.asyncio
async def test_create_bug_success():
    service = JiraService()
    service._base_url = "https://jira.example.com"

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json = MagicMock(return_value={"key": "PROJ-123"})
    mock_response.raise_for_status = MagicMock()

    mock_token = MagicMock()
    mock_token.get_secret_value.return_value = "test-token"
    service._token = mock_token

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await service.create_bug("PROJ", "Bug title", "Bug desc")
        assert result == "PROJ-123"