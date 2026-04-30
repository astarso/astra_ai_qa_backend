import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import TestCase, TestResult, TestRun
from app.repositories.test_runs import TestRunRepository


logger = logging.getLogger(__name__)


@dataclass
class RunRequest:
    suite_id: UUID
    commit_sha: str
    branch: str
    triggered_by: UUID
    priority: int
    environment: str


@dataclass
class TestShard:
    shard_id: int
    cases: list[TestCase]


class MockTaskBus:
    async def schedule_shard(self, run_id: UUID, shard: TestShard) -> None:
        logger.info(f"[MOCK] Would schedule shard {shard.shard_id} for run {run_id}")

    async def schedule_analysis(self, run_id: UUID) -> None:
        logger.info(f"[MOCK] Would schedule analysis for run {run_id}")


class TaskiqAdapter:
    def __init__(self) -> None:
        from app.tasks.tasks import run_suite_shard, analyze_run_failures
        self._run_suite_shard = run_suite_shard
        self._analyze_run_failures = analyze_run_failures

    async def schedule_shard(self, run_id: UUID, shard: TestShard) -> None:
        case_ids = [str(c.id) for c in shard.cases]
        await self._run_suite_shard.kiq(str(run_id), shard.shard_id, case_ids)
        logger.info(f"Scheduled shard {shard.shard_id} for run {run_id} via Taskiq")

    async def schedule_analysis(self, run_id: UUID) -> None:
        await self._analyze_run_failures.kiq(str(run_id))
        logger.info(f"Scheduled analysis for run {run_id} via Taskiq")


def _create_task_bus() -> MockTaskBus | TaskiqAdapter:
    try:
        return TaskiqAdapter()
    except Exception:
        logger.warning("Taskiq broker unavailable, using MockTaskBus")
        return MockTaskBus()


class OrchestrationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = TestRunRepository(session)
        self._task_bus = _create_task_bus()

    async def create_run(self, request: RunRequest) -> TestRun:
        suite = await self._repo.get_suite(request.suite_id)
        if suite is None:
            raise ValueError(f"Suite {request.suite_id} not found")

        run = TestRun(
            suite_id=request.suite_id,
            commit_sha=request.commit_sha,
            branch=request.branch,
            triggered_by=request.triggered_by,
            priority=request.priority,
            environment=request.environment,
            status="pending",
        )

        saved_run = await self._repo.save(run)
        logger.info(f"Created test run {saved_run.id} for suite {request.suite_id}")

        cases = await self._repo.list_cases_for_suite(request.suite_id)
        shards = self._split_by_lpt(cases, len(cases))

        for shard in shards:
            await self._task_bus.schedule_shard(saved_run.id, shard)

        saved_run.started_at = datetime.utcnow()
        saved_run.status = "running"
        await self._repo.save(saved_run)

        return saved_run

    def _split_by_lpt(self, cases: list[TestCase], shard_count: int) -> list[TestShard]:
        if not cases:
            return []
        if shard_count <= 0:
            shard_count = 1

        sorted_cases = sorted(
            cases, key=lambda c: c.avg_duration_ms or 0, reverse=True
        )

        shards: list[list[TestCase]] = [[] for _ in range(shard_count)]
        shard_totals: list[float] = [0.0] * shard_count

        for case in sorted_cases:
            min_idx = shard_totals.index(min(shard_totals))
            shards[min_idx].append(case)
            shard_totals[min_idx] += case.avg_duration_ms or 0

        return [
            TestShard(shard_id=i, cases=shards[i])
            for i in range(shard_count)
            if shards[i]
        ]

    async def handle_result(self, run_id: UUID, results: list[dict]) -> None:
        for r in results:
            result = TestResult(
                run_id=run_id,
                test_case_id=r["test_case_id"],
                status=r["status"],
                duration_ms=r.get("duration_ms"),
                error_message=r.get("error_message"),
                stack_trace=r.get("stack_trace"),
                stdout=r.get("stdout"),
                stderr=r.get("stderr"),
                finished_at=datetime.utcnow(),
            )
            await self._repo.save_result(result)

        await self._recompute_run_status(run_id)

    async def _recompute_run_status(self, run_id: UUID) -> None:
        statuses = await self._repo.collect_statuses(run_id)

        if not statuses:
            return

        if all(s == "passed" for s in statuses):
            final_status = "passed"
        elif any(s == "failed" for s in statuses):
            final_status = "failed"
        elif all(s in ("passed", "skipped") for s in statuses):
            final_status = "passed"
        else:
            final_status = "running"

        await self._repo.update_run_status(run_id, final_status)

        if final_status in ("passed", "failed"):
            run = await self._repo.get(run_id)
            if run:
                run.finished_at = datetime.utcnow()
                await self._repo.save(run)

        # Send notification on run completion with failures
        if final_status == "failed" and run:
            try:
                from app.services.notifications import NotificationService

                notifier = NotificationService()  # Uses None backend by default
                await notifier.notify(
                    f"⚠️ Test run {run_id} FAILED. Commit: {run.commit_sha}, Branch: {run.branch}",
                )
            except Exception:
                logger.warning(f"Failed to send notification for run {run_id}")

            try:
                await self._task_bus.schedule_analysis(run_id)
            except Exception:
                logger.warning(f"Failed to schedule analysis for run {run_id}")

    async def rerun_failed(self, run_id: UUID) -> TestRun:
        stmt = (
            select(TestResult)
            .where(
                TestResult.run_id == run_id,
                TestResult.status == "failed",
            )
            .options(selectinload(TestResult.test_case))
        )
        result = await self._session.execute(stmt)
        failed_results = list(result.scalars().all())

        if not failed_results:
            raise ValueError(f"No failed results found for run {run_id}")

        original_run = await self._repo.get(run_id)
        if original_run is None:
            raise ValueError(f"Test run {run_id} not found")

        new_run = TestRun(
            suite_id=original_run.suite_id,
            commit_sha=original_run.commit_sha,
            branch=original_run.branch,
            triggered_by=original_run.triggered_by,
            priority=original_run.priority,
            environment=original_run.environment,
            status="pending",
        )
        saved = await self._repo.save(new_run)

        failed_cases = [r.test_case for r in failed_results if r.test_case]
        if failed_cases:
            shard = TestShard(shard_id=0, cases=failed_cases)
            try:
                await self._task_bus.schedule_shard(saved.id, shard)
            except Exception as exc:
                logger.warning("Could not schedule shard for rerun %s: %s", saved.id, exc)

        saved.started_at = datetime.utcnow()
        saved.status = "running"
        await self._repo.save(saved)

        return saved