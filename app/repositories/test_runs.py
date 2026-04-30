from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.entities import TestCase, TestResult, TestRun, TestSuite
from app.repositories.base import BaseRepository


class TestRunRepository(BaseRepository[TestRun]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TestRun)

    async def get_with_stats(self, run_id: UUID) -> TestRun | None:
        run = await self.get(run_id)
        if run is None:
            return None

        stats_q = select(
            TestResult.status,
            func.count(TestResult.id).label("count"),
        ).where(TestResult.run_id == run_id).group_by(TestResult.status)

        result = await self._session.execute(stats_q)
        counts = {row.status: row.count for row in result}

        run._pass_count = counts.get("passed", 0)
        run._fail_count = counts.get("failed", 0)
        run._skipped_count = counts.get("skipped", 0)

        return run

    async def collect_statuses(self, run_id: UUID) -> list[str]:
        stmt = select(TestResult.status).where(TestResult.run_id == run_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_run_status(self, run_id: UUID, status: str) -> None:
        run = await self.get(run_id)
        if run:
            run.status = status
            await self._session.flush()

    async def save_result(self, result: TestResult) -> TestResult:
        self._session.add(result)
        await self._session.flush()
        await self._session.refresh(result)
        return result

    async def get_suite(self, suite_id: UUID) -> TestSuite | None:
        stmt = select(TestSuite).where(TestSuite.id == suite_id)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_cases_for_suite(self, suite_id: UUID) -> list[TestCase]:
        stmt = select(TestCase).where(TestCase.suite_id == suite_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_run_with_results(self, run_id: UUID) -> TestRun | None:
        stmt = (
            select(TestRun)
            .options(
                joinedload(TestRun.results).joinedload(TestResult.test_case),
                joinedload(TestRun.results).joinedload(TestResult.ai_analysis),
            )
            .where(TestRun.id == run_id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()
