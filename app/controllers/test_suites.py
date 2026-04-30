"""Test suites controller - CRUD for test suites."""

from uuid import UUID

from litestar import Controller, delete, get, post, put
from litestar.status_codes import HTTP_200_OK
from litestar.di import Provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import TestSuite
from app.repositories.base import BaseRepository
from app.schemas.schemas import TestSuiteCreate, TestSuiteResponse, TestSuiteUpdate


async def provide_test_suite_repo(db_session: AsyncSession) -> BaseRepository[TestSuite]:
    return BaseRepository(db_session, TestSuite)


class TestSuitesController(Controller):
    """CRUD operations for test suites."""

    path = "/api/v1/test-suites"
    tags = ["Test Suites"]
    dependencies = {"repo": Provide(provide_test_suite_repo)}

    @get()
    async def list_test_suites(self, repo: BaseRepository[TestSuite]) -> list[TestSuiteResponse]:
        suites = await repo.list_all(limit=1000)
        return [
            TestSuiteResponse(
                id=s.id,
                project_id=s.project_id,
                name=s.name,
                kind=s.kind,
                config=s.config or {},
                created_at=s.created_at.isoformat() if s.created_at else "",
            )
            for s in suites
        ]

    @get("/{suite_id:uuid}")
    async def get_test_suite(
        self, suite_id: UUID, repo: BaseRepository[TestSuite]
    ) -> TestSuiteResponse:
        suite = await repo.get(suite_id)
        if suite is None:
            raise ValueError(f"TestSuite {suite_id} not found")
        return TestSuiteResponse(
            id=suite.id,
            project_id=suite.project_id,
            name=suite.name,
            kind=suite.kind,
            config=suite.config or {},
            created_at=suite.created_at.isoformat() if suite.created_at else "",
        )

    @post()
    async def create_test_suite(
        self, data: TestSuiteCreate, repo: BaseRepository[TestSuite]
    ) -> TestSuiteResponse:
        suite = TestSuite(
            project_id=data.project_id,
            name=data.name,
            kind=data.kind,
            config=data.config,
        )
        saved = await repo.save(suite)
        return TestSuiteResponse(
            id=saved.id,
            project_id=saved.project_id,
            name=saved.name,
            kind=saved.kind,
            config=saved.config or {},
            created_at=saved.created_at.isoformat() if saved.created_at else "",
        )

    @put("/{suite_id:uuid}")
    async def update_test_suite(
        self,
        suite_id: UUID,
        data: TestSuiteUpdate,
        repo: BaseRepository[TestSuite],
    ) -> TestSuiteResponse:
        suite = await repo.get(suite_id)
        if suite is None:
            raise ValueError(f"TestSuite {suite_id} not found")
        if data.name is not None:
            suite.name = data.name
        if data.kind is not None:
            suite.kind = data.kind
        if data.config is not None:
            suite.config = data.config
        saved = await repo.save(suite)
        return TestSuiteResponse(
            id=saved.id,
            project_id=saved.project_id,
            name=saved.name,
            kind=saved.kind,
            config=saved.config or {},
            created_at=saved.created_at.isoformat() if saved.created_at else "",
        )

    @delete("/{suite_id:uuid}", status_code=HTTP_200_OK)
    async def delete_test_suite(
        self, suite_id: UUID, repo: BaseRepository[TestSuite]
    ) -> dict[str, str]:
        deleted = await repo.delete(suite_id)
        if not deleted:
            raise ValueError(f"TestSuite {suite_id} not found")
        return {"status": "deleted"}