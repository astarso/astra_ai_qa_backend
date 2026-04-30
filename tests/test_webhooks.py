import pytest
from litestar.testing import AsyncTestClient


@pytest.mark.asyncio
async def test_gitlab_pipeline_success(test_client: AsyncTestClient):
    payload = {
        "object_kind": "pipeline",
        "object_attributes": {
            "status": "success",
            "ref": "main",
            "sha": "abc123def456" + "0" * 34,
        },
    }
    response = await test_client.post("/api/v1/webhooks/gitlab", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "triggered"
    assert data["ref"] == "main"


@pytest.mark.asyncio
async def test_gitlab_pipeline_non_success(test_client: AsyncTestClient):
    payload = {
        "object_kind": "pipeline",
        "object_attributes": {
            "status": "running",
            "ref": "main",
            "sha": "abc123" + "0" * 40,
        },
    }
    response = await test_client.post("/api/v1/webhooks/gitlab", json=payload)
    assert response.status_code == 201
    assert response.json()["status"] == "accepted"


@pytest.mark.asyncio
async def test_gitlab_ignored_event(test_client: AsyncTestClient):
    payload = {"object_kind": "push", "ref": "main"}
    response = await test_client.post("/api/v1/webhooks/gitlab", json=payload)
    assert response.status_code == 201
    assert response.json()["status"] == "ignored"