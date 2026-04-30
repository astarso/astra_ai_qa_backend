"""Jira status synchronization service."""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Defect

logger = logging.getLogger(__name__)


class JiraSyncService:
    """Service for syncing defect statuses with Jira issue updates."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle_jira_webhook(self, payload: dict) -> dict:
        """
        Handle incoming Jira webhook.

        Expected payload format:
        {
            "webhookEvent": "jira:issue_updated",
            "issue": {
                "key": "ASTR-1234",
                "fields": {
                    "status": {"name": "Done"}
                }
            },
            "changelog": {
                "items": [
                    {"field": "status", "toString": "Done"}
                ]
            }
        }
        """
        try:
            issue_key = payload.get("issue", {}).get("key")
            if not issue_key:
                return {"status": "ignored", "message": "No issue key in payload"}

            changelog = payload.get("changelog", {})
            status_change = any(
                item.get("field") == "status"
                for item in changelog.get("items", [])
            )

            if not status_change:
                return {"status": "ignored", "message": "Not a status change"}

            new_status = payload.get("issue", {}).get("fields", {}).get("status", {}).get("name")

            defect_status = self._map_jira_status(new_status)

            stmt = select(Defect).where(Defect.jira_key == issue_key)
            result = await self._session.execute(stmt)
            defects = result.scalars().all()

            updated = 0
            for defect in defects:
                if defect.status != defect_status:
                    defect.status = defect_status
                    updated += 1

            if updated > 0:
                await self._session.commit()
                logger.info(
                    "Synced %d defects with Jira issue %s to status %s",
                    updated,
                    issue_key,
                    defect_status,
                )

            return {
                "status": "synced",
                "issue_key": issue_key,
                "defect_status": defect_status,
                "updated_count": updated,
            }

        except Exception as e:
            logger.error("Failed to handle Jira webhook: %s", e)
            raise

    def _map_jira_status(self, jira_status: str) -> str:
        """Map Jira status to our defect status."""
        mapping = {
            "To Do": "open",
            "In Progress": "in_progress",
            "Done": "closed",
            "Closed": "closed",
            "Resolved": "resolved",
        }
        return mapping.get(jira_status, "open")