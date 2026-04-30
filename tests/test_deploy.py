import uuid

import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_trigger_deploy_with_approval(test_client):
    run_id = uuid.uuid4()
    payload = {"environment": "preprod", "approve": True}

    response = await test_client.post(f"/api/v1/runs/{run_id}/deploy", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "deployment_id" in data
    assert data["run_id"] == str(run_id)
    assert data["environment"] == "preprod"
    assert data["status"] == "triggered"


@pytest.mark.asyncio
async def test_trigger_deploy_prod_environment(test_client):
    run_id = uuid.uuid4()
    payload = {"environment": "prod", "approve": True}

    response = await test_client.post(f"/api/v1/runs/{run_id}/deploy", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["environment"] == "prod"


@pytest.mark.asyncio
async def test_trigger_deploy_without_approval_fails(test_client):
    run_id = uuid.uuid4()
    payload = {"environment": "preprod", "approve": False}

    response = await test_client.post(f"/api/v1/runs/{run_id}/deploy", json=payload)
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_trigger_deploy_invalid_environment(test_client):
    run_id = uuid.uuid4()
    payload = {"environment": "staging", "approve": True}

    response = await test_client.post(f"/api/v1/runs/{run_id}/deploy", json=payload)
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_trigger_deploy_default_environment(test_client):
    run_id = uuid.uuid4()
    payload = {"approve": True}

    response = await test_client.post(f"/api/v1/runs/{run_id}/deploy", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["environment"] == "preprod"
