import pytest
from litestar.testing import AsyncTestClient
from app.models.entities import Project, Role, TestRun, TestCase, TestSuite, User


async def _seed_suite_with_cases(async_session):
    role = Role(code="import_role", description="Import test")
    async_session.add(role)
    await async_session.flush()

    user = User(email="import@example.com", full_name="Import User", role_id=role.id)
    async_session.add(user)
    await async_session.flush()

    project = Project(code="IMPORT", name="Import Project", owner_id=user.id)
    async_session.add(project)
    await async_session.flush()

    suite = TestSuite(project_id=project.id, name="Import Suite", kind="unit", config={})
    async_session.add(suite)
    await async_session.flush()

    case1 = TestCase(suite_id=suite.id, title="Test Login", source="auto")
    case2 = TestCase(suite_id=suite.id, title="Test Logout", source="auto")
    async_session.add_all([case1, case2])
    await async_session.flush()

    return str(suite.id)


ALLURE_JSON = """[
    {
        "name": "Test Login",
        "description": "Verify login functionality",
        "status": "passed",
        "severity": "normal"
    },
    {
        "name": "Test Logout",
        "description": "Verify logout functionality",
        "status": "failed",
        "severity": "critical"
    }
]"""

ALLURE_JSON_SINGLE = """{
    "name": "Single Test Case",
    "description": "A single test case",
    "status": "passed"
}"""

TESTRAIL_JSON = """{
    "cases": [
        {"title": "Test Login", "section": "Auth", "steps": "1. Open app\\n2. Login"},
        {"title": "Test Logout", "section": "Auth", "steps": "1. Logout"}
    ]
}"""

TESTIT_JSON = """{
    "testCases": [
        {"name": "Test Login", "description": "Verify login", "steps": []},
        {"name": "Test Logout", "description": "Verify logout", "steps": []}
    ]
}"""

ALLURE_XML = """<testsuite name="AllureTests" tests="3" failures="1">
    <testcase name="Test Login" status="passed" time="0.5"/>
    <testcase name="Test Logout" status="failed" time="0.3">
        <failure message="AssertionError: expected 200">Traceback: logout failed</failure>
    </testcase>
    <testcase name="Test API" status="passed" time="1.2"/>
</testsuite>"""

ALLURE_XML_NESTED_FAILURE = """<testsuite name="AllureTests" tests="2" failures="1">
    <testcase name="Test Login" status="passed" time="0.5"/>
    <testcase name="Test Failed" status="passed" time="0.3">
        <failure message="Test failed">Actual error</failure>
    </testcase>
</testsuite>"""


