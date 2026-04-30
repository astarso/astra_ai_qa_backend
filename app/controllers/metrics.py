from litestar import get
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import TestRun, TestResult


@get("/metrics", exclude_from_auth=True, media_type="text/plain")
async def metrics_handler(db_session: AsyncSession) -> str:
    total_runs = await db_session.scalar(select(func.count(TestRun.id))) or 0

    failed_runs = await db_session.scalar(
        select(func.count(TestRun.id)).where(TestRun.status == "failed")
    ) or 0

    passed_results = await db_session.scalar(
        select(func.count(TestResult.id)).where(TestResult.status == "passed")
    ) or 0

    failed_results = await db_session.scalar(
        select(func.count(TestResult.id)).where(TestResult.status == "failed")
    ) or 0

    skipped_results = await db_session.scalar(
        select(func.count(TestResult.id)).where(TestResult.status == "skipped")
    ) or 0

    avg_duration_result = await db_session.scalar(
        select(func.avg(
            func.extract('epoch', TestRun.finished_at) -
            func.extract('epoch', TestRun.started_at)
        )).where(
            TestRun.finished_at.isnot(None),
            TestRun.started_at.isnot(None)
        )
    ) or 0.0

    lines = [
        "# HELP astra_test_runs_total Total number of test runs",
        "# TYPE astra_test_runs_total counter",
        f"astra_test_runs_total {total_runs}",
        "",
        "# HELP astra_test_runs_failed_total Total number of failed test runs",
        "# TYPE astra_test_runs_failed_total counter",
        f"astra_test_runs_failed_total {failed_runs}",
        "",
        "# HELP astra_test_results_total Total number of test results by status",
        "# TYPE astra_test_results_total counter",
        f"astra_test_results_total{{status=\"passed\"}} {passed_results}",
        f"astra_test_results_total{{status=\"failed\"}} {failed_results}",
        f"astra_test_results_total{{status=\"skipped\"}} {skipped_results}",
        "",
        "# HELP astra_test_run_duration_seconds Average duration of test runs in seconds",
        "# TYPE astra_test_run_duration_seconds gauge",
        f"astra_test_run_duration_seconds {avg_duration_result:.3f}",
    ]

    return "\n".join(lines) + "\n"