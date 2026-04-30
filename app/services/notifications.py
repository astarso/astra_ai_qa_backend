"""Notification service with multiple backends (Mattermost, Email, Telegram)."""

import logging
from abc import ABC, abstractmethod
from email.message import EmailMessage

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class NotificationBackend(ABC):
    """Abstract base for notification backends."""

    @abstractmethod
    async def send(self, message: str, **kwargs) -> bool:
        """Send a notification. Returns True if successful."""
        ...


class MattermostBackend(NotificationBackend):
    """Send notifications via Mattermost webhook."""

    def __init__(self, webhook_url: str) -> None:
        self._webhook_url = webhook_url

    async def send(self, message: str, **kwargs) -> bool:
        payload = {"text": message}
        if kwargs.get("attachments"):
            payload["attachments"] = kwargs["attachments"]

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self._webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=10,
                )
                response.raise_for_status()
                logger.info("Mattermost notification sent")
                return True
        except httpx.HTTPError as e:
            logger.warning(f"Mattermost notification failed: {e}")
            return False


class EmailBackend(NotificationBackend):
    """Send notifications via email (using aiosmtplib if available)."""

    def __init__(self, to: str, smtp_host: str = "localhost", smtp_port: int = 587) -> None:
        self._to = to
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port

    async def send(self, message: str, **kwargs) -> bool:
        subject = kwargs.get("subject", "Astra QA Notification")
        try:
            import aiosmtplib

            msg = EmailMessage()
            msg["From"] = "noreply@astra-qa.local"
            msg["To"] = self._to
            msg["Subject"] = subject
            msg.set_content(message)

            await aiosmtplib.send(
                msg,
                hostname=self._smtp_host,
                port=self._smtp_port,
                start_tls=True,
            )
            logger.info(f"Email notification sent to {self._to}")
            return True
        except ImportError:
            logger.warning("aiosmtplib not installed, skipping email notification")
            return False
        except Exception as e:
            logger.warning(f"Email notification failed: {e}")
            return False


class TelegramBackend(NotificationBackend):
    """Send notifications via Telegram Bot API."""

    def __init__(self, token: str, chat_id: str) -> None:
        self._token = token
        self._chat_id = chat_id

    async def send(self, message: str, **kwargs) -> bool:
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": message,
            "parse_mode": kwargs.get("parse_mode", "Markdown"),
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=10)
                response.raise_for_status()
                logger.info("Telegram notification sent")
                return True
        except httpx.HTTPError as e:
            logger.warning(f"Telegram notification failed: {e}")
            return False


class NotificationService:
    """Dispatcher that sends via configured backend."""

    def __init__(self, backend: NotificationBackend | None = None) -> None:
        self._backend = backend

    async def notify(self, message: str, **kwargs) -> bool:
        """Send notification if a backend is configured."""
        if self._backend is None:
            logger.info("No notification backend configured, skipping")
            return False
        return await self._backend.send(message, **kwargs)