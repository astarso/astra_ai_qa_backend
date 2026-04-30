# ПРИЛОЖЕНИЯ

## ПРИЛОЖЕНИЕ А

**Листинг ключевых программных модулей разрабатываемой платформы**

А.1. Основной файл запуска приложения (`backend/app/main.py`)

```python
from litestar import Litestar, get
from litestar.di import Provide
from litestar.config.cors import CORSConfig
from litestar.logging import LoggingConfig
from litestar.openapi import OpenAPIConfig
from litestar.plugins.sqlalchemy import SQLAlchemyPlugin

from app.config import settings
from app.auth.sso import sso_auth_guard, oidc_login_handler
from app.controllers import (
    ProjectsController,
    TestCasesController,
    TestRunsController,
    DefectsController,
    AdminController,
)
from app.services.orchestration import OrchestrationService
from app.services.ai_analyzer import AIAnalyzerService
from app.services.report_generator import ReportGeneratorService
from app.db import provide_db_session, engine


logging_config = LoggingConfig(
    root={"level": "INFO", "handlers": ["queue_listener"]},
    formatters={
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        }
    },
)


@get("/api/v1/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


def create_app() -> Litestar:
    return Litestar(
        route_handlers=[
            healthcheck,
            oidc_login_handler,
            ProjectsController,
            TestCasesController,
            TestRunsController,
            DefectsController,
            AdminController,
        ],
        dependencies={
            "db_session": Provide(provide_db_session),
            "orchestrator": Provide(OrchestrationService),
            "ai_analyzer": Provide(AIAnalyzerService),
            "report_generator": Provide(ReportGeneratorService),
        },
        plugins=[SQLAlchemyPlugin(engine=engine)],
        cors_config=CORSConfig(allow_origins=settings.cors_origins),
        openapi_config=OpenAPIConfig(
            title="Astra CI-Test Platform",
            version="1.0.0",
            description="API платформы непрерывного тестирования и верификации ПО",
        ),
        logging_config=logging_config,
        guards=[sso_auth_guard],
        debug=settings.debug,
    )


app = create_app()
```

А.2. Конфигурация через pydantic-settings (`backend/app/config.py`)

```python
from functools import lru_cache
from pydantic import Field, SecretStr, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_")

    service_name: str = "astra-ci-test"
    debug: bool = False

    database_url: PostgresDsn
    redis_url: str = "redis://redis:6379/0"
    rabbitmq_url: str = "amqp://guest:guest@rabbit:5672/"
    opensearch_url: str = "http://opensearch:9200"
    minio_endpoint: str = "minio:9000"
    minio_access_key: SecretStr
    minio_secret_key: SecretStr

    oidc_issuer_url: str
    oidc_client_id: str
    oidc_client_secret: SecretStr

    llm_provider: str = "yandex_gpt"
    llm_api_key: SecretStr
    llm_model_name: str = "yandexgpt/latest"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 1024
    llm_request_timeout_seconds: int = 30

    cors_origins: list[str] = Field(default_factory=lambda: ["https://qa.astra.local"])

    jira_base_url: str = "https://jira.astra.local"
    jira_token: SecretStr
    gitlab_base_url: str = "https://gitlab.astra.local"
    gitlab_token: SecretStr


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
```

А.3. Сервис оркестрации прогонов (`backend/app/services/orchestration.py`)

