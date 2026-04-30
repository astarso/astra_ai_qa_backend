import uuid

import pytest
from sqlalchemy import insert, select

from app.models.entities import Project, TestSuite, TestRun, TestResult, User, Role, TestCase


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_prometheus_format(test_client, async_session):
    response = await test_client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"

    text = response.text
    assert "astra_test_runs_total" in text
    assert "astra_test_runs_failed_total" in text
    assert "astra_test_results_total" in text
    assert 'status="passed"' in text
    assert 'status="failed"' in text
    assert 'status="skipped"' in text
    assert "astra_test_run_duration_seconds" in text


@pytest.mark.asyncio
async def test_metrics_returns_zero_when_no_data(test_client, async_session):
    response = await test_client.get("/metrics")
    assert response.status_code == 200

    text = response.text
    assert "astra_test_runs_total 0" in text
    assert "astra_test_runs_failed_total 0" in text
    assert 'status="passed"} 0' in text
    assert 'status="failed"} 0' in text
    assert 'status="skipped"} 0' in text


@pytest.mark.asyncio
async def test_metrics_counts_test_runs(test_client, async_session):
    await async_session.execute(insert(Role).values(code="admin", description="Admin"))
    await async_session.commit()

    role_id = (await async_session.execute(select(Role).limit(1))).scalar()
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    suite_id = uuid.uuid4()

    await async_session.execute(
        insert(User).values(
            id=user_id,
            email="test@example.com",
            full_name="Test User",
            role_id=role_id.id,
            is_active=True,
        )
    )
    await async_session.execute(
        insert(Project).values(
            id=project_id,
            code="TEST",
            name="Test Project",
            owner_id=user_id,
        )
    )
    await async_session.execute(
        insert(TestSuite).values(
            id=suite_id,
            project_id=project_id,
            name="Test Suite",
            kind="automated",
        )
    )

    run1_id = uuid.uuid4()
    run2_id = uuid.uuid4()
    run3_id = uuid.uuid4()

    await async_session.execute(
        insert(TestRun).values(
            id=run1_id,
            suite_id=suite_id,
            commit_sha="a" * 40,
            branch="main",
            triggered_by=user_id,
            priority=0,
            environment="test",
            status="passed",
        )
    )
    await async_session.execute(
        insert(TestRun).values(
            id=run2_id,
            suite_id=suite_id,
            commit_sha="b" * 40,
            branch="main",
            triggered_by=user_id,
            priority=0,
            environment="test",
            status="failed",
        )
    )
    await async_session.execute(
        insert(TestRun).values(
            id=run3_id,
            suite_id=suite_id,
            commit_sha="c" * 40,
            branch="develop",
            triggered_by=user_id,
            priority=0,
            environment="test",
            status="passed",
        )
    )

    await async_session.commit()

    response = await test_client.get("/metrics")
    assert response.status_code == 200

    text = response.text
    assert "astra_test_runs_total 3" in text
    assert "astra_test_runs_failed_total 1" in text


@pytest.mark.asyncio
async def test_metrics_counts_test_results_by_status(test_client, async_session):
    await async_session.execute(insert(Role).values(code="admin", description="Admin"))
    await async_session.commit()

    role_id = (await async_session.execute(select(Role).limit(1))).scalar()
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    suite_id = uuid.uuid4()
    case_id = uuid.uuid4()

    await async_session.execute(
        insert(User).values(
            id=user_id,
            email="test2@example.com",
            full_name="Test User 2",
            role_id=role_id.id,
            is_active=True,
        )
    )
    await async_session.execute(
        insert(Project).values(
            id=project_id,
            code="TEST2",
            name="Test Project 2",
            owner_id=user_id,
        )
    )
    await async_session.execute(
        insert(TestSuite).values(
            id=suite_id,
            project_id=project_id,
            name="Test Suite 2",
            kind="automated",
        )
    )
    await async_session.execute(
        insert(TestCase).values(
            id=case_id,
            suite_id=suite_id,
            title="Test Case",
            source="test",
        )
    )

    run_id = uuid.uuid4()
    await async_session.execute(
        insert(TestRun).values(
            id=run_id,
            suite_id=suite_id,
            commit_sha="d" * 40,
            branch="main",
            triggered_by=user_id,
            priority=0,
            environment="test",
            status="passed",
        )
    )

    await async_session.execute(
        insert(TestResult).values(
            id=uuid.uuid4(),
            run_id=run_id,
            test_case_id=case_id,
            status="passed",
            duration_ms=100.0,
        )
    )
    await async_session.execute(
        insert(TestResult).values(
            id=uuid.uuid4(),
            run_id=run_id,
            test_case_id=case_id,
            status="failed",
            duration_ms=200.0,
        )
    )
    await async_session.execute(
        insert(TestResult).values(
            id=uuid.uuid4(),
            run_id=run_id,
            test_case_id=case_id,
            status="skipped",
            duration_ms=0.0,
        )
    )

    await async_session.commit()

    response = await test_client.get("/metrics")
    assert response.status_code == 200

    text = response.text
    assert 'status="passed"} 1' in text
    assert 'status="failed"} 1' in text
    assert 'status="skipped"} 1' in text