"""Test cases controller - CRUD for test cases."""

from uuid import UUID

from litestar import Controller, get, post
from litestar.di import Provide
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import TestCase
from app.repositories.base import BaseRepository
from app.schemas.schemas import (
    GenerateTestCaseRequest,
    GeneratedTestCase,
    GeneratedTestCaseStep,
    TestCaseCreate,
    TestCaseResponse,
)


async def provide_test_case_repo(db_session: AsyncSession) -> BaseRepository[TestCase]:
    return BaseRepository(db_session, TestCase)


class TestCasesController(Controller):
    """CRUD operations for test cases."""

    path = "/api/v1/test-cases"
    tags = ["Test Cases"]
    dependencies = {"repo": Provide(provide_test_case_repo)}

    @get()
    async def list_test_cases(
        self,
        repo: BaseRepository[TestCase],
        db_session: AsyncSession,
        suite_id: UUID | None = None,
    ) -> list[TestCaseResponse]:
        if suite_id is not None:
            stmt = select(TestCase).where(TestCase.suite_id == suite_id).limit(1000)
            result = await db_session.execute(stmt)
            cases = list(result.scalars().all())
        else:
            cases = await repo.list_all(limit=1000)
        return [
            TestCaseResponse(
                id=c.id,
                title=c.title,
                suite_id=c.suite_id,
                source=c.source,
                created_at=c.created_at.isoformat() if c.created_at else "",
                requirement_id=c.requirement_id,
            )
            for c in cases
        ]

    @get("/{case_id:uuid}")
    async def get_test_case(
        self, case_id: UUID, repo: BaseRepository[TestCase]
    ) -> TestCaseResponse:
        case = await repo.get(case_id)
        if case is None:
            raise ValueError(f"Test case {case_id} not found")
        return TestCaseResponse(
            id=case.id,
            title=case.title,
            suite_id=case.suite_id,
            source=case.source,
            created_at=case.created_at.isoformat() if case.created_at else "",
            requirement_id=case.requirement_id,
        )

    @post()
    async def create_test_case(
        self, data: TestCaseCreate, repo: BaseRepository[TestCase]
    ) -> TestCaseResponse:
        case = TestCase(
            title=data.title,
            description=data.description,
            source=data.source,
            code_path=data.code_path,
            suite_id=data.suite_id,
            requirement_id=data.requirement_id,
        )
        saved = await repo.save(case)
        return TestCaseResponse(
            id=saved.id,
            title=saved.title,
            suite_id=saved.suite_id,
            source=saved.source,
            created_at=saved.created_at.isoformat() if saved.created_at else "",
            requirement_id=saved.requirement_id,
        )

    @post("/generate")
    async def generate_test_case(
        self, data: GenerateTestCaseRequest, db_session: AsyncSession
    ) -> GeneratedTestCase:
        from app.services.test_case_generator import TestCaseGeneratorService

        generator = TestCaseGeneratorService()
        result = await generator.generate(data.user_story)

        steps = [
            GeneratedTestCaseStep(step=s.get("step", ""), expected=s.get("expected", ""))
            for s in result.get("steps", [])
        ]

        return GeneratedTestCase(
            title=result.get("title", ""),
            preconditions=result.get("preconditions", ""),
            steps=steps,
        )
