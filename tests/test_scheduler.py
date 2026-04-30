import uuid

import pytest


@pytest.mark.asyncio
async def test_create_schedule(test_client):
    suite_id = uuid.uuid4()
    triggered_by = uuid.uuid4()
    payload = {
        "suite_id": str(suite_id),
        "name": "Daily CI Run",
        "cron_expression": "0 0 * * *",
        "timezone": "UTC",
        "triggered_by": str(triggered_by),
    }

    response = await test_client.post("/api/v1/schedules", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Daily CI Run"
    assert data["cron_expression"] == "0 0 * * *"
    assert data["timezone"] == "UTC"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_create_schedule_with_timezone(test_client):
    suite_id = uuid.uuid4()
    triggered_by = uuid.uuid4()
    payload = {
        "suite_id": str(suite_id),
        "name": "Nightly Build",
        "cron_expression": "0 2 * * *",
        "timezone": "Europe/Moscow",
        "triggered_by": str(triggered_by),
    }

    response = await test_client.post("/api/v1/schedules", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["timezone"] == "Europe/Moscow"


@pytest.mark.asyncio
async def test_create_schedule_invalid_cron(test_client):
    suite_id = uuid.uuid4()
    triggered_by = uuid.uuid4()
    payload = {
        "suite_id": str(suite_id),
        "name": "Bad Cron",
        "cron_expression": "invalid",
        "timezone": "UTC",
        "triggered_by": str(triggered_by),
    }

    response = await test_client.post("/api/v1/schedules", json=payload)
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_list_schedules(test_client):
    response = await test_client.get("/api/v1/schedules")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_list_schedules_with_suite_filter(test_client):
    suite_id = uuid.uuid4()
    response = await test_client.get(f"/api/v1/schedules?suite_id={suite_id}")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_schedule(test_client):
    schedule_id = uuid.uuid4()
    response = await test_client.get(f"/api/v1/schedules/{schedule_id}")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_schedule(test_client):
    schedule_id = uuid.uuid4()
    payload = {
        "name": "Updated Schedule Name",
        "is_active": False,
    }

    response = await test_client.put(f"/api/v1/schedules/{schedule_id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["updated"] is True


@pytest.mark.asyncio
async def test_delete_schedule(test_client):
    schedule_id = uuid.uuid4()
    response = await test_client.delete(f"/api/v1/schedules/{schedule_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] is True
    assert data["schedule_id"] == str(schedule_id)