```python
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TestRun, TestSuite, TestResult, TestRunStatus
from app.queue import task_bus
from app.repositories.test_runs import TestRunRepository


@dataclass(frozen=True, slots=True)
class RunRequest:
    suite_id: uuid.UUID
    commit_sha: str
    branch: str
    triggered_by: str
    priority: int = 3
    environment: str = "dev"


class OrchestrationService:
    def __init__(self, db_session: AsyncSession) -> None:
        self._repo = TestRunRepository(db_session)
        self._session = db_session

    async def create_run(self, request: RunRequest) -> TestRun:
        suite = await self._repo.get_suite(request.suite_id)
        if suite is None:
            raise ValueError(f"Suite {request.suite_id} not found")

        run = TestRun(
            id=uuid.uuid4(),
            suite_id=request.suite_id,
            commit_sha=request.commit_sha,
            branch=request.branch,
            triggered_by=request.triggered_by,
            priority=request.priority,
            environment=request.environment,
            status=TestRunStatus.PENDING,
            started_at=datetime.now(tz=timezone.utc),
        )
        await self._repo.save(run)
        await self._schedule_shards(run, suite)
        return run

    async def _schedule_shards(self, run: TestRun, suite: TestSuite) -> None:
        test_cases = await self._repo.list_cases_for_suite(suite.id)
        shard_count = min(max(1, len(test_cases) // 75), 16)
        shards = self._split_by_lpt(test_cases, shard_count)

        for idx, shard in enumerate(shards):
            await task_bus.enqueue(
                "run_suite_shard",
                payload={
                    "run_id": str(run.id),
                    "shard_index": idx,
                    "test_case_ids": [str(tc.id) for tc in shard],
                    "priority": run.priority,
                },
                priority=run.priority,
            )

    @staticmethod
    def _split_by_lpt(cases, shard_count):
        sorted_cases = sorted(
            cases, key=lambda tc: tc.avg_duration_ms or 0, reverse=True
        )
        shards = [[] for _ in range(shard_count)]
        loads = [0] * shard_count
        for case in sorted_cases:
            idx = loads.index(min(loads))
            shards[idx].append(case)
            loads[idx] += case.avg_duration_ms or 1_000
        return shards

    async def handle_result(
        self, run_id: uuid.UUID, results: list[dict]
    ) -> None:
        for item in results:
            await self._repo.save_result(
                TestResult(
                    id=uuid.uuid4(),
                    run_id=run_id,
                    test_case_id=uuid.UUID(item["test_case_id"]),
                    status=item["status"],
                    duration_ms=item.get("duration_ms", 0),
                    error_message=item.get("error_message"),
                )
            )
        await self._recompute_run_status(run_id)

    async def _recompute_run_status(self, run_id: uuid.UUID) -> None:
        statuses = await self._repo.collect_statuses(run_id)
        if "running" in statuses or "pending" in statuses:
            return
        final = "failed" if "failed" in statuses else "passed"
        await self._repo.update_run_status(run_id, final)
        if final == "failed":
            await task_bus.enqueue(
                "analyze_run_failures",
                payload={"run_id": str(run_id)},
                priority=1,
            )
```

А.4. Сервис AI-анализа падений (`backend/app/services/ai_analyzer.py`)

