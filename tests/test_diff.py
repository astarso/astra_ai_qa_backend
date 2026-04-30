import pytest
from litestar.testing import AsyncTestClient
from app.models.entities import Project, Role, TestRun, TestCase, TestSuite, TestResult, User


async def _seed_two_runs_with_diff(async_session):
    role = Role(code="diff_role", description="Diff test")
    async_session.add(role)
    await async_session.flush()

    user = User(email="diff@example.com", full_name="Diff User", role_id=role.id)
    async_session.add(user)
    await async_session.flush()

    project = Project(code="DIFF", name="Diff Project", owner_id=user.id)
    async_session.add(project)
    await async_session.flush()

    suite = TestSuite(project_id=project.id, name="Diff Suite", kind="unit", config={})
    async_session.add(suite)
    await async_session.flush()

    case1 = TestCase(suite_id=suite.id, title="Test One", source="auto")
    case2 = TestCase(suite_id=suite.id, title="Test Two", source="auto")
    case3 = TestCase(suite_id=suite.id, title="Test Three", source="auto")
    case4 = TestCase(suite_id=suite.id, title="Test Four", source="auto")
    async_session.add_all([case1, case2, case3, case4])
    await async_session.flush()

    from datetime import datetime
    run1 = TestRun(
        suite_id=suite.id, commit_sha="a" * 40, branch="main",
        triggered_by=user.id, priority=3, environment="dev",
        status="failed", started_at=datetime.utcnow(), finished_at=datetime.utcnow(),
    )
    run2 = TestRun(
        suite_id=suite.id, commit_sha="b" * 40, branch="feature",
        triggered_by=user.id, priority=3, environment="dev",
        status="failed", started_at=datetime.utcnow(), finished_at=datetime.utcnow(),
    )
    async_session.add_all([run1, run2])
    await async_session.flush()

    r1 = TestResult(run_id=run1.id, test_case_id=case1.id, status="passed", duration_ms=100)
    r2 = TestResult(run_id=run1.id, test_case_id=case2.id, status="failed", duration_ms=200)
    r3 = TestResult(run_id=run1.id, test_case_id=case3.id, status="skipped", duration_ms=50)
    async_session.add_all([r1, r2, r3])
    await async_session.flush()

    r4 = TestResult(run_id=run2.id, test_case_id=case1.id, status="failed", duration_ms=120)
    r5 = TestResult(run_id=run2.id, test_case_id=case2.id, status="passed", duration_ms=180)
    r6 = TestResult(run_id=run2.id, test_case_id=case4.id, status="passed", duration_ms=90)
    async_session.add_all([r4, r5, r6])
    await async_session.flush()

    return str(run1.id), str(run2.id)


@pytest.mark.asyncio
async def test_run_diff_success(test_client: AsyncTestClient, async_session):
    run1_id, run2_id = await _seed_two_runs_with_diff(async_session)
    response = await test_client.get(f"/api/v1/runs/{run1_id}/diff?compare_to={run2_id}")
    assert response.status_code == 200
    data = response.json()

    assert data["base_run_id"] == run1_id
    assert data["compare_run_id"] == run2_id
    assert data["summary"]["total_base"] == 3
    assert data["summary"]["total_compare"] == 3

    added_titles = [item["title"] for item in data["added"]]
    assert "Test Four" in added_titles

    removed_titles = [item["title"] for item in data["removed"]]
    assert "Test Three" in removed_titles

    changed_titles = [item["title"] for item in data["changed"]]
    assert "Test One" in changed_titles
    assert "Test Two" in changed_titles

    assert data["summary"]["added"] == 1
    assert data["summary"]["removed"] == 1
    assert data["summary"]["changed"] == 2
    assert data["unchanged_count"] == 0


@pytest.mark.asyncio
async def test_run_diff_unchanged(test_client: AsyncTestClient, async_session):
    role = Role(code="same_role", description="Same test")
    async_session.add(role)
    await async_session.flush()

    user = User(email="same@example.com", full_name="Same User", role_id=role.id)
    async_session.add(user)
    await async_session.flush()

    project = Project(code="SAME", name="Same Project", owner_id=user.id)
    async_session.add(project)
    await async_session.flush()

    suite = TestSuite(project_id=project.id, name="Same Suite", kind="unit", config={})
    async_session.add(suite)
    await async_session.flush()

    case1 = TestCase(suite_id=suite.id, title="Same Test", source="auto")
    async_session.add(case1)
    await async_session.flush()

    from datetime import datetime
    run1 = TestRun(
        suite_id=suite.id, commit_sha="c" * 40, branch="main",
        triggered_by=user.id, priority=3, environment="dev",
        status="passed", started_at=datetime.utcnow(), finished_at=datetime.utcnow(),
    )
    run2 = TestRun(
        suite_id=suite.id, commit_sha="d" * 40, branch="feature",
        triggered_by=user.id, priority=3, environment="dev",
        status="passed", started_at=datetime.utcnow(), finished_at=datetime.utcnow(),
    )
    async_session.add_all([run1, run2])
    await async_session.flush()

    r1 = TestResult(run_id=run1.id, test_case_id=case1.id, status="passed", duration_ms=100)
    r2 = TestResult(run_id=run2.id, test_case_id=case1.id, status="passed", duration_ms=100)
    async_session.add_all([r1, r2])
    await async_session.flush()

    response = await test_client.get(f"/api/v1/runs/{run1.id}/diff?compare_to={run2.id}")
    assert response.status_code == 200
    data = response.json()

    assert data["summary"]["added"] == 0
    assert data["summary"]["removed"] == 0
    assert data["summary"]["changed"] == 0
    assert data["unchanged_count"] == 1


@pytest.mark.asyncio
async def test_run_diff_base_not_found(test_client: AsyncTestClient, async_session):
    from uuid import uuid4
    fake_run = str(uuid4())
    compare_run = str(uuid4())

    response = await test_client.get(f"/api/v1/runs/{fake_run}/diff?compare_to={compare_run}")
    assert response.status_code == 500