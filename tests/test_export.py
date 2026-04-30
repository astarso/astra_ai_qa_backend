import pytest
from litestar.testing import AsyncTestClient
from app.models.entities import Project, Role, TestRun, TestCase, TestSuite, TestResult, User


async def _seed_run_with_results(async_session):
    role = Role(code="export_role", description="Export test")
    async_session.add(role)
    await async_session.flush()

    user = User(email="export@example.com", full_name="Export User", role_id=role.id)
    async_session.add(user)
    await async_session.flush()

    project = Project(code="EXPORT", name="Export Project", owner_id=user.id)
    async_session.add(project)
    await async_session.flush()

    suite = TestSuite(project_id=project.id, name="Export Suite", kind="unit", config={})
    async_session.add(suite)
    await async_session.flush()

    case1 = TestCase(suite_id=suite.id, title="Test Login", source="auto")
    case2 = TestCase(suite_id=suite.id, title="Test Logout", source="auto")
    case3 = TestCase(suite_id=suite.id, title="Test Search", source="auto")
    async_session.add_all([case1, case2, case3])
    await async_session.flush()

    from datetime import datetime
    run = TestRun(
        suite_id=suite.id, commit_sha="e" * 40, branch="main",
        triggered_by=user.id, priority=3, environment="dev",
        status="failed", started_at=datetime.utcnow(), finished_at=datetime.utcnow(),
    )
    async_session.add(run)
    await async_session.flush()

    r1 = TestResult(run_id=run.id, test_case_id=case1.id, status="passed", duration_ms=150)
    r2 = TestResult(run_id=run.id, test_case_id=case2.id, status="failed", duration_ms=200, error_message="AssertionError: expected 200")
    r3 = TestResult(run_id=run.id, test_case_id=case3.id, status="skipped", duration_ms=None)
    async_session.add_all([r1, r2, r3])
    await async_session.flush()

    return str(run.id), case1.id, case2.id, case3.id


@pytest.mark.asyncio
async def test_export_json_success(test_client: AsyncTestClient, async_session):
    run_id, case1_id, case2_id, case3_id = await _seed_run_with_results(async_session)

    response = await test_client.get(f"/api/v1/runs/{run_id}/export?format=json")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert "attachment" in response.headers.get("content-disposition", "")
    assert "run-" + run_id + ".json" in response.headers.get("content-disposition", "")

    data = response.json()
    assert len(data) == 3

    login = next(r for r in data if r["title"] == "Test Login")
    assert login["status"] == "passed"
    assert login["duration_ms"] == 150
    assert login["error_message"] is None
    assert str(case1_id) == login["test_case_id"]

    logout = next(r for r in data if r["title"] == "Test Logout")
    assert logout["status"] == "failed"
    assert logout["duration_ms"] == 200
    assert "AssertionError" in logout["error_message"]
    assert str(case2_id) == logout["test_case_id"]

    search = next(r for r in data if r["title"] == "Test Search")
    assert search["status"] == "skipped"
    assert search["duration_ms"] is None


@pytest.mark.asyncio
async def test_export_csv_success(test_client: AsyncTestClient, async_session):
    run_id, case1_id, case2_id, case3_id = await _seed_run_with_results(async_session)

    response = await test_client.get(f"/api/v1/runs/{run_id}/export?format=csv")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "attachment" in response.headers.get("content-disposition", "")
    assert "run-" + run_id + ".csv" in response.headers.get("content-disposition", "")

    content = response.content.decode("utf-8")
    lines = content.strip().splitlines()

    assert lines[0] == "test_case_id,title,status,duration_ms,error_message"
    assert len(lines) == 4

    for line in lines[1:]:
        parts = line.split(",")
        assert len(parts) == 5


@pytest.mark.asyncio
async def test_export_default_format_is_json(test_client: AsyncTestClient, async_session):
    run_id, _, _, _ = await _seed_run_with_results(async_session)

    response = await test_client.get(f"/api/v1/runs/{run_id}/export")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"

    data = response.json()
    assert len(data) == 3


@pytest.mark.asyncio
async def test_export_empty_run(test_client: AsyncTestClient, async_session):
    role = Role(code="empty_role", description="Empty test")
    async_session.add(role)
    await async_session.flush()

    user = User(email="empty@example.com", full_name="Empty User", role_id=role.id)
    async_session.add(user)
    await async_session.flush()

    project = Project(code="EMPTY", name="Empty Project", owner_id=user.id)
    async_session.add(project)
    await async_session.flush()

    suite = TestSuite(project_id=project.id, name="Empty Suite", kind="unit", config={})
    async_session.add(suite)
    await async_session.flush()

    from datetime import datetime
    run = TestRun(
        suite_id=suite.id, commit_sha="f" * 40, branch="main",
        triggered_by=user.id, priority=3, environment="dev",
        status="passed", started_at=datetime.utcnow(), finished_at=datetime.utcnow(),
    )
    async_session.add(run)
    await async_session.flush()

    response = await test_client.get(f"/api/v1/runs/{run.id}/export?format=json")
    assert response.status_code == 200
    data = response.json()
    assert data == []

    response = await test_client.get(f"/api/v1/runs/{run.id}/export?format=csv")
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    lines = content.strip().splitlines()
    assert lines[0] == "test_case_id,title,status,duration_ms,error_message"
    assert len(lines) == 1


@pytest.mark.asyncio
async def test_export_parquet_not_implemented(test_client: AsyncTestClient, async_session):
    run_id, _, _, _ = await _seed_run_with_results(async_session)

    response = await test_client.get(f"/api/v1/runs/{run_id}/export?format=parquet")
    assert response.status_code == 501
    data = response.json()
    assert "error" in data
    assert "pandas" in data["error"]
    assert "pyarrow" in data["error"]