```python
import asyncio
import hashlib
import json
import logging
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_community.chat_models import ChatYandexGPT
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AIAnalysis, TestResult
from app.repositories.ai import AIRepository
from app.services.embeddings import EmbeddingService
from app.services.sanitizer import Sanitizer

logger = logging.getLogger(__name__)


class AIAnalysisSchema(BaseModel):
    category: str = Field(pattern="^(real_defect|flaky|infrastructure)$")
    probability: float = Field(ge=0.0, le=1.0)
    short_cause: str = Field(max_length=300)
    next_steps: list[str] = Field(min_length=1, max_length=6)


PROMPT_TEMPLATE = """Ты — senior QA-инженер «Группы Астра». Проанализируй ошибку автотеста и
верни строго JSON без дополнительных комментариев со следующими полями:
- category: одно из "real_defect", "flaky", "infrastructure"
- probability: число от 0 до 1 (уверенность)
- short_cause: краткое описание причины до 300 символов
- next_steps: список 1-6 шагов для устранения

Текст ошибки:
{error_text}

Последние 50 строк stdout:
{stdout_tail}

Стек-трейс:
{stack_trace}
"""


class AIAnalyzerService:
    def __init__(self, db_session: AsyncSession) -> None:
        self._repo = AIRepository(db_session)
        self._embeddings = EmbeddingService()
        self._sanitizer = Sanitizer()
        self._llm = ChatYandexGPT(
            api_key=settings.llm_api_key.get_secret_value(),
            model_name=settings.llm_model_name,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            timeout=settings.llm_request_timeout_seconds,
        )
        prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
        self._chain = prompt | self._llm | JsonOutputParser()

    async def analyze(self, result: TestResult) -> AIAnalysis:
        similar = await self._find_similar(result)
        if similar is not None:
            return await self._as_duplicate(result, similar)

        payload = self._sanitizer.clean(
            {
                "error_text": result.error_message or "",
                "stdout_tail": "\n".join((result.stdout or "").splitlines()[-50:]),
                "stack_trace": result.stack_trace or "",
            }
        )
        data = await self._ask_with_retries(payload)
        prompt_hash = self._prompt_hash(payload)
        analysis = AIAnalysis(
            id=None,
            result_id=result.id,
            category=data["category"],
            probability=data["probability"],
            short_cause=data["short_cause"],
            suggestion=json.dumps(data["next_steps"], ensure_ascii=False),
            llm_model=settings.llm_model_name,
            prompt_hash=prompt_hash,
        )
        await self._repo.save(analysis)
        return analysis

    async def _ask_with_retries(self, payload: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                raw = await self._chain.ainvoke(payload)
                return AIAnalysisSchema(**raw).model_dump()
            except (ValidationError, ValueError) as exc:
                last_error = exc
                await asyncio.sleep(1 + attempt)
        logger.error("LLM analysis failed after 3 attempts", exc_info=last_error)
        return {
            "category": "infrastructure",
            "probability": 0.1,
            "short_cause": "Не удалось распознать причину автоматически",
            "next_steps": ["Передайте падение на ручной анализ QA-лиду"],
        }

    async def _find_similar(self, result: TestResult):
        if not result.error_message:
            return None
        vector = await self._embeddings.encode(result.error_message)
        return await self._repo.find_nearest(vector, threshold=0.92)

    async def _as_duplicate(self, result, similar) -> AIAnalysis:
        analysis = AIAnalysis(
            id=None,
            result_id=result.id,
            category=similar.category,
            probability=similar.probability,
            short_cause=f"Дубликат {similar.id}: {similar.short_cause}",
            suggestion=similar.suggestion,
            llm_model="duplicate-match",
            prompt_hash=similar.prompt_hash,
        )
        return await self._repo.save(analysis)

    @staticmethod
    def _prompt_hash(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()
```

А.5. Контроллер управления прогонами (`backend/app/controllers/test_runs.py`)

```python
import uuid
from litestar import Controller, get, post
from litestar.params import Body
from msgspec import Struct, field
from typing import Annotated

from app.services.orchestration import OrchestrationService, RunRequest


class CreateRunPayload(Struct):
    suite_id: uuid.UUID
    commit_sha: str
    branch: str
    triggered_by: str
    priority: int = field(default=3)
    environment: str = field(default="dev")


class TestRunDTO(Struct):
    id: uuid.UUID
    suite_id: uuid.UUID
    status: str
    started_at: str
    finished_at: str | None
    pass_count: int
    fail_count: int
    skipped_count: int


class TestRunsController(Controller):
    path = "/api/v1/runs"
    tags = ["Test Runs"]

    @post()
    async def create_run(
        self,
        data: Annotated[CreateRunPayload, Body()],
        orchestrator: OrchestrationService,
    ) -> TestRunDTO:
        run = await orchestrator.create_run(
            RunRequest(
                suite_id=data.suite_id,
                commit_sha=data.commit_sha,
                branch=data.branch,
                triggered_by=data.triggered_by,
                priority=data.priority,
                environment=data.environment,
            )
        )
        return TestRunDTO(
            id=run.id,
            suite_id=run.suite_id,
            status=run.status.value,
            started_at=run.started_at.isoformat(),
            finished_at=None,
            pass_count=0,
            fail_count=0,
            skipped_count=0,
        )

    @get("/{run_id:uuid}")
    async def get_run(
        self,
        run_id: uuid.UUID,
        orchestrator: OrchestrationService,
    ) -> TestRunDTO:
        run = await orchestrator._repo.get_with_stats(run_id)
        return TestRunDTO(
            id=run.id,
            suite_id=run.suite_id,
            status=run.status.value,
            started_at=run.started_at.isoformat(),
            finished_at=run.finished_at.isoformat() if run.finished_at else None,
            pass_count=run.pass_count,
            fail_count=run.fail_count,
            skipped_count=run.skipped_count,
        )
```

