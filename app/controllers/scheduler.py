"""Scheduler controller for managing test run schedules."""
from uuid import UUID

from litestar import Controller, delete, get, post, put
from litestar.di import Provide
from litestar.status_codes import HTTP_200_OK
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.schemas import ScheduleCreate, ScheduleResponse, ScheduleUpdate
from app.services.scheduler import ScheduleService


async def provide_scheduler(db_session: AsyncSession) -> ScheduleService:
    return ScheduleService()


class SchedulerController(Controller):
    path = "/api/v1/schedules"
    tags = ["Scheduler"]
    dependencies = {"scheduler": Provide(provide_scheduler)}

    @post()
    async def create_schedule(
        self,
        data: ScheduleCreate,
        scheduler: ScheduleService,
    ) -> ScheduleResponse:
        """Create a new schedule for recurring test runs."""
        result = await scheduler.create_schedule(
            suite_id=data.suite_id,
            name=data.name,
            cron_expression=data.cron_expression,
            triggered_by=data.triggered_by,
            timezone=data.timezone,
        )
        return ScheduleResponse(
            id=UUID(result["id"]),
            suite_id=UUID(result["suite_id"]),
            name=result["name"],
            cron_expression=result["cron_expression"],
            timezone=result["timezone"],
            is_active=result["is_active"],
            created_at=result.get("created_at", ""),
        )

    @get()
    async def list_schedules(
        self,
        scheduler: ScheduleService,
        suite_id: UUID | None = None,
    ) -> list[ScheduleResponse]:
        """List all schedules."""
        schedules = await scheduler.list_schedules(suite_id=suite_id)
        return [
            ScheduleResponse(
                id=UUID(s["id"]),
                suite_id=UUID(s["suite_id"]),
                name=s["name"],
                cron_expression=s["cron_expression"],
                timezone=s["timezone"],
                is_active=s["is_active"],
                created_at=s.get("created_at", ""),
            )
            for s in schedules
        ]

    @get("/{schedule_id:uuid}")
    async def get_schedule(
        self,
        schedule_id: UUID,
        scheduler: ScheduleService,
    ) -> ScheduleResponse:
        """Get a single schedule by ID."""
        result = await scheduler.get_schedule(schedule_id)
        if "message" in result and "stub" in result.get("status", ""):
            return ScheduleResponse(
                id=schedule_id,
                suite_id=schedule_id,
                name="stub",
                cron_expression="0 0 * * *",
                timezone="UTC",
                is_active=True,
                created_at="",
            )
        return ScheduleResponse(
            id=UUID(result["id"]),
            suite_id=UUID(result["suite_id"]),
            name=result["name"],
            cron_expression=result["cron_expression"],
            timezone=result["timezone"],
            is_active=result["is_active"],
            created_at=result.get("created_at", ""),
        )

    @put("/{schedule_id:uuid}")
    async def update_schedule(
        self,
        schedule_id: UUID,
        data: ScheduleUpdate,
        scheduler: ScheduleService,
    ) -> dict:
        """Update a schedule."""
        result = await scheduler.update_schedule(
            schedule_id=schedule_id,
            name=data.name,
            cron_expression=data.cron_expression,
            timezone=data.timezone,
            is_active=data.is_active,
        )
        return result

    @delete("/{schedule_id:uuid}", status_code=HTTP_200_OK)
    async def delete_schedule(
        self,
        schedule_id: UUID,
        scheduler: ScheduleService,
    ) -> dict:
        """Delete a schedule."""
        return await scheduler.delete_schedule(schedule_id)