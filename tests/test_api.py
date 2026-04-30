"""Test API endpoints using Litestar AsyncTestClient."""

import uuid

import pytest
from sqlalchemy import select

from app.models.entities import Project, Role, TestSuite, TestCase, User


@pytest.fixture
async def setup_test_data(async_session):
    role = Role(code="admin", description="Admin role")
    async_session.add(role)
    await async_session.flush()

    user = User(
        email="test@example.com",
        full_name="Test User",
        role_id=role.id,
        is_active=True,
    )
    async_session.add(user)
    await async_session.flush()

    project = Project(
        code="DEMO",
        name="Demo Project",
        owner_id=user.id,
    )
    async_session.add(project)
    await async_session.flush()

    return {"role": role, "user": user, "project": project}


@pytest.mark.asyncio
async def test_health_endpoint(test_client):
    response = await test_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_list_projects_empty(test_client):
    response = await test_client.get("/api/v1/projects")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_create_project(test_client, setup_test_data):
    payload = {
        "code": "NEWPROJ",
        "name": "New Project",
        "owner_id": str(setup_test_data["user"].id),
    }
    response = await test_client.post("/api/v1/projects", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["code"] == "NEWPROJ"
    assert data["name"] == "New Project"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_projects_after_creation(test_client, setup_test_data):
    payload = {
        "code": "ANOTHER",
        "name": "Another Project",
        "owner_id": str(setup_test_data["user"].id),
    }
    await test_client.post("/api/v1/projects", json=payload)
    response = await test_client.get("/api/v1/projects")
    assert response.status_code == 200
    projects = response.json()
    assert len(projects) >= 1


@pytest.mark.asyncio
async def test_get_project_by_id(test_client, setup_test_data):
    project_id = setup_test_data["project"].id
    response = await test_client.get(f"/api/v1/projects/{project_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "DEMO"
    assert data["name"] == "Demo Project"


@pytest.mark.asyncio
async def test_get_nonexistent_project_returns_error(test_client):
    fake_id = uuid.uuid4()
    response = await test_client.get(f"/api/v1/projects/{fake_id}")
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_create_run_without_suite_fails(test_client, setup_test_data):
    payload = {
        "suite_id": str(uuid.uuid4()),
        "commit_sha": "a" * 40,
        "branch": "main",
        "triggered_by": str(setup_test_data["user"].id),
        "priority": 3,
        "environment": "dev",
    }
    response = await test_client.post("/api/v1/runs", json=payload)
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_get_run_without_existing_run(test_client):
    fake_id = uuid.uuid4()
    response = await test_client.get(f"/api/v1/runs/{fake_id}")
    assert response.status_code == 500