А.6. Основной компонент фронтенда (`frontend/src/App.tsx`)

```tsx
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConfigProvider } from "antd";
import ruRU from "antd/locale/ru_RU";

import { AuthGuard } from "./auth/AuthGuard";
import { MainLayout } from "./layout/MainLayout";
import { DashboardPage } from "./pages/DashboardPage";
import { ProjectPage } from "./pages/ProjectPage";
import { TestRunPage } from "./pages/TestRunPage";
import { TestResultPage } from "./pages/TestResultPage";
import { TestCaseEditorPage } from "./pages/TestCaseEditorPage";
import { ReleaseReportPage } from "./pages/ReleaseReportPage";
import { AdminPage } from "./pages/AdminPage";
import { LoginPage } from "./pages/LoginPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchInterval: 15_000, staleTime: 10_000, retry: 2 },
  },
});

export default function App(): JSX.Element {
  return (
    <ConfigProvider locale={ruRU}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/"
              element={
                <AuthGuard>
                  <MainLayout />
                </AuthGuard>
              }
            >
              <Route index element={<DashboardPage />} />
              <Route path="projects/:projectId" element={<ProjectPage />} />
              <Route path="projects/:projectId/runs/:runId" element={<TestRunPage />} />
              <Route path="results/:resultId" element={<TestResultPage />} />
              <Route path="cases/:caseId" element={<TestCaseEditorPage />} />
              <Route path="release-reports/:reportId" element={<ReleaseReportPage />} />
              <Route path="admin" element={<AdminPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </ConfigProvider>
  );
}
```

А.7. Компонент отображения AI-рекомендации (`frontend/src/components/AIRecommendation.tsx`)

```tsx
import { Card, Tag, Typography, List, Button, Space, Skeleton } from "antd";
import { useQuery } from "@tanstack/react-query";
import { fetchAIAnalysis } from "../api/ai";

const { Title, Paragraph } = Typography;

const CATEGORY_COLOR: Record<string, string> = {
  real_defect: "red",
  flaky: "gold",
  infrastructure: "blue",
};

const CATEGORY_LABEL: Record<string, string> = {
  real_defect: "Реальный дефект",
  flaky: "Нестабильный (flaky)",
  infrastructure: "Инфраструктура",
};

export function AIRecommendation({ resultId }: { resultId: string }): JSX.Element {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["ai-analysis", resultId],
    queryFn: () => fetchAIAnalysis(resultId),
  });

  if (isLoading) return <Skeleton active paragraph={{ rows: 4 }} />;
  if (isError || !data) {
    return (
      <Card title="AI-ассистент">
        <Paragraph type="secondary">Не удалось получить рекомендацию.</Paragraph>
        <Button onClick={() => refetch()}>Повторить</Button>
      </Card>
    );
  }

  const steps: string[] = JSON.parse(data.suggestion ?? "[]");

  return (
    <Card
      title={
        <Space>
          <span>AI-ассистент</span>
          <Tag color={CATEGORY_COLOR[data.category]}>
            {CATEGORY_LABEL[data.category]}
          </Tag>
          <Tag>уверенность {(data.probability * 100).toFixed(0)}%</Tag>
        </Space>
      }
    >
      <Title level={5}>Вероятная причина</Title>
      <Paragraph>{data.short_cause}</Paragraph>

      <Title level={5}>Рекомендуемые действия</Title>
      <List
        size="small"
        bordered
        dataSource={steps}
        renderItem={(item, idx) => (
          <List.Item>{idx + 1}. {item}</List.Item>
        )}
      />
    </Card>
  );
}
```

