"""Import service for test cases and results from various formats."""
import json
import xml.etree.ElementTree as ET
import logging
from uuid import UUID
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import TestCase, TestResult, TestRun

logger = logging.getLogger(__name__)


class ImportService:
    """Service for importing test cases and results from external formats."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def import_test_cases_from_allure(self, suite_id: UUID, content: str) -> dict:
        """
        Import test cases from Allure JSON/YAML format.

        Allure test case format:
        {
            "name": "Test Login",
            "description": "Verify login functionality",
            "status": "passed",
            "steps": [...],
            "severity": "normal"
        }

        Supports both JSON and YAML-like formats.
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON format for Allure import")

        imported = 0
        for item in data if isinstance(data, list) else [data]:
            case = TestCase(
                suite_id=suite_id,
                title=item.get("name", "Untitled"),
                description=item.get("description"),
                source="allure_import",
            )
            self._session.add(case)
            imported += 1

        await self._session.commit()
        return {"imported": imported, "format": "allure_json"}

    async def import_test_cases_from_testrail(
        self, suite_id: UUID, content: str
    ) -> dict:
        """
        Import test cases from TestRail JSON export.

        TestRail format:
        {
            "cases": [
                {"title": "...", "section": "...", "steps": "..."}
            ]
        }
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON format for TestRail import")

        cases = data.get("cases", []) if isinstance(data, dict) else data

        imported = 0
        for item in cases:
            case = TestCase(
                suite_id=suite_id,
                title=item.get("title", "Untitled"),
                description=item.get("steps", item.get("description")),
                source="testrail_import",
            )
            self._session.add(case)
            imported += 1

        await self._session.commit()
        return {"imported": imported, "format": "testrail"}

    async def import_test_cases_from_testit(
        self, suite_id: UUID, content: str
    ) -> dict:
        """
        Import test cases from TestIT JSON export.

        TestIT format:
        {
            "testCases": [
                {"name": "...", "description": "...", "steps": [...]}
            ]
        }
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON format for TestIT import")

        cases = data.get("testCases", []) if isinstance(data, dict) else data

        imported = 0
        for item in cases:
            case = TestCase(
                suite_id=suite_id,
                title=item.get("name", "Untitled"),
                description=item.get("description"),
                source="testit_import",
            )
            self._session.add(case)
            imported += 1

        await self._session.commit()
        return {"imported": imported, "format": "testit"}

    async def import_results_from_allure_xml(
        self, run_id: UUID, xml_content: str
    ) -> dict:
        """
        Import test results from Allure XML format.

        Allure XML structure:
        <testsuite name="..." tests="..." failures="...">
            <testcase name="..." status="passed" time="0.5">
                <failure message="...">stack trace</failure>
                <steps>
                    <step name="..." status="passed"/>
                </steps>
            </testcase>
        </testsuite>

        NOTE: Unlike standard JUnit, Allure has:
        - status="passed" vs status="failed"
        - Nested <failure> with message attribute
        - <steps> inside testcase
        - time attribute (float seconds)
        """
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            raise ValueError(f"Invalid XML: {e}")

        # Allure can have <testsuite> or <testsuites> as root
        suites = root.findall("testsuite")
        if not suites:
            suites = [root] if root.tag == "testsuite" else []

        imported = 0
        skipped = 0

        for suite in suites:
            for testcase in suite.findall("testcase"):
                case_name = testcase.get("name")
                if not case_name:
                    skipped += 1
                    continue

                # Map Allure status to our status
                allure_status = testcase.get("status", "passed")
                if allure_status == "failed" or testcase.find("failure") is not None:
                    status = "failed"
                elif allure_status == "skipped" or testcase.find("skipped") is not None:
                    status = "skipped"
                else:
                    status = "passed"

                # Parse time
                time_str = testcase.get("time", "0")
                try:
                    duration_ms = float(time_str) * 1000
                except ValueError:
                    duration_ms = 0.0

                # Get failure info
                failure = testcase.find("failure")
                error_message = None
                stack_trace = None
                if failure is not None:
                    error_message = failure.get("message", "")
                    stack_trace = failure.text

                result = TestResult(
                    run_id=run_id,
                    test_case_id=UUID("00000000-0000-0000-0000-000000000001"),  # placeholder
                    status=status,
                    duration_ms=duration_ms,
                    error_message=error_message,
                    stack_trace=stack_trace,
                )
                self._session.add(result)
                imported += 1

        await self._session.commit()
        return {
            "imported": imported,
            "skipped": skipped,
            "format": "allure_xml",
            "note": "Allure XML imported (test_case_id is placeholder — use JUnit import for full mapping)",
        }