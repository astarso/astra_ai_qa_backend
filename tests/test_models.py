"""Test model creation and relationships using async session."""

import uuid

import pytest
from sqlalchemy import select

from app.models.entities import (
    AIAnalysis,
    Attachment,
    Defect,
    Project,
    Role,
    TestCase,
    TestResult,
    TestRun,
    TestSuite,
    User,
)


@pytest.fixture
async def role(async_session):
    role = Role(code="test_role", description="Test role")
    async_session.add(role)
    await async_session.flush()
    return role


@pytest.fixture
async def user(async_session, role):
    user = User(
        email="testuser@example.com",
        full_name="Test User",
        role_id=role.id,
        is_active=True,
    )
    async_session.add(user)
    await async_session.flush()
    return user


@pytest.fixture
async def project(async_session, user):
    proj = Project(
        code="TESTPROJ",
        name="Test Project",
        owner_id=user.id,
    )
    async_session.add(proj)
    await async_session.flush()
    return proj


@pytest.fixture
async def test_suite(async_session, project):
    suite = TestSuite(
        project_id=project.id,
        name="Unit Tests",
        kind="pytest",
        config={"timeout": 30},
    )
    async_session.add(suite)
    await async_session.flush()
    return suite


@pytest.fixture
async def test_case(async_session, test_suite):
    case = TestCase(
        suite_id=test_suite.id,
        title="Test example",
        description="A sample test case",
        source="manual",
        code_path="/tests/test_example.py",
        avg_duration_ms=150.5,
    )
    async_session.add(case)
    await async_session.flush()
    return case


@pytest.fixture
async def test_run(async_session, test_suite, user):
    run = TestRun(
        suite_id=test_suite.id,
        commit_sha="a" * 40,
        branch="main",
        triggered_by=user.id,
        priority=3,
        environment="dev",
        status="pending",
    )
    async_session.add(run)
    await async_session.flush()
    return run


@pytest.mark.asyncio
async def test_role_creation(async_session, role):
    assert role.id is not None
    assert role.code == "test_role"
    assert role.description == "Test role"
    result = await async_session.execute(select(Role).where(Role.code == "test_role"))
    found = result.scalars().first()
    assert found is not None


@pytest.mark.asyncio
async def test_user_creation(async_session, user, role):
    assert user.id is not None
    assert user.email == "testuser@example.com"
    assert user.full_name == "Test User"
    assert user.role_id == role.id
    assert user.is_active is True


@pytest.mark.asyncio
async def test_user_role_relationship(async_session, user, role):
    await async_session.refresh(user, ["role"])
    assert user.role.code == "test_role"


@pytest.mark.asyncio
async def test_project_creation(async_session, project, user):
    assert project.id is not None
    assert project.code == "TESTPROJ"
    assert project.name == "Test Project"
    assert project.owner_id == user.id


@pytest.mark.asyncio
async def test_project_owner_relationship(async_session, project, user):
    await async_session.refresh(project, ["owner"])
    assert project.owner.id == user.id


@pytest.mark.asyncio
async def test_testsuite_creation(async_session, test_suite, project):
    assert test_suite.id is not None
    assert test_suite.name == "Unit Tests"
    assert test_suite.kind == "pytest"
    assert test_suite.config == {"timeout": 30}
    assert test_suite.project_id == project.id


@pytest.mark.asyncio
async def test_testsuite_project_relationship(async_session, test_suite, project):
    await async_session.refresh(test_suite, ["project"])
    assert test_suite.project.id == project.id


@pytest.mark.asyncio
async def test_testcase_creation(async_session, test_case, test_suite):
    assert test_case.id is not None
    assert test_case.title == "Test example"
    assert test_case.description == "A sample test case"
    assert test_case.source == "manual"
    assert test_case.code_path == "/tests/test_example.py"
    assert test_case.avg_duration_ms == 150.5
    assert test_case.suite_id == test_suite.id


