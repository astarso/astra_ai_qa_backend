"""Tests for DORA metrics analytics."""

import pytest
from datetime import datetime, timedelta, timezone
from litestar.testing import AsyncTestClient
from app.models.entities import Project, Role, TestRun, TestSuite, User


async def _seed_dora_data(async_session) -> None:
    """Create test runs for DORA calculation."""
    role = Role(code="dora_role", description="DORA test")
    async_session.add(role)
    await async_session.flush()

    user = User(email="dora@example.com", full_name="DORA", role_id=role.id)
    async_session.add(user)
    await async_session.flush()

    project = Project(code="DORA", name="DORA Project", owner_id=user.id)
    async_session.add(project)
    await async_session.flush()

    suite = TestSuite(project_id=project.id, name="DORA Suite", kind="unit", config={})
    async_session.add(suite)
    await async_session.flush()

    now = datetime.now(timezone.utc)
    # 3 passed runs, 2 failed runs over various hours
    for i, (status, hours_ago) in enumerate([
        ("passed", 1), ("passed", 5), ("failed", 10),
        ("passed", 20), ("failed", 25),
    ]):
        started = now - timedelta(hours=hours_ago, minutes=30)
        finished = now - timedelta(hours=hours_ago)
        run = TestRun(
            suite_id=suite.id, commit_sha=f"sha{i:040d}", branch="main",
            triggered_by=user.id, priority=3, environment="dev",
            status=status, started_at=started, finished_at=finished,
        )
        async_session.add(run)
    await async_session.flush()


@pytest.mark.asyncio
async def test_dora_metrics(test_client: AsyncTestClient, async_session):
    await _seed_dora_data(async_session)
    response = await test_client.get("/api/v1/analytics/dora")
    assert response.status_code == 200
    data = response.json()
    assert "lead_time_hours" in data
    assert "deployment_frequency_per_day" in data
    assert "change_failure_rate_pct" in data
    assert "mttr_hours" in data
    # 2 failed / 5 total = 40%
    assert data["change_failure_rate_pct"] == 40.0
    # 3 passed / 30 days = 0.1 per day
    assert data["deployment_frequency_per_day"] == 0.1


@pytest.mark.asyncio
async def test_dora_metrics_empty(test_client: AsyncTestClient):
    """With no runs, all metrics should be 0."""
    response = await test_client.get("/api/v1/analytics/dora")
    assert response.status_code == 200
    data = response.json()
    assert data["lead_time_hours"] == 0.0
    assert data["change_failure_rate_pct"] == 0.0


@pytest.mark.asyncio
async def test_dora_metrics_custom_days(test_client: AsyncTestClient, async_session):
    response = await test_client.get("/api/v1/analytics/dora?days=7")
    assert response.status_code == 200