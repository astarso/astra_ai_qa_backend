"""Analytics service for DORA metrics calculation."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import TestResult, TestCase, TestRun, TestSuite


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def calculate_dora(self, project_id: UUID | None = None, days: int = 30) -> dict:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        lead_time = await self._calc_lead_time(cutoff, project_id)
        deploy_freq = await self._calc_deployment_frequency(cutoff, days, project_id)
        cfr = await self._calc_change_failure_rate(cutoff, project_id)
        mttr = await self._calc_mttr(cutoff, project_id)

        return {
            "lead_time_hours": lead_time,
            "deployment_frequency_per_day": deploy_freq,
            "change_failure_rate_pct": cfr,
            "mttr_hours": mttr,
        }

    async def _calc_lead_time(self, cutoff: datetime, project_id: UUID | None = None) -> float:
        """Average time from started_at to finished_at for completed runs."""
        stmt = select(TestRun.started_at, TestRun.finished_at).where(
            TestRun.finished_at.isnot(None),
            TestRun.started_at.isnot(None),
            TestRun.finished_at >= cutoff,
        )
        if project_id:
            stmt = stmt.join(TestSuite, TestRun.suite_id == TestSuite.id).where(
                TestSuite.project_id == project_id
            )
        result = await self._session.execute(stmt)
        rows = result.all()
        if not rows:
            return 0.0
        hours = []
        for row in rows:
            delta = row.finished_at - row.started_at
            hours.append(delta.total_seconds() / 3600)
        return round(sum(hours) / len(hours), 2)

    async def _calc_deployment_frequency(self, cutoff: datetime, days: int, project_id: UUID | None = None) -> float:
        """Number of successful runs per day."""
        stmt = select(func.count(TestRun.id)).where(
            TestRun.status == "passed",
            TestRun.finished_at.isnot(None),
            TestRun.finished_at >= cutoff,
        )
        if project_id:
            stmt = stmt.join(TestSuite, TestRun.suite_id == TestSuite.id).where(
                TestSuite.project_id == project_id
            )
        result = await self._session.execute(stmt)
        count = result.scalar() or 0
        return round(count / max(days, 1), 2)

    async def _calc_change_failure_rate(self, cutoff: datetime, project_id: UUID | None = None) -> float:
        """Percentage of runs that failed."""
        total_stmt = select(func.count(TestRun.id)).where(
            TestRun.finished_at.isnot(None),
            TestRun.finished_at >= cutoff,
        )
        failed_stmt = select(func.count(TestRun.id)).where(
            TestRun.status == "failed",
            TestRun.finished_at.isnot(None),
            TestRun.finished_at >= cutoff,
        )
        if project_id:
            total_stmt = total_stmt.join(TestSuite, TestRun.suite_id == TestSuite.id).where(
                TestSuite.project_id == project_id
            )
            failed_stmt = failed_stmt.join(TestSuite, TestRun.suite_id == TestSuite.id).where(
                TestSuite.project_id == project_id
            )
        total_result = await self._session.execute(total_stmt)
        failed_result = await self._session.execute(failed_stmt)
        total = total_result.scalar() or 0
        failed = failed_result.scalar() or 0
        if total == 0:
            return 0.0
        return round(failed / total * 100, 2)

    async def _calc_mttr(self, cutoff: datetime, project_id: UUID | None = None) -> float:
        """Mean time to restore: average duration of failed runs."""
        stmt = select(TestRun.started_at, TestRun.finished_at).where(
            TestRun.status == "failed",
            TestRun.finished_at.isnot(None),
            TestRun.started_at.isnot(None),
            TestRun.finished_at >= cutoff,
        )
        if project_id:
            stmt = stmt.join(TestSuite, TestRun.suite_id == TestSuite.id).where(
                TestSuite.project_id == project_id
            )
        result = await self._session.execute(stmt)
        rows = result.all()
        if not rows:
            return 0.0
        hours = []
        for row in rows:
            delta = row.finished_at - row.started_at
            hours.append(delta.total_seconds() / 3600)
        return round(sum(hours) / len(hours), 2)

    async def detect_flaky_tests(
        self, project_id: UUID | None = None, suite_id: UUID | None = None, threshold: int = 3, lookback: int = 30
    ) -> list[dict]:
        """Detect flaky tests: tests whose status changed > threshold times in last N results."""
        stmt = (
            select(TestResult.test_case_id, TestResult.status, TestResult.finished_at, TestCase.title)
            .join(TestCase, TestResult.test_case_id == TestCase.id)
            .join(TestRun, TestResult.run_id == TestRun.id)
            .order_by(TestResult.test_case_id, TestResult.finished_at.desc())
        )
        if project_id:
            stmt = stmt.join(TestSuite, TestRun.suite_id == TestSuite.id).where(TestSuite.project_id == project_id)
        elif suite_id:
            stmt = stmt.join(TestSuite, TestRun.suite_id == TestSuite.id).where(TestSuite.id == suite_id)

        result = await self._session.execute(stmt)
        rows = result.all()

        # Group by test_case_id and take last `lookback` results
        from collections import OrderedDict
        grouped: dict[UUID, list] = OrderedDict()
        for row in rows:
            tc_id = row.test_case_id
            if tc_id not in grouped:
                grouped[tc_id] = []
            grouped[tc_id].append({"status": row.status, "finished_at": row.finished_at, "title": row.title})

        flaky = []
        for tc_id, results in grouped.items():
            last_n = results[:lookback]
            statuses = [r["status"] for r in last_n]
            transitions = sum(1 for i in range(1, len(statuses)) if statuses[i] != statuses[i - 1])
            if transitions > threshold:
                total_runs = len(last_n)
                flaky_score = transitions / max(total_runs - 1, 1)
                flaky.append({
                    "test_case_id": tc_id,
                    "title": last_n[0]["title"],
                    "transitions": transitions,
                    "total_runs": total_runs,
                    "flaky_score": round(flaky_score, 4),
                    "last_statuses": statuses,
                })

        return flaky