@pytest.mark.asyncio
async def test_testcase_suite_relationship(async_session, test_case, test_suite):
    await async_session.refresh(test_case, ["suite"])
    assert test_case.suite.id == test_suite.id


@pytest.mark.asyncio
async def test_testrun_creation(async_session, test_run, test_suite, user):
    assert test_run.id is not None
    assert test_run.commit_sha == "a" * 40
    assert test_run.branch == "main"
    assert test_run.triggered_by == user.id
    assert test_run.priority == 3
    assert test_run.environment == "dev"
    assert test_run.status == "pending"


@pytest.mark.asyncio
async def test_testrun_suite_relationship(async_session, test_run, test_suite):
    await async_session.refresh(test_run, ["suite"])
    assert test_run.suite.id == test_suite.id


@pytest.mark.asyncio
async def test_testresult_creation(async_session, test_run, test_case):
    result = TestResult(
        run_id=test_run.id,
        test_case_id=test_case.id,
        status="passed",
        duration_ms=45.2,
        error_message=None,
        stdout="All tests passed",
        stderr=None,
    )
    async_session.add(result)
    await async_session.flush()
    assert result.id is not None
    assert result.status == "passed"
    assert result.duration_ms == 45.2


@pytest.mark.asyncio
async def test_attachment_creation(async_session, test_result, test_run, test_case):
    attachment = Attachment(
        result_id=test_result.id,
        file_path="/artifacts/screenshot.png",
        mime_type="image/png",
        size=102400,
    )
    async_session.add(attachment)
    await async_session.flush()
    assert attachment.id is not None
    assert attachment.file_path == "/artifacts/screenshot.png"
    assert attachment.mime_type == "image/png"
    assert attachment.size == 102400


@pytest.fixture
async def test_result(async_session, test_run, test_case):
    result = TestResult(
        run_id=test_run.id,
        test_case_id=test_case.id,
        status="failed",
        duration_ms=30.0,
        error_message="AssertionError: expected 1, got 2",
        stack_trace="File '/tests/test_example.py', line 10",
        stdout="FAIL test_example.py",
        stderr=None,
    )
    async_session.add(result)
    await async_session.flush()
    return result


@pytest.mark.asyncio
async def test_aianalysis_creation(async_session, test_result):
    analysis = AIAnalysis(
        result_id=test_result.id,
        category="assertion_error",
        probability=0.95,
        short_cause="Values mismatch in comparison",
        suggestion="Check the input data generation logic",
        llm_model="gigachat-2",
        prompt_hash="abc123",
        error_embedding=None,
    )
    async_session.add(analysis)
    await async_session.flush()
    assert analysis.id is not None
    assert analysis.category == "assertion_error"
    assert analysis.probability == 0.95
    assert analysis.result_id == test_result.id


@pytest.mark.asyncio
async def test_defect_creation(async_session):
    defect = Defect(
        title="Login fails on Firefox",
        description="Users cannot log in when using Firefox browser",
        severity=2,
        status="open",
        jira_key="PROJ-123",
    )
    async_session.add(defect)
    await async_session.flush()
    assert defect.id is not None
    assert defect.title == "Login fails on Firefox"
    assert defect.severity == 2
    assert defect.status == "open"
    assert defect.jira_key == "PROJ-123"


@pytest.mark.asyncio
async def test_project_has_test_suites(async_session, project, test_suite):
    await async_session.refresh(project, ["test_suites"])
    assert len(project.test_suites) >= 1
    assert any(s.name == "Unit Tests" for s in project.test_suites)


@pytest.mark.asyncio
async def test_suite_has_test_cases(async_session, test_suite, test_case):
    await async_session.refresh(test_suite, ["test_cases"])
    assert len(test_suite.test_cases) >= 1
    assert any(c.title == "Test example" for c in test_suite.test_cases)


@pytest.mark.asyncio
async def test_run_has_results(async_session, test_run, test_result):
    await async_session.refresh(test_run, ["results"])
    assert len(test_run.results) >= 1