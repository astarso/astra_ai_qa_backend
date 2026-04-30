"""msgspec Struct DTOs for all API entities."""

from datetime import datetime
from typing import Optional
from uuid import UUID

import msgspec


class ProjectCreate(msgspec.Struct):
    code: str
    name: str
    owner_id: UUID


class ProjectResponse(msgspec.Struct):
    id: UUID
    code: str
    name: str
    owner_id: UUID
    created_at: str


class TestCaseCreate(msgspec.Struct):
    title: str
    source: str
    suite_id: UUID
    description: Optional[str] = None
    code_path: Optional[str] = None
    requirement_id: Optional[UUID] = None


class TestCaseResponse(msgspec.Struct):
    id: UUID
    title: str
    suite_id: UUID
    source: str
    created_at: str
    requirement_id: Optional[UUID] = None


class CreateRunPayload(msgspec.Struct):
    suite_id: UUID
    commit_sha: str
    branch: str
    triggered_by: UUID
    priority: int = 3
    environment: str = "dev"


class TestRunResponse(msgspec.Struct):
    id: UUID
    suite_id: UUID
    status: str
    commit_sha: str
    branch: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    pass_count: int = 0
    fail_count: int = 0
    skipped_count: int = 0


class SubmitResultsPayload(msgspec.Struct):
    results: list[dict]


class AIAnalysisResponse(msgspec.Struct):
    id: UUID
    result_id: UUID
    category: str
    probability: float
    short_cause: str
    suggestion: str
    llm_model: str


class DefectCreate(msgspec.Struct):
    title: str
    description: str
    severity: int
    jira_key: Optional[str] = None


class DefectResponse(msgspec.Struct):
    id: UUID
    title: str
    severity: int
    status: str
    created_at: str
    jira_key: Optional[str] = None


class DefectUpdate(msgspec.Struct):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[int] = None
    status: Optional[str] = None
    jira_key: Optional[str] = None


class TestSuiteCreate(msgspec.Struct):
    project_id: UUID
    name: str
    kind: str
    config: dict = {}


class TestSuiteResponse(msgspec.Struct):
    id: UUID
    project_id: UUID
    name: str
    kind: str
    config: dict
    created_at: str


class TestSuiteUpdate(msgspec.Struct):
    name: Optional[str] = None
    kind: Optional[str] = None
    config: Optional[dict] = None


class UserCreate(msgspec.Struct):
    email: str
    full_name: str
    role_id: int
    is_active: bool = True


class UserResponse(msgspec.Struct):
    id: UUID
    email: str
    full_name: str
    role_id: int
    is_active: bool
    created_at: str


class UserUpdate(msgspec.Struct):
    full_name: Optional[str] = None
    role_id: Optional[int] = None
    is_active: Optional[bool] = None


class SettingsResponse(msgspec.Struct):
    llm_model_name: str
    llm_temperature: float
    llm_max_tokens: int
    llm_request_timeout_seconds: int


class SettingsUpdate(msgspec.Struct):
    llm_model_name: Optional[str] = None
    llm_temperature: Optional[float] = None
    llm_max_tokens: Optional[int] = None
    llm_request_timeout_seconds: Optional[int] = None


class ReportInfo(msgspec.Struct):
    run_id: str
    branch: str
    commit_sha: str
    status: str
    pass_rate: float
    total_tests: int
    passed_count: int
    failed_count: int
    failed_tests: list[dict]


class DORAMetrics(msgspec.Struct):
    lead_time_hours: float
    deployment_frequency_per_day: float
    change_failure_rate_pct: float
    mttr_hours: float


class GenerateTestCaseRequest(msgspec.Struct):
    suite_id: UUID
    user_story: str


class GeneratedTestCaseStep(msgspec.Struct):
    step: str
    expected: str


class GeneratedTestCase(msgspec.Struct):
    title: str
    preconditions: str
    steps: list[GeneratedTestCaseStep]


class RerunResponse(msgspec.Struct):
    new_run_id: str
    rerun_count: int
    status: str


class FlakyTestInfo(msgspec.Struct):
    test_case_id: UUID
    title: str
    transitions: int
    total_runs: int
    flaky_score: float
    last_statuses: list[str]


class FlakyTestsResponse(msgspec.Struct):
    flaky_tests: list[FlakyTestInfo]
    total_count: int


class TestCaseDiffItem(msgspec.Struct):
    test_case_id: UUID
    title: str
    status_before: Optional[str]
    status_after: Optional[str]


class RunDiffResponse(msgspec.Struct):
    base_run_id: UUID
    compare_run_id: UUID
    added: list[TestCaseDiffItem]
    removed: list[TestCaseDiffItem]
    changed: list[TestCaseDiffItem]
    unchanged_count: int
    summary: dict


class RiskFactorDetail(msgspec.Struct):
    test_case_id: UUID
    title: str
    category: Optional[str]
    weight: float


class RiskScoreResponse(msgspec.Struct):
    run_id: UUID
    score: int
    risk_level: str
    recommendation: str
    total_tests: int
    passed_count: int
    failed_count: int
    skipped_count: int
    factors: list[RiskFactorDetail]


class DeployTriggerRequest(msgspec.Struct):
    """Request body for triggering a deployment."""
    environment: str = "preprod"  # preprod or prod
    approve: bool = False


class ScheduleCreate(msgspec.Struct):
    suite_id: UUID
    name: str
    cron_expression: str
    triggered_by: UUID
    timezone: str = "UTC"


class ScheduleResponse(msgspec.Struct):
    id: UUID
    suite_id: UUID
    name: str
    cron_expression: str
    timezone: str
    is_active: bool
    created_at: str


class ScheduleUpdate(msgspec.Struct):
    name: Optional[str] = None
    cron_expression: Optional[str] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None