А.8. Воркер запуска автотестов (`worker/run_shard.py`)

```python
import asyncio
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path

import aio_pika
import httpx
from junitparser import JUnitXml

API_BASE = os.environ["APP_API_BASE"]
SERVICE_TOKEN = os.environ["APP_SERVICE_TOKEN"]
AMQP_URL = os.environ["APP_RABBITMQ_URL"]


async def handle_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    async with message.process(requeue=False):
        payload = json.loads(message.body)
        run_id = payload["run_id"]
        case_ids = payload["test_case_ids"]
        logging.info("Starting shard run_id=%s, %s cases", run_id, len(case_ids))
        results = await execute_cases(case_ids)
        await submit_results(run_id, results)


async def execute_cases(case_ids: list[str]) -> list[dict]:
    with tempfile.TemporaryDirectory() as tmpdir:
        xml_path = Path(tmpdir) / "report.xml"
        cmd = [
            "pytest",
            "--junitxml",
            str(xml_path),
            "-k",
            " or ".join(case_ids),
            "--tb=short",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3_600)
        return parse_junit_xml(xml_path, proc.stdout, proc.stderr)


def parse_junit_xml(path: Path, stdout: str, stderr: str) -> list[dict]:
    if not path.exists():
        return []
    results: list[dict] = []
    xml = JUnitXml.fromfile(str(path))
    for suite in xml:
        for case in suite:
            status = "passed"
            error_message: str | None = None
            for failure in case.result:
                status = "failed"
                error_message = str(failure.message)
            results.append(
                {
                    "test_case_id": case.name,
                    "status": status,
                    "duration_ms": int((case.time or 0.0) * 1_000),
                    "error_message": error_message,
                    "stdout": stdout[-8_000:],
                    "stderr": stderr[-8_000:],
                }
            )
    return results


async def submit_results(run_id: str, results: list[dict]) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{API_BASE}/api/v1/runs/{run_id}/results",
            headers={"Authorization": f"Bearer {SERVICE_TOKEN}"},
            json={"results": results},
        )
        response.raise_for_status()


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    connection = await aio_pika.connect_robust(AMQP_URL)
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)
        queue = await channel.declare_queue("run_suite_shard", durable=True)
        async for message in queue:
            await handle_message(message)


if __name__ == "__main__":
    asyncio.run(main())
```

## ПРИЛОЖЕНИЕ Б

**Схема базы данных платформы в нотации DDL (PostgreSQL 15)**

