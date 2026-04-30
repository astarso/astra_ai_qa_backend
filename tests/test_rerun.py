import pytest
from litestar.testing import AsyncTestClient
from app.models.entities import Project, Role, TestRun, TestCase, TestSuite, TestResult, User


async def _seed_run_with_failures(async_session) -> str:
    role = Role(code="rerun_role", description="Rerun test")
    async_session.add(role)
    await async_session.flush()

    user = User(email="rerun@example.com", full_name="Rerun", role_id=role.id)
    async_session.add(user)
    await async_session.flush()

    project = Project(code="RERUN", name="Rerun Project", owner_id=user.id)
    async_session.add(project)
    await async_session.flush()

    suite = TestSuite(project_id=project.id, name="Rerun Suite", kind="unit", config={})
    async_session.add(suite)
    await async_session.flush()

    case1 = TestCase(suite_id=suite.id, title="Pass Test", source="auto")
    case2 = TestCase(suite_id=suite.id, title="Fail Test", source="auto")
    async_session.add_all([case1, case2])
    await async_session.flush()

    from datetime import datetime
    run = TestRun(
        suite_id=suite.id, commit_sha="b" * 40, branch="main",
        triggered_by=user.id, priority=3, environment="dev",
        status="failed", started_at=datetime.utcnow(), finished_at=datetime.utcnow(),
    )
    async_session.add(run)
    await async_session.flush()

    r1 = TestResult(run_id=run.id, test_case_id=case1.id, status="passed", duration_ms=100)
    r2 = TestResult(run_id=run.id, test_case_id=case2.id, status="failed", duration_ms=200,
                    error_message="assert failed")
    async_session.add_all([r1, r2])
    await async_session.flush()
    return str(run.id)


@pytest.mark.asyncio
async def test_rerun_failed(test_client: AsyncTestClient, async_session):
    run_id = await _seed_run_with_failures(async_session)
    response = await test_client.post(f"/api/v1/runs/{run_id}/rerun")
    assert response.status_code == 201
    data = response.json()
    assert "new_run_id" in data
    assert data["rerun_count"] == 1
    assert data["status"] in ("pending", "running")


@pytest.mark.asyncio
async def test_rerun_no_failures(test_client: AsyncTestClient, async_session):
    role = Role(code="rerun_empty", description="Rerun empty")
    async_session.add(role)
    await async_session.flush()
    user = User(email="rerun_empty@example.com", full_name="Rerun Empty", role_id=role.id)
    async_session.add(user)
    await async_session.flush()
    project = Project(code="REMPTY", name="Empty", owner_id=user.id)
    async_session.add(project)
    await async_session.flush()
    suite = TestSuite(project_id=project.id, name="Empty Suite", kind="unit", config={})
    async_session.add(suite)
    await async_session.flush()
    from datetime import datetime
    run = TestRun(
        suite_id=suite.id, commit_sha="c" * 40, branch="main",
        triggered_by=user.id, priority=3, environment="dev",
        status="passed", started_at=datetime.utcnow(), finished_at=datetime.utcnow(),
    )
    async_session.add(run)
    await async_session.flush()

    response = await test_client.post(f"/api/v1/runs/{run.id}/rerun")
    assert response.status_code == 500