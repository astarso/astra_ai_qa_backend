"""Projects controller - CRUD for projects."""

from uuid import UUID

from litestar import Controller, get, post, put
from litestar.di import Provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import provide_db_session
from app.models.entities import Project
from app.repositories.base import BaseRepository
from app.schemas.schemas import ProjectCreate, ProjectResponse


async def provide_project_repo(db_session: AsyncSession) -> BaseRepository[Project]:
    return BaseRepository(db_session, Project)


class ProjectsController(Controller):
    """CRUD operations for projects."""

    path = "/api/v1/projects"
    tags = ["Projects"]
    dependencies = {"repo": Provide(provide_project_repo)}

    @get()
    async def list_projects(self, repo: BaseRepository[Project]) -> list[ProjectResponse]:
        projects = await repo.list_all(limit=1000)
        return [
            ProjectResponse(
                id=p.id,
                code=p.code,
                name=p.name,
                owner_id=p.owner_id,
                created_at=p.created_at.isoformat() if p.created_at else "",
            )
            for p in projects
        ]

    @get("/{project_id:uuid}")
    async def get_project(
        self, project_id: UUID, repo: BaseRepository[Project]
    ) -> ProjectResponse:
        project = await repo.get(project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")
        return ProjectResponse(
            id=project.id,
            code=project.code,
            name=project.name,
            owner_id=project.owner_id,
            created_at=project.created_at.isoformat() if project.created_at else "",
        )

    @post()
    async def create_project(
        self, data: ProjectCreate, repo: BaseRepository[Project]
    ) -> ProjectResponse:
        project = Project(
            code=data.code,
            name=data.name,
            owner_id=data.owner_id,
        )
        saved = await repo.save(project)
        return ProjectResponse(
            id=saved.id,
            code=saved.code,
            name=saved.name,
            owner_id=saved.owner_id,
            created_at=saved.created_at.isoformat() if saved.created_at else "",
        )
