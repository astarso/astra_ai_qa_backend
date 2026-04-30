"""Analytics controller for DORA metrics."""

from uuid import UUID

from litestar import Controller, get
from litestar.di import Provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.schemas import DORAMetrics, FlakyTestsResponse
from app.services.analytics import AnalyticsService


async def provide_analytics(db_session: AsyncSession) -> AnalyticsService:
    return AnalyticsService(db_session)


class AnalyticsController(Controller):
    path = "/api/v1/analytics"
    tags = ["Analytics"]
    dependencies = {"analytics": Provide(provide_analytics)}

    @get("/dora")
    async def get_dora_metrics(
        self,
        analytics: AnalyticsService,
        project_id: UUID | None = None,
        days: int = 30,
    ) -> DORAMetrics:
        metrics = await analytics.calculate_dora(project_id=project_id, days=days)
        return DORAMetrics(**metrics)

    @get("/flaky")
    async def get_flaky_tests(
        self,
        analytics: AnalyticsService,
        project_id: UUID | None = None,
        suite_id: UUID | None = None,
        threshold: int = 3,
        lookback: int = 30,
    ) -> FlakyTestsResponse:
        from app.schemas.schemas import FlakyTestInfo
        flaky = await analytics.detect_flaky_tests(project_id=project_id, suite_id=suite_id, threshold=threshold, lookback=lookback)
        return FlakyTestsResponse(flaky_tests=[FlakyTestInfo(**f) for f in flaky], total_count=len(flaky))