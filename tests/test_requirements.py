"""Test requirement_id field on TestCase model and API."""

import uuid

import pytest

from app.models.entities import Project, Requirement, Role, TestSuite, TestCase, User


@pytest.fixture
async def setup_test_data_with_suite(async_session):
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

    suite = TestSuite(
        project_id=project.id,
        name="Test Suite",
        kind="automated",
        config={},
    )
    async_session.add(suite)
    await async_session.flush()

    requirement = Requirement(
        id=uuid.uuid4(),
        title="Login Feature",
        source="jira",
        external_id="JIRA-123",
    )
    async_session.add(requirement)
    await async_session.flush()

    return {"role": role, "user": user, "project": project, "suite": suite, "requirement": requirement}


@pytest.mark.asyncio
async def test_create_test_case_with_requirement_id(test_client, setup_test_data_with_suite, async_session):
    suite_id = setup_test_data_with_suite["suite"].id
    requirement_id = setup_test_data_with_suite["requirement"].id

    payload = {
        "title": "Test login with valid credentials",
        "source": "jira",
        "suite_id": str(suite_id),
        "requirement_id": str(requirement_id),
    }
    response = await test_client.post("/api/v1/test-cases", json=payload)
    assert response.status_code == 201, response.json()
    data = response.json()
    assert data["title"] == "Test login with valid credentials"
    assert data["requirement_id"] == str(requirement_id)


@pytest.mark.asyncio
async def test_create_test_case_without_requirement_id(test_client, setup_test_data_with_suite, async_session):
    suite_id = setup_test_data_with_suite["suite"].id

    payload = {
        "title": "Test logout",
        "source": "manual",
        "suite_id": str(suite_id),
    }
    response = await test_client.post("/api/v1/test-cases", json=payload)
    assert response.status_code == 201, response.json()
    data = response.json()
    assert data["title"] == "Test logout"
    assert data["requirement_id"] is None


@pytest.mark.asyncio
async def test_list_test_cases_includes_requirement_id(test_client, setup_test_data_with_suite, async_session):
    suite_id = setup_test_data_with_suite["suite"].id
    requirement_id = setup_test_data_with_suite["requirement"].id

    case_with_req = TestCase(
        title="Case with requirement",
        source="jira",
        suite_id=suite_id,
        requirement_id=requirement_id,
    )
    case_without_req = TestCase(
        title="Case without requirement",
        source="manual",
        suite_id=suite_id,
    )
    async_session.add(case_with_req)
    async_session.add(case_without_req)
    await async_session.flush()

    response = await test_client.get(f"/api/v1/test-cases?suite_id={suite_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    by_title = {c["title"]: c for c in data}
    assert by_title["Case with requirement"]["requirement_id"] == str(requirement_id)
    assert by_title["Case without requirement"]["requirement_id"] is None


@pytest.mark.asyncio
async def test_get_test_case_includes_requirement_id(test_client, setup_test_data_with_suite, async_session):
    suite_id = setup_test_data_with_suite["suite"].id
    requirement_id = setup_test_data_with_suite["requirement"].id

    case = TestCase(
        title="Get test case",
        source="jira",
        suite_id=suite_id,
        requirement_id=requirement_id,
    )
    async_session.add(case)
    await async_session.flush()

    response = await test_client.get(f"/api/v1/test-cases/{case.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Get test case"
    assert data["requirement_id"] == str(requirement_id)