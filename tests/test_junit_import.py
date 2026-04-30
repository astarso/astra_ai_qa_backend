import pytest
from litestar.testing import AsyncTestClient
from app.models.entities import Project, Role, TestRun, TestCase, TestSuite, TestResult, User


async def _seed_run_with_cases(async_session):
    role = Role(code="junit_role", description="JUnit test")
    async_session.add(role)
    await async_session.flush()

    user = User(email="junit@example.com", full_name="JUnit User", role_id=role.id)
    async_session.add(user)
    await async_session.flush()

    project = Project(code="JUNIT", name="JUnit Project", owner_id=user.id)
    async_session.add(project)
    await async_session.flush()

    suite = TestSuite(project_id=project.id, name="JUnit Suite", kind="unit", config={})
    async_session.add(suite)
    await async_session.flush()

    case1 = TestCase(suite_id=suite.id, title="Test Login", source="auto")
    case2 = TestCase(suite_id=suite.id, title="Test Logout", source="auto")
    case3 = TestCase(suite_id=suite.id, title="Test API", source="auto")
    async_session.add_all([case1, case2, case3])
    await async_session.flush()

    from datetime import datetime
    run = TestRun(
        suite_id=suite.id, commit_sha="j" * 40, branch="main",
        triggered_by=user.id, priority=3, environment="dev",
        status="pending", started_at=datetime.utcnow(),
    )
    async_session.add(run)
    await async_session.flush()

    return str(run.id)


JUNIT_XML = """<testsuites>
  <testsuite name="Suite1" tests="3" failures="1" errors="0">
    <testcase classname="tests.test_login" name="Test Login" time="0.5" />
    <testcase classname="tests.test_logout" name="Test Logout" time="0.3">
      <failure message="AssertionError: expected 200">Traceback...</failure>
    </testcase>
    <testcase classname="tests.test_api" name="Test API" time="1.2" />
  </testsuite>
</testsuites>"""

JUNIT_XML_NO_SUITES = """<testsuite name="SingleSuite" tests="2" failures="0" errors="0">
  <testcase classname="tests.test_login" name="Test Login" time="0.5" />
  <testcase classname="tests.test_api" name="Test API" time="1.2" />
</testsuite>"""

JUNIT_XML_SOME_NOT_FOUND = """<testsuites>
  <testsuite name="Suite1" tests="3" failures="0" errors="0">
    <testcase classname="tests.test_login" name="Test Login" time="0.5" />
    <testcase classname="tests.test_unknown" name="Test Unknown" time="0.1" />
    <testcase classname="tests.test_api" name="Test API" time="1.2" />
  </testsuite>
</testsuites>"""


@pytest.mark.asyncio
async def test_import_junit_success(test_client: AsyncTestClient, async_session):
    run_id = await _seed_run_with_cases(async_session)
    response = await test_client.post(
        f"/api/v1/runs/{run_id}/import/junit",
        json={"xml_content": JUNIT_XML},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["imported"] == 3
    assert data["skipped"] == 0
    assert data["errors"] == 0

    from sqlalchemy import select
    from app.models.entities import TestResult
    stmt = select(TestResult).where(TestResult.run_id == run_id)
    result = await async_session.execute(stmt)
    results = list(result.scalars().all())
    assert len(results) == 3

    passed = [r for r in results if r.status == "passed"]
    failed = [r for r in results if r.status == "failed"]
    assert len(passed) == 2
    assert len(failed) == 1
    assert failed[0].error_message == "AssertionError: expected 200"
    assert failed[0].stack_trace == "Traceback..."


@pytest.mark.asyncio
async def test_import_junit_no_suites_element(test_client: AsyncTestClient, async_session):
    run_id = await _seed_run_with_cases(async_session)
    response = await test_client.post(
        f"/api/v1/runs/{run_id}/import/junit",
        json={"xml_content": JUNIT_XML_NO_SUITES},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["imported"] == 2


@pytest.mark.asyncio
async def test_import_junit_skips_unmatched(test_client: AsyncTestClient, async_session):
    run_id = await _seed_run_with_cases(async_session)
    response = await test_client.post(
        f"/api/v1/runs/{run_id}/import/junit",
        json={"xml_content": JUNIT_XML_SOME_NOT_FOUND},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["imported"] == 2
    assert data["skipped"] == 1


@pytest.mark.asyncio
async def test_import_junit_missing_xml_content(test_client: AsyncTestClient, async_session):
    run_id = await _seed_run_with_cases(async_session)
    response = await test_client.post(
        f"/api/v1/runs/{run_id}/import/junit",
        json={},
    )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_import_junit_invalid_xml(test_client: AsyncTestClient, async_session):
    run_id = await _seed_run_with_cases(async_session)
    response = await test_client.post(
        f"/api/v1/runs/{run_id}/import/junit",
        json={"xml_content": "not valid xml <"},
    )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_import_junit_run_not_found(test_client: AsyncTestClient, async_session):
    from uuid import uuid4
    fake_run = str(uuid4())
    response = await test_client.post(
        f"/api/v1/runs/{fake_run}/import/junit",
        json={"xml_content": JUNIT_XML},
    )
    assert response.status_code == 500