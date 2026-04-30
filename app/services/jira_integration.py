"""Jira integration — auto-create Bug issues for defects."""

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class JiraService:
    """Lightweight Jira REST API v3 client using httpx."""

    def __init__(self) -> None:
        self._base_url = settings.jira_base_url
        self._token = settings.jira_token

    def _is_configured(self) -> bool:
        return bool(self._base_url and self._token)

    def _get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token.get_secret_value()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def create_bug(
        self,
        project_key: str,
        summary: str,
        description: str,
        priority_name: str = "Medium",
    ) -> str | None:
        """Create a Bug issue in Jira. Returns the issue key or None if not configured."""
        if not self._is_configured():
            logger.info("Jira not configured, skipping bug creation")
            return None

        url = f"{self._base_url.rstrip('/')}/rest/api/3/issue"
        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": description}],
                        }
                    ],
                },
                "issuetype": {"name": "Bug"},
                "priority": {"name": priority_name},
            }
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url, json=payload, headers=self._get_headers(), timeout=30
                )
                response.raise_for_status()
                data = response.json()
                issue_key = data.get("key", "")
                logger.info(f"Created Jira issue: {issue_key}")
                return issue_key
        except httpx.HTTPError as e:
            logger.warning(f"Failed to create Jira issue: {e}")
            return None


PRIORITY_MAP = {
    "CRITICAL": "Highest",
    "HIGH": "High",
    "MEDIUM": "Medium",
    "LOW": "Low",
    "MINIMAL": "Lowest",
}


def map_severity_to_jira(severity: int) -> str:
    """Map internal severity (1-5) to Jira priority name."""
    mapping = {1: "Highest", 2: "High", 3: "Medium", 4: "Low", 5: "Lowest"}
    return mapping.get(severity, "Medium")