@pytest.mark.asyncio
async def test_import_test_cases_allure_json(test_client: AsyncTestClient, async_session):
    suite_id = await _seed_suite_with_cases(async_session)
    response = await test_client.post(
        f"/api/v1/test-cases/import?suite_id={suite_id}&format=allure",
        json={"content": ALLURE_JSON},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["imported"] == 2
    assert data["format"] == "allure_json"


@pytest.mark.asyncio
async def test_import_test_cases_allure_single(test_client: AsyncTestClient, async_session):
    suite_id = await _seed_suite_with_cases(async_session)
    response = await test_client.post(
        f"/api/v1/test-cases/import?suite_id={suite_id}&format=allure",
        json={"content": ALLURE_JSON_SINGLE},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["imported"] == 1


@pytest.mark.asyncio
async def test_import_test_cases_testrail(test_client: AsyncTestClient, async_session):
    suite_id = await _seed_suite_with_cases(async_session)
    response = await test_client.post(
        f"/api/v1/test-cases/import?suite_id={suite_id}&format=testrail",
        json={"content": TESTRAIL_JSON},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["imported"] == 2
    assert data["format"] == "testrail"


@pytest.mark.asyncio
async def test_import_test_cases_testit(test_client: AsyncTestClient, async_session):
    suite_id = await _seed_suite_with_cases(async_session)
    response = await test_client.post(
        f"/api/v1/test-cases/import?suite_id={suite_id}&format=testit",
        json={"content": TESTIT_JSON},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["imported"] == 2
    assert data["format"] == "testit"


@pytest.mark.asyncio
async def test_import_test_cases_missing_content(test_client: AsyncTestClient, async_session):
    suite_id = await _seed_suite_with_cases(async_session)
    response = await test_client.post(
        f"/api/v1/test-cases/import?suite_id={suite_id}&format=allure",
        json={},
    )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_import_test_cases_invalid_json(test_client: AsyncTestClient, async_session):
    suite_id = await _seed_suite_with_cases(async_session)
    response = await test_client.post(
        f"/api/v1/test-cases/import?suite_id={suite_id}&format=allure",
        json={"content": "not valid json"},
    )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_import_allure_xml_success(test_client: AsyncTestClient, async_session):
    suite_id = await _seed_suite_with_cases(async_session)

    from datetime import datetime
    from app.models.entities import User, TestRun
    user = User(email="import_allure@example.com", full_name="Import Allure User", role_id=1)
    async_session.add(user)
    await async_session.flush()

    run = TestRun(
        suite_id=suite_id, commit_sha="a" * 40, branch="main",
        triggered_by=user.id, priority=3, environment="dev",
        status="pending", started_at=datetime.utcnow(),
    )
    async_session.add(run)
    await async_session.flush()
    run_id = str(run.id)

    response = await test_client.post(
        f"/api/v1/runs/{run_id}/import/allure",
        json={"xml_content": ALLURE_XML},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["imported"] == 3
    assert data["skipped"] == 0
    assert data["format"] == "allure_xml"


@pytest.mark.asyncio
async def test_import_allure_xml_nested_failure(test_client: AsyncTestClient, async_session):
    suite_id = await _seed_suite_with_cases(async_session)

    from datetime import datetime
    from app.models.entities import User, TestRun
    user = User(email="import_allure2@example.com", full_name="Import Allure User 2", role_id=1)
    async_session.add(user)
    await async_session.flush()

    run = TestRun(
        suite_id=suite_id, commit_sha="b" * 40, branch="main",
        triggered_by=user.id, priority=3, environment="dev",
        status="pending", started_at=datetime.utcnow(),
    )
    async_session.add(run)
    await async_session.flush()
    run_id = str(run.id)

    response = await test_client.post(
        f"/api/v1/runs/{run_id}/import/allure",
        json={"xml_content": ALLURE_XML_NESTED_FAILURE},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["imported"] == 2
    assert data["skipped"] == 0


@pytest.mark.asyncio
async def test_import_allure_xml_missing_content(test_client: AsyncTestClient, async_session):
    suite_id = await _seed_suite_with_cases(async_session)

    from datetime import datetime
    from app.models.entities import User, TestRun
    user = User(email="import_allure3@example.com", full_name="Import Allure User 3", role_id=1)
    async_session.add(user)
    await async_session.flush()

    run = TestRun(
        suite_id=suite_id, commit_sha="c" * 40, branch="main",
        triggered_by=user.id, priority=3, environment="dev",
        status="pending", started_at=datetime.utcnow(),
    )
    async_session.add(run)
    await async_session.flush()
    run_id = str(run.id)

    response = await test_client.post(
        f"/api/v1/runs/{run_id}/import/allure",
        json={},
    )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_import_allure_xml_invalid_xml(test_client: AsyncTestClient, async_session):
    suite_id = await _seed_suite_with_cases(async_session)

    from datetime import datetime
    from app.models.entities import User, TestRun
    user = User(email="import_allure4@example.com", full_name="Import Allure User 4", role_id=1)
    async_session.add(user)
    await async_session.flush()

    run = TestRun(
        suite_id=suite_id, commit_sha="d" * 40, branch="main",
        triggered_by=user.id, priority=3, environment="dev",
        status="pending", started_at=datetime.utcnow(),
    )
    async_session.add(run)
    await async_session.flush()
    run_id = str(run.id)

    response = await test_client.post(
        f"/api/v1/runs/{run_id}/import/allure",
        json={"xml_content": "not valid xml <"},
    )
    assert response.status_code == 500