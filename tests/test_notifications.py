import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.services.notifications import (
    MattermostBackend,
    TelegramBackend,
    NotificationService,
)


@pytest.mark.asyncio
async def test_mattermost_success():
    backend = MattermostBackend("https://mattermost.example.com/hooks/abc123")

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await backend.send("Test run failed!")
        assert result is True


@pytest.mark.asyncio
async def test_mattermost_failure():
    import httpx

    backend = MattermostBackend("https://mattermost.example.com/hooks/abc123")

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.HTTPError("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await backend.send("Test message")
        assert result is False


@pytest.mark.asyncio
async def test_telegram_success():
    backend = TelegramBackend(token="123456:ABC", chat_id="-1001234567890")

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await backend.send("Pipeline failed!")
        assert result is True
        call_args = mock_client.post.call_args
        assert "bot123456:ABC" in call_args[0][0]


@pytest.mark.asyncio
async def test_notification_service_no_backend():
    service = NotificationService(backend=None)
    result = await service.notify("Test message")
    assert result is False


@pytest.mark.asyncio
async def test_notification_service_with_backend():
    mock_backend = AsyncMock()
    mock_backend.send.return_value = True

    service = NotificationService(backend=mock_backend)
    result = await service.notify("Alert!", subject="Test Alert")
    assert result is True
    mock_backend.send.assert_called_once_with("Alert!", subject="Test Alert")