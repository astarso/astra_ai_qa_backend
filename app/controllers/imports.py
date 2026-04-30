"""Import controller for external test formats."""
from uuid import UUID

from litestar import Controller, post
from litestar.di import Provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.import_service import ImportService


async def provide_import_service(db_session: AsyncSession) -> ImportService:
    return ImportService(db_session)


class ImportController(Controller):
    path = "/api/v1"
    tags = ["Import"]
    dependencies = {"import_service": Provide(provide_import_service)}

    @post("/test-cases/import")
    async def import_test_cases(
        self,
        data: dict,
        import_service: ImportService,
        suite_id: UUID,
        format: str = "allure",
    ) -> dict:
        """Import test cases from external format (Allure, TestRail, TestIT)."""
        content = data.get("content", "")
        if not content:
            raise ValueError("content field is required")

        if format == "testrail":
            return await import_service.import_test_cases_from_testrail(suite_id, content)
        elif format == "testit":
            return await import_service.import_test_cases_from_testit(suite_id, content)
        else:
            return await import_service.import_test_cases_from_allure(suite_id, content)

    @post("/runs/{run_id:uuid}/import/allure")
    async def import_allure_xml(
        self,
        run_id: UUID,
        data: dict,
        import_service: ImportService,
    ) -> dict:
        """Import test results from Allure XML format."""
        xml_content = data.get("xml_content")
        if not xml_content:
            raise ValueError("xml_content field is required")

        return await import_service.import_results_from_allure_xml(run_id, xml_content)