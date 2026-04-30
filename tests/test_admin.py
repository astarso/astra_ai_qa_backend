import pytest
from litestar.testing import AsyncTestClient


@pytest.mark.asyncio
async def test_list_users_empty(test_client: AsyncTestClient):
    response = await test_client.get("/api/v1/admin/users")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_user(test_client: AsyncTestClient):
    payload = {
        "email": "test@example.com",
        "full_name": "Test User",
        "role_id": 1,
        "is_active": True,
    }
    response = await test_client.post("/api/v1/admin/users", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["full_name"] == "Test User"
    assert data["role_id"] == 1
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_list_users_after_create(test_client: AsyncTestClient):
    payload = {
        "email": "test2@example.com",
        "full_name": "Test User 2",
        "role_id": 1,
        "is_active": True,
    }
    create_response = await test_client.post("/api/v1/admin/users", json=payload)
    assert create_response.status_code == 201
    created_id = create_response.json()["id"]

    list_response = await test_client.get("/api/v1/admin/users")
    assert list_response.status_code == 200
    users = list_response.json()
    assert len(users) == 1
    assert users[0]["id"] == created_id
    assert users[0]["email"] == "test2@example.com"


@pytest.mark.asyncio
async def test_update_user_role(test_client: AsyncTestClient):
    payload = {
        "email": "test3@example.com",
        "full_name": "Test User 3",
        "role_id": 1,
        "is_active": True,
    }
    create_response = await test_client.post("/api/v1/admin/users", json=payload)
    assert create_response.status_code == 201
    user_id = create_response.json()["id"]

    update_payload = {"role_id": 2}
    update_response = await test_client.put(f"/api/v1/admin/users/{user_id}", json=update_payload)
    assert update_response.status_code == 200
    data = update_response.json()
    assert data["role_id"] == 2
    assert data["full_name"] == "Test User 3"


@pytest.mark.asyncio
async def test_get_settings(test_client: AsyncTestClient):
    response = await test_client.get("/api/v1/admin/settings")
    assert response.status_code == 200
    data = response.json()
    assert "llm_model_name" in data
    assert "llm_temperature" in data
    assert "llm_max_tokens" in data
    assert "llm_request_timeout_seconds" in data


@pytest.mark.asyncio
async def test_update_settings(test_client: AsyncTestClient):
    payload = {"llm_temperature": 0.5}
    response = await test_client.put("/api/v1/admin/settings", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["llm_temperature"] == 0.5