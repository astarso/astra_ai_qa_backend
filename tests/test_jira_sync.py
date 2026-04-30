import pytest
from litestar.testing import AsyncTestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Defect
from app.repositories.base import BaseRepository


@pytest.mark.asyncio
async def test_jira_webhook_updates_defect_status(test_client: AsyncTestClient, async_session: AsyncSession):
    repo = BaseRepository(async_session, Defect)
    defect = Defect(
        title="Test defect",
        description="Test description",
        severity=3,
        jira_key="ASTR-1234",
    )
    saved = await repo.save(defect)
    assert saved.status == "open"

    payload = {
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

    response = await test_client.post("/api/v1/webhooks/jira", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "synced"
    assert data["issue_key"] == "ASTR-1234"
    assert data["defect_status"] == "closed"
    assert data["updated_count"] == 1

    await async_session.refresh(saved)
    assert saved.status == "closed"


@pytest.mark.asyncio
async def test_jira_webhook_ignores_non_status_change(test_client: AsyncTestClient):
    payload = {
        "webhookEvent": "jira:issue_updated",
        "issue": {
            "key": "ASTR-1234",
            "fields": {
                "status": {"name": "In Progress"}
            }
        },
        "changelog": {
            "items": [
                {"field": "summary", "toString": "Updated summary"}
            ]
        }
    }

    response = await test_client.post("/api/v1/webhooks/jira", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "ignored"
    assert "Not a status change" in data["message"]


@pytest.mark.asyncio
async def test_jira_webhook_ignores_missing_issue_key(test_client: AsyncTestClient):
    payload = {
        "webhookEvent": "jira:issue_updated",
        "issue": {
            "fields": {
                "status": {"name": "Done"}
            }
        }
    }

    response = await test_client.post("/api/v1/webhooks/jira", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "ignored"
    assert "No issue key" in data["message"]


@pytest.mark.asyncio
async def test_jira_webhook_maps_in_progress_status(test_client: AsyncTestClient, async_session: AsyncSession):
    repo = BaseRepository(async_session, Defect)
    defect = Defect(
        title="Test defect",
        description="Test description",
        severity=3,
        jira_key="ASTR-5678",
        status="open",
    )
    saved = await repo.save(defect)

    payload = {
        "webhookEvent": "jira:issue_updated",
        "issue": {
            "key": "ASTR-5678",
            "fields": {
                "status": {"name": "In Progress"}
            }
        },
        "changelog": {
            "items": [
                {"field": "status", "toString": "In Progress"}
            ]
        }
    }

    response = await test_client.post("/api/v1/webhooks/jira", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "synced"
    assert data["defect_status"] == "in_progress"


@pytest.mark.asyncio
async def test_jira_sync_service_no_defects_found(test_client: AsyncTestClient):
    payload = {
        "webhookEvent": "jira:issue_updated",
        "issue": {
            "key": "ASTR-NONEXISTENT",
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

    response = await test_client.post("/api/v1/webhooks/jira", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "synced"
    assert data["updated_count"] == 0


@pytest.mark.asyncio
async def test_jira_sync_service_resolved_status(test_client: AsyncTestClient, async_session: AsyncSession):
    repo = BaseRepository(async_session, Defect)
    defect = Defect(
        title="Test defect",
        description="Test description",
        severity=3,
        jira_key="ASTR-RESOLVED",
        status="open",
    )
    saved = await repo.save(defect)

    payload = {
        "webhookEvent": "jira:issue_updated",
        "issue": {
            "key": "ASTR-RESOLVED",
            "fields": {
                "status": {"name": "Resolved"}
            }
        },
        "changelog": {
            "items": [
                {"field": "status", "toString": "Resolved"}
            ]
        }
    }

    response = await test_client.post("/api/v1/webhooks/jira", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "synced"
    assert data["defect_status"] == "resolved"