```sql
-- Таблица пользователей и ролей
CREATE TABLE roles (
    id        SMALLSERIAL PRIMARY KEY,
    code      VARCHAR(32) NOT NULL UNIQUE,
    description VARCHAR(255) NOT NULL
);

CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       VARCHAR(255) NOT NULL UNIQUE,
    full_name   VARCHAR(255) NOT NULL,
    role_id     SMALLINT NOT NULL REFERENCES roles(id),
    ldap_dn     VARCHAR(512),
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Проекты и тест-наборы
CREATE TABLE projects (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code       VARCHAR(64) NOT NULL UNIQUE,
    name       VARCHAR(255) NOT NULL,
    owner_id   UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE test_suites (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name        VARCHAR(255) NOT NULL,
    kind        VARCHAR(32) NOT NULL,
    config      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Тест-кейсы
CREATE TABLE test_cases (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    suite_id          UUID NOT NULL REFERENCES test_suites(id),
    title             VARCHAR(512) NOT NULL,
    description       TEXT,
    source            VARCHAR(32) NOT NULL,
    code_path         VARCHAR(512),
    avg_duration_ms   INTEGER DEFAULT 0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Прогоны и результаты
CREATE TABLE test_runs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    suite_id      UUID NOT NULL REFERENCES test_suites(id),
    commit_sha    CHAR(40) NOT NULL,
    branch        VARCHAR(255) NOT NULL,
    triggered_by  VARCHAR(255) NOT NULL,
    priority      SMALLINT NOT NULL DEFAULT 3,
    environment   VARCHAR(32) NOT NULL DEFAULT 'dev',
    status        VARCHAR(32) NOT NULL DEFAULT 'pending',
    started_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at   TIMESTAMPTZ
);

CREATE INDEX idx_test_runs_suite_started
    ON test_runs(suite_id, started_at DESC);
CREATE INDEX idx_test_runs_commit ON test_runs(commit_sha);

CREATE TABLE test_results (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id        UUID NOT NULL REFERENCES test_runs(id) ON DELETE CASCADE,
    test_case_id  UUID NOT NULL REFERENCES test_cases(id),
    status        VARCHAR(32) NOT NULL,
    duration_ms   INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    stack_trace   TEXT,
    stdout        TEXT,
    stderr        TEXT,
    finished_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_results_run_status ON test_results(run_id, status);
CREATE INDEX idx_results_finished ON test_results USING brin(finished_at);

-- AI-анализ (с векторным индексом)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE ai_analyses (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    result_id         UUID NOT NULL REFERENCES test_results(id) ON DELETE CASCADE,
    category          VARCHAR(32) NOT NULL,
    probability       REAL NOT NULL,
    short_cause       VARCHAR(512) NOT NULL,
    suggestion        TEXT NOT NULL,
    llm_model         VARCHAR(128) NOT NULL,
    prompt_hash       CHAR(64) NOT NULL,
    error_embedding   VECTOR(768),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ai_analyses_result ON ai_analyses(result_id);
CREATE INDEX idx_ai_analyses_vec
    ON ai_analyses USING ivfflat (error_embedding vector_cosine_ops)
    WITH (lists = 100);

-- Дефекты
CREATE TABLE defects (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title        VARCHAR(512) NOT NULL,
    description  TEXT,
    severity     VARCHAR(16) NOT NULL,
    status       VARCHAR(32) NOT NULL DEFAULT 'new',
    jira_key     VARCHAR(64),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE defect_results (
    defect_id  UUID NOT NULL REFERENCES defects(id) ON DELETE CASCADE,
    result_id  UUID NOT NULL REFERENCES test_results(id) ON DELETE CASCADE,
    PRIMARY KEY (defect_id, result_id)
);
```

## ПРИЛОЖЕНИЕ В

**Пример CI-пайплайна GitLab для интеграции с платформой (`.gitlab-ci.yml`)**

```yaml
stages:
  - build
  - test
  - quality-gate
  - deploy

variables:
  ASTRA_CI_TEST_URL: "https://qa.astra.local/api/v1"
  IMAGE_REGISTRY: "harbor.astra.local/astra-linux"

build-image:
  stage: build
  image: docker:25
  services: [docker:25-dind]
  script:
    - docker build -t $IMAGE_REGISTRY/astra-linux:$CI_COMMIT_SHA .
    - docker push $IMAGE_REGISTRY/astra-linux:$CI_COMMIT_SHA

unit-tests:
  stage: test
  image: python:3.12-slim
  script:
    - pip install -r requirements.txt
    - pytest --junitxml=report.xml -q
  artifacts:
    reports:
      junit: report.xml

trigger-platform-run:
  stage: quality-gate
  image: curlimages/curl:8
  script: |
    RUN_ID=$(curl -sSf -X POST "$ASTRA_CI_TEST_URL/runs" \
      -H "Authorization: Bearer $ASTRA_CI_TEST_TOKEN" \
      -H "Content-Type: application/json" \
      -d "{
        \"suite_id\": \"$ASTRA_SUITE_ID\",
        \"commit_sha\": \"$CI_COMMIT_SHA\",
        \"branch\": \"$CI_COMMIT_BRANCH\",
        \"triggered_by\": \"$GITLAB_USER_LOGIN\",
        \"priority\": 1
      }" | jq -r .id)
    echo "run_id=$RUN_ID" > platform.env
  artifacts:
    reports:
      dotenv: platform.env

wait-for-platform:
  stage: quality-gate
  image: curlimages/curl:8
  needs: [trigger-platform-run]
  script: |
    for i in $(seq 1 120); do
      STATUS=$(curl -sSf "$ASTRA_CI_TEST_URL/runs/$run_id" \
        -H "Authorization: Bearer $ASTRA_CI_TEST_TOKEN" | jq -r .status)
      if [ "$STATUS" = "passed" ]; then exit 0; fi
      if [ "$STATUS" = "failed" ]; then exit 1; fi
      sleep 15
    done
    exit 1

deploy-to-stage:
  stage: deploy
  image: alpine/kubectl:1.29
  needs: [wait-for-platform]
  only: [main, /^release\//]
  script:
    - kubectl --context astra-stage set image deployment/astra-linux \
        astra-linux=$IMAGE_REGISTRY/astra-linux:$CI_COMMIT_SHA
    - kubectl --context astra-stage rollout status deployment/astra-linux
```

