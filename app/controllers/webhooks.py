"""Webhook controller for external CI/CD integrations."""

import logging

from litestar import Controller, post
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logger = logging.getLogger(__name__)


class WebhooksController(Controller):
    path = "/api/v1/webhooks"
    tags = ["Webhooks"]
    exclude_from_auth = True

    @post("/gitlab")
    async def gitlab_webhook(self, data: dict) -> dict:
        event_type = data.get("object_kind", "")

        if event_type == "pipeline":
            return await self._handle_pipeline(data)

        return {"status": "ignored", "event": event_type}

    @post("/jira")
    async def jira_webhook(self, data: dict, db_session: AsyncSession) -> dict:
        from app.services.jira_sync import JiraSyncService

        service = JiraSyncService(db_session)
        return await service.handle_jira_webhook(data)

    async def _handle_pipeline(self, data: dict) -> dict:
        attrs = data.get("object_attributes", {})
        status = attrs.get("status", "")
        ref = attrs.get("ref", "")
        sha = attrs.get("sha", "")

        if status == "success":
            logger.info(f"GitLab pipeline success on {ref} ({sha[:8]})")
            return {"status": "triggered", "ref": ref, "sha": sha}

        return {"status": "accepted", "pipeline_status": status}