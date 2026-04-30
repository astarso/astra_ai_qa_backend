import pytest

from app.models.entities import (
    Project,
    Role,
    TestCase,
    TestResult,
    TestRun,
    TestSuite,
    User,
)


async def _create_test_run_with_results(test_client, async_session) -> str:
    role = Role(code="report_test_role", description="Report test role")
    async_session.add(role)
    await async_session.flush()

    user = User(
        email="report@example.com",
        full_name="Report User",
        role_id=role.id,
        is_active=True,
    )
    async_session.add(user)
    await async_session.flush()

    project = Project(
        code="RPTPRJ",
        name="Report Project",
        owner_id=user.id,
    )
    async_session.add(project)
    await async_session.flush()

    suite = TestSuite(
        project_id=project.id,
        name="Report Suite",
        kind="unit",
        config={},
    )
    async_session.add(suite)
    await async_session.flush()

    case1 = TestCase(suite_id=suite.id, title="Test Pass 1", source="auto")
    case2 = TestCase(suite_id=suite.id, title="Test Fail", source="auto")
    case3 = TestCase(suite_id=suite.id, title="Test Pass 2", source="auto")
    async_session.add_all([case1, case2, case3])
    await async_session.flush()

    run = TestRun(
        suite_id=suite.id,
        commit_sha="a" * 40,
        branch="main",
        triggered_by=user.id,
        priority=3,
        environment="dev",
        status="completed",
    )
    async_session.add(run)
    await async_session.flush()

    results = [
        TestResult(run_id=run.id, test_case_id=case1.id, status="passed", duration_ms=100),
        TestResult(run_id=run.id, test_case_id=case2.id, status="failed", duration_ms=200,
                   error_message="Assertion failed: expected True, got False"),
        TestResult(run_id=run.id, test_case_id=case3.id, status="passed", duration_ms=50),
    ]
    async_session.add_all(results)
    await async_session.flush()

    return str(run.id)


@pytest.mark.asyncio
async def test_generate_report(test_client, async_session):
    run_id = await _create_test_run_with_results(test_client, async_session)
    response = await test_client.post(f"/api/v1/runs/{run_id}/report")
    assert response.status_code == 201
    assert response.headers["content-type"] == "application/pdf"
    assert len(response.content) > 0
    assert response.content[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_report_nonexistent_run(test_client):
    fake_id = "00000000-0000-0000-0000-000000000999"
    response = await test_client.post(f"/api/v1/runs/{fake_id}/report")
    assert response.status_code == 500