## ПРИЛОЖЕНИЕ Г

**Таблица Г.1. Соответствие функциональных требований платформы и разделов ВКР**

| Требование | Источник | Раздел реализации |
|---|---|---|
| F1. Управление проектами и тест-наборами | ТЗ, пункт 3.1 | 2.3.4; приложение А.5 |
| F2. Управление тест-кейсами | ТЗ, пункт 3.2 | 2.3.4 |
| F3. Оркестрация автотестов | ТЗ, пункт 3.3 | 2.3.4; приложение А.3, А.8 |
| F4. Анализ результатов | ТЗ, пункт 3.4 | 2.3.4; приложение А.4 |
| F5. Управление дефектами | ТЗ, пункт 3.5 | 2.3.4 |
| F6. Доставка приложения (CD) | ТЗ, пункт 3.6 | 2.4; приложение В |
| F7. Отчётность и аналитика | ТЗ, пункт 3.7 | 2.2.3 |
| S1. Аутентификация и авторизация | ТЗ, пункт 4.1 | 2.1.3; приложение А.1 |
| S2. Администрирование | ТЗ, пункт 4.2 | 2.4 (экранная форма №8) |

**Таблица Г.2. Матрица покрытия целевых метрик DORA**

| Метрика DORA | Базовое значение (до) | Целевое (после) | Механизм в платформе |
|---|---|---|---|
| Lead Time for Changes | 4,2 дня | 2,3 дня | Автозапуск тестов по push, AI-приоритизация |
| Deployment Frequency | 1,5 релиза/неделю | 3,0 релиза/неделю | Ускорение QA-цикла, автоматический релизный отчёт |
| Change Failure Rate | 18 % | 11 % | AI-классификация падений, прогноз рисков |
| MTTR (Mean Time to Restore) | 8 часов | 3 часа | AI-рекомендации, база похожих падений |

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

# ПОСЛЕДНИЙ ЛИСТ ВКР

Выпускная квалификационная работа выполнена мной совершенно самостоятельно. Все использованные в работе материалы и концепции из опубликованной литературы и других источников имеют ссылки на них.

Выпускная квалификационная работа прошла проверку на корректность заимствования в системе «Антиплагиат.ВУЗ».

Настоящим подтверждаю, что даю разрешение Университету «Синергия» на размещение полного текста моей выпускной квалификационной работы и отзыва о работе в период ее подготовки в электронно-библиотечной системе Университета «Синергия».

| | | |
|---|---|---|
| Обучающийся | \_\_\_\_\_\_\_\_\_\_\_\_\_ | Старухин А. А. |
| | *(подпись)* | *(расшифровка)* |

«\_\_» \_\_\_\_\_\_\_\_\_\_\_ 2025 г.
