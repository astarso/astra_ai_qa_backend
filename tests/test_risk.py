import pytest
from litestar.testing import AsyncTestClient
from app.models.entities import Project, Role, TestRun, TestCase, TestSuite, TestResult, User, AIAnalysis


async def _seed_run_with_results(async_session):
    role = Role(code="risk_role", description="Risk test")
    async_session.add(role)
    await async_session.flush()

    user = User(email="risk@example.com", full_name="Risk User", role_id=role.id)
    async_session.add(user)
    await async_session.flush()

    project = Project(code="RISK", name="Risk Project", owner_id=user.id)
    async_session.add(project)
    await async_session.flush()

    suite = TestSuite(project_id=project.id, name="Risk Suite", kind="unit", config={})
    async_session.add(suite)
    await async_session.flush()

    case1 = TestCase(suite_id=suite.id, title="Passing Test", source="auto")
    case2 = TestCase(suite_id=suite.id, title="Real Defect Test", source="auto")
    case3 = TestCase(suite_id=suite.id, title="Flaky Test", source="auto")
    case4 = TestCase(suite_id=suite.id, title="Infra Test", source="auto")
    case5 = TestCase(suite_id=suite.id, title="Skipped Test", source="auto")
    async_session.add_all([case1, case2, case3, case4, case5])
    await async_session.flush()

    from datetime import datetime
    run = TestRun(
        suite_id=suite.id, commit_sha="a" * 40, branch="main",
        triggered_by=user.id, priority=3, environment="dev",
        status="failed", started_at=datetime.utcnow(), finished_at=datetime.utcnow(),
    )
    async_session.add(run)
    await async_session.flush()

    r1 = TestResult(run_id=run.id, test_case_id=case1.id, status="passed", duration_ms=100)
    r2 = TestResult(run_id=run.id, test_case_id=case2.id, status="failed", duration_ms=200)
    r3 = TestResult(run_id=run.id, test_case_id=case3.id, status="failed", duration_ms=150)
    r4 = TestResult(run_id=run.id, test_case_id=case4.id, status="failed", duration_ms=120)
    r5 = TestResult(run_id=run.id, test_case_id=case5.id, status="skipped", duration_ms=50)
    async_session.add_all([r1, r2, r3, r4, r5])
    await async_session.flush()

    a1 = AIAnalysis(result_id=r2.id, category="real_defect", probability=0.9, short_cause="Logic error", suggestion="Fix the condition", llm_model="gpt-4", prompt_hash="abc")
    a2 = AIAnalysis(result_id=r3.id, category="flaky", probability=0.7, short_cause="Timing issue", suggestion="Add retry", llm_model="gpt-4", prompt_hash="def")
    a3 = AIAnalysis(result_id=r4.id, category="infrastructure", probability=0.85, short_cause="DB timeout", suggestion="Increase timeout", llm_model="gpt-4", prompt_hash="ghi")
    async_session.add_all([a1, a2, a3])
    await async_session.flush()

    return str(run.id)


@pytest.mark.asyncio
async def test_risk_score_success(test_client: AsyncTestClient, async_session):
    run_id = await _seed_run_with_results(async_session)
    response = await test_client.get(f"/api/v1/runs/{run_id}/risk")
    assert response.status_code == 200
    data = response.json()

    assert data["run_id"] == run_id
    assert data["total_tests"] == 5
    assert data["passed_count"] == 1
    assert data["failed_count"] == 3
    assert data["skipped_count"] == 1

    assert data["score"] > 0
    assert data["risk_level"] in ["low", "medium", "high", "critical"]
    assert data["recommendation"] in ["release", "release_with_caution", "investigate", "hold"]

    assert len(data["factors"]) == 3
    factor_categories = {f["category"] for f in data["factors"]}
    assert "real_defect" in factor_categories
    assert "flaky" in factor_categories
    assert "infrastructure" in factor_categories

    for factor in data["factors"]:
        if factor["category"] == "real_defect":
            assert factor["weight"] == 3.0
        elif factor["category"] == "infrastructure":
            assert factor["weight"] == 2.0
        elif factor["category"] == "flaky":
            assert factor["weight"] == 1.0


@pytest.mark.asyncio
async def test_risk_score_all_passed(test_client: AsyncTestClient, async_session):
    role = Role(code="risk_pass_role", description="Risk pass test")
    async_session.add(role)
    await async_session.flush()

    user = User(email="riskpass@example.com", full_name="Risk Pass User", role_id=role.id)
    async_session.add(user)
    await async_session.flush()

    project = Project(code="RISKPASS", name="Risk Pass Project", owner_id=user.id)
    async_session.add(project)
    await async_session.flush()

    suite = TestSuite(project_id=project.id, name="Risk Pass Suite", kind="unit", config={})
    async_session.add(suite)
    await async_session.flush()

    case1 = TestCase(suite_id=suite.id, title="All Pass Test", source="auto")
    case2 = TestCase(suite_id=suite.id, title="Another Pass", source="auto")
    async_session.add_all([case1, case2])
    await async_session.flush()

    from datetime import datetime
    run = TestRun(
        suite_id=suite.id, commit_sha="b" * 40, branch="main",
        triggered_by=user.id, priority=3, environment="dev",
        status="passed", started_at=datetime.utcnow(), finished_at=datetime.utcnow(),
    )
    async_session.add(run)
    await async_session.flush()

    r1 = TestResult(run_id=run.id, test_case_id=case1.id, status="passed", duration_ms=100)
    r2 = TestResult(run_id=run.id, test_case_id=case2.id, status="passed", duration_ms=100)
    async_session.add_all([r1, r2])
    await async_session.flush()

    response = await test_client.get(f"/api/v1/runs/{run.id}/risk")
    assert response.status_code == 200
    data = response.json()

    assert data["score"] == 0
    assert data["risk_level"] == "low"
    assert data["recommendation"] == "release"
    assert data["failed_count"] == 0
    assert len(data["factors"]) == 0


@pytest.mark.asyncio
async def test_risk_score_not_found(test_client: AsyncTestClient, async_session):
    from uuid import uuid4
    fake_run = str(uuid4())

    response = await test_client.get(f"/api/v1/runs/{fake_run}/risk")
    assert response.status_code == 500