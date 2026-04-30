"""Defects controller - CRUD for defects."""

import logging
from uuid import UUID

from litestar import Controller, get, post, put
from litestar.di import Provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Defect
from app.repositories.base import BaseRepository
from app.schemas.schemas import DefectCreate, DefectResponse, DefectUpdate

logger = logging.getLogger(__name__)


async def provide_defect_repo(db_session: AsyncSession) -> BaseRepository[Defect]:
    return BaseRepository(db_session, Defect)


class DefectsController(Controller):
    """CRUD operations for defects."""

    path = "/api/v1/defects"
    tags = ["Defects"]
    dependencies = {"repo": Provide(provide_defect_repo)}

    @get()
    async def list_defects(self, repo: BaseRepository[Defect]) -> list[DefectResponse]:
        defects = await repo.list_all(limit=1000)
        return [
            DefectResponse(
                id=d.id,
                title=d.title,
                severity=d.severity,
                status=d.status,
                jira_key=d.jira_key,
                created_at=d.created_at.isoformat() if d.created_at else "",
            )
            for d in defects
        ]

    @get("/{defect_id:uuid}")
    async def get_defect(
        self, defect_id: UUID, repo: BaseRepository[Defect]
    ) -> DefectResponse:
        defect = await repo.get(defect_id)
        if defect is None:
            raise ValueError(f"Defect {defect_id} not found")
        return DefectResponse(
            id=defect.id,
            title=defect.title,
            severity=defect.severity,
            status=defect.status,
            jira_key=defect.jira_key,
            created_at=defect.created_at.isoformat() if defect.created_at else "",
        )

    @post()
    async def create_defect(
        self, data: DefectCreate, repo: BaseRepository[Defect]
    ) -> DefectResponse:
        defect = Defect(
            title=data.title,
            description=data.description,
            severity=data.severity,
            jira_key=data.jira_key,
        )
        saved = await repo.save(defect)

        # After saving defect, try to auto-create Jira issue if not already provided
        if not saved.jira_key:
            try:
                from app.services.jira_integration import JiraService, map_severity_to_jira

                jira = JiraService()
                jira_key = await jira.create_bug(
                    project_key="AST",
                    summary=saved.title,
                    description=saved.description or "",
                    priority_name=map_severity_to_jira(saved.severity),
                )
                if jira_key:
                    saved.jira_key = jira_key
                    saved = await repo.save(saved)
            except Exception as e:
                logger.warning(f"Failed to create Jira issue for defect {saved.id}: {e}")

        return DefectResponse(
            id=saved.id,
            title=saved.title,
            severity=saved.severity,
            status=saved.status,
            jira_key=saved.jira_key,
            created_at=saved.created_at.isoformat() if saved.created_at else "",
        )

    @put("/{defect_id:uuid}")
    async def update_defect(
        self,
        defect_id: UUID,
        data: DefectUpdate,
        repo: BaseRepository[Defect],
    ) -> DefectResponse:
        defect = await repo.get(defect_id)
        if defect is None:
            raise ValueError(f"Defect {defect_id} not found")
        if data.title is not None:
            defect.title = data.title
        if data.description is not None:
            defect.description = data.description
        if data.severity is not None:
            defect.severity = data.severity
        if data.status is not None:
            defect.status = data.status
        if data.jira_key is not None:
            defect.jira_key = data.jira_key
        saved = await repo.save(defect)
        return DefectResponse(
            id=saved.id,
            title=saved.title,
            severity=saved.severity,
            status=saved.status,
            jira_key=saved.jira_key,
            created_at=saved.created_at.isoformat() if saved.created_at else "",
        )
