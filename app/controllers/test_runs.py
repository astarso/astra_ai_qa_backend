"""Test runs controller - create run, get run, submit results, get AI analysis."""

from uuid import UUID

from litestar import Controller, get, post
from litestar.di import Provide
from litestar.response import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AIAnalysis, TestResult, TestRun, TestCase
from app.repositories.ai import AIRepository
from app.schemas.schemas import (
    AIAnalysisResponse,
    CreateRunPayload,
    RerunResponse,
    RiskFactorDetail,
    RiskScoreResponse,
    RunDiffResponse,
    SubmitResultsPayload,
    TestCaseDiffItem,
    TestRunResponse,
)
from app.services.orchestration import OrchestrationService


async def provide_orchestration(db_session: AsyncSession) -> OrchestrationService:
    return OrchestrationService(db_session)


async def provide_ai_repo(db_session: AsyncSession) -> AIRepository:
    return AIRepository(db_session)


class TestRunsController(Controller):
    """Operations for test runs."""

    path = "/api/v1/runs"
    tags = ["Test Runs"]
    dependencies = {
        "orchestration": Provide(provide_orchestration),
        "ai_repo": Provide(provide_ai_repo),
    }

    @post()
    async def create_run(
        self, data: CreateRunPayload, orchestration: OrchestrationService
    ) -> TestRunResponse:
        from app.services.orchestration import RunRequest

        request = RunRequest(
            suite_id=data.suite_id,
            commit_sha=data.commit_sha,
            branch=data.branch,
            triggered_by=data.triggered_by,
            priority=data.priority,
            environment=data.environment,
        )
        run = await orchestration.create_run(request)
        return TestRunResponse(
            id=run.id,
            suite_id=run.suite_id,
            status=run.status,
            started_at=run.started_at.isoformat() if run.started_at else None,
            finished_at=run.finished_at.isoformat() if run.finished_at else None,
            commit_sha=run.commit_sha,
            branch=run.branch,
        )

    @get("/{run_id:uuid}")
    async def get_run(
        self,
        run_id: UUID,
        orchestration: OrchestrationService,
    ) -> TestRunResponse:
        from app.repositories.test_runs import TestRunRepository

        repo = orchestration._repo
        run = await repo.get_with_stats(run_id)
        if run is None:
            raise ValueError(f"Test run {run_id} not found")
        return TestRunResponse(
            id=run.id,
            suite_id=run.suite_id,
            status=run.status,
            started_at=run.started_at.isoformat() if run.started_at else None,
            finished_at=run.finished_at.isoformat() if run.finished_at else None,
            commit_sha=run.commit_sha,
            branch=run.branch,
            pass_count=getattr(run, "_pass_count", 0),
            fail_count=getattr(run, "_fail_count", 0),
            skipped_count=getattr(run, "_skipped_count", 0),
        )

    @post("/{run_id:uuid}/results")
    async def submit_results(
        self,
        run_id: UUID,
        data: SubmitResultsPayload,
        orchestration: OrchestrationService,
    ) -> dict:
        await orchestration.handle_result(run_id, data.results)
        return {"status": "ok", "run_id": str(run_id)}

    @get("/{run_id:uuid}/analyses")
    async def get_run_analyses(
        self,
        run_id: UUID,
        ai_repo: AIRepository,
        db_session: AsyncSession,
    ) -> list[AIAnalysisResponse]:
        stmt = (
            select(AIAnalysis)
            .join(TestResult, AIAnalysis.result_id == TestResult.id)
            .where(TestResult.run_id == run_id)
        )
        result = await db_session.execute(stmt)
        analyses = list(result.scalars().all())
        return [
            AIAnalysisResponse(
                id=a.id,
                result_id=a.result_id,
                category=a.category,
                probability=a.probability,
                short_cause=a.short_cause,
                suggestion=a.suggestion,
                llm_model=a.llm_model,
            )
            for a in analyses
        ]

    @post("/{run_id:uuid}/report")
    async def generate_report(
        self,
        run_id: UUID,
        orchestration: OrchestrationService,
    ) -> Response:
        run = await orchestration._repo.get_run_with_results(run_id)
        if run is None:
            raise ValueError(f"Test run {run_id} not found")

        results = run.results or []
        total = len(results)
        passed = sum(1 for r in results if r.status == "passed")
        failed = sum(1 for r in results if r.status == "failed")

        failed_tests = []
        for r in results:
            if r.status == "failed":
                failed_tests.append({
                    "title": r.test_case.title if r.test_case else "Unknown",
                    "error_message": r.error_message or "",
                    "category": r.ai_analysis.category if r.ai_analysis else "",
                    "suggestion": r.ai_analysis.suggestion if r.ai_analysis else "",
                })

        ai_summary = ""
        analyses = [r.ai_analysis for r in results if r.status == "failed" and r.ai_analysis]
        if analyses:
            categories = [a.category for a in analyses]
            ai_summary = f"Detected {len(analyses)} AI-analyzed failures. Categories: {', '.join(set(categories))}"

        from app.services.report_generator import ReportGeneratorService

        generator = ReportGeneratorService()
        pdf_bytes = await generator.generate_report(
            run_id=str(run.id),
            branch=run.branch,
            commit_sha=run.commit_sha,
            status=run.status,
            total_tests=total,
            passed_count=passed,
            failed_count=failed,
            failed_tests=failed_tests,
            ai_summary=ai_summary,
        )

        filename = f"report-{run.commit_sha[:8]}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @post("/{run_id:uuid}/rerun")
    async def rerun_failed(
        self,
        run_id: UUID,
        orchestration: OrchestrationService,
    ) -> RerunResponse:
        new_run = await orchestration.rerun_failed(run_id)
        return RerunResponse(
            new_run_id=str(new_run.id),
            rerun_count=1,
            status=new_run.status,
        )

    @post("/{run_id:uuid}/attachments")
    async def upload_attachment(
        self,
        run_id: UUID,
        data: dict,
    ) -> dict:
        from app.services.storage import StorageService
        import base64

        service = StorageService()
        filename = data.get("filename", "attachment")
        content_type = data.get("content_type", "application/octet-stream")
        raw_data = data.get("data", "")

        try:
            file_bytes = base64.b64decode(raw_data)
        except Exception:
            raise ValueError("Invalid base64 data")

        key = f"runs/{run_id}/{filename}"
        await service.upload(bucket="astra-attachments", key=key, data=file_bytes, content_type=content_type)
        return {"status": "ok", "key": key, "size": len(file_bytes)}

    @get("/{run_id:uuid}/diff")
    async def get_run_diff(
        self,
        run_id: UUID,
        compare_to: UUID,
        db_session: AsyncSession,
    ) -> RunDiffResponse:
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload

        from app.models.entities import TestCase, TestResult

        base_results_stmt = (
            select(TestResult, TestCase.title)
            .join(TestCase, TestResult.test_case_id == TestCase.id)
            .where(TestResult.run_id == run_id)
        )
        base_result = await db_session.execute(base_results_stmt)
        base_results = {row.TestResult.test_case_id: (row.TestResult.status, row.title) for row in base_result}

        compare_results_stmt = (
            select(TestResult, TestCase.title)
            .join(TestCase, TestResult.test_case_id == TestCase.id)
            .where(TestResult.run_id == compare_to)
        )
        compare_result = await db_session.execute(compare_results_stmt)
        compare_results = {row.TestResult.test_case_id: (row.TestResult.status, row.title) for row in compare_result}

        if not base_results:
            raise ValueError(f"Test run {run_id} not found")
        if not compare_results:
            raise ValueError(f"Test run {compare_to} not found")

        added = []
        removed = []
        changed = []
        unchanged_count = 0

        all_test_case_ids = set(base_results.keys()) | set(compare_results.keys())

        for tc_id in all_test_case_ids:
            base_status, base_title = base_results.get(tc_id, (None, None))
            compare_status, compare_title = compare_results.get(tc_id, (None, None))

            title = compare_title or base_title or "Unknown"

            if base_status is None:
                added.append(TestCaseDiffItem(
                    test_case_id=tc_id,
                    title=title,
                    status_before=None,
                    status_after=compare_status,
                ))
            elif compare_status is None:
                removed.append(TestCaseDiffItem(
                    test_case_id=tc_id,
                    title=title,
                    status_before=base_status,
                    status_after=None,
                ))
            elif base_status != compare_status:
                changed.append(TestCaseDiffItem(
                    test_case_id=tc_id,
                    title=title,
                    status_before=base_status,
                    status_after=compare_status,
                ))
            else:
                unchanged_count += 1

        summary = {
            "total_base": len(base_results),
            "total_compare": len(compare_results),
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
        }

        return RunDiffResponse(
            base_run_id=run_id,
            compare_run_id=compare_to,
            added=added,
            removed=removed,
            changed=changed,
            unchanged_count=unchanged_count,
            summary=summary,
        )

    @get("/{run_id:uuid}/risk")
    async def get_risk_score(
        self,
        run_id: UUID,
        db_session: AsyncSession,
    ) -> RiskScoreResponse:
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload

        from app.models.entities import AIAnalysis, TestCase, TestResult

        stmt = (
            select(TestResult, TestCase.title, AIAnalysis.category)
            .join(TestCase, TestResult.test_case_id == TestCase.id)
            .outerjoin(AIAnalysis, TestResult.id == AIAnalysis.result_id)
            .where(TestResult.run_id == run_id)
        )
        result = await db_session.execute(stmt)
        rows = list(result.all())

        if not rows:
            raise ValueError(f"Test run {run_id} not found")

        total_count = len(rows)
        passed_count = sum(1 for r in rows if r.TestResult.status == "passed")
        failed_count = sum(1 for r in rows if r.TestResult.status == "failed")
        skipped_count = sum(1 for r in rows if r.TestResult.status == "skipped")

        weighted_sum = 0.0
        factors = []

        for row in rows:
            test_result = row.TestResult
            title = row.title
            category = row.category

            if test_result.status == "failed":
                if category == "real_defect":
                    weight = 3.0
                elif category == "infrastructure":
                    weight = 2.0
                elif category == "flaky":
                    weight = 1.0
                else:
                    weight = 2.0

                weighted_sum += weight
                factors.append(RiskFactorDetail(
                    test_case_id=test_result.test_case_id,
                    title=title,
                    category=category,
                    weight=weight,
                ))

        max_weighted_sum = total_count * 3.0
        weighted_failure_ratio = weighted_sum / max_weighted_sum if max_weighted_sum > 0 else 0.0
        score = min(100, round(weighted_failure_ratio * 100))

        if score <= 25:
            risk_level = "low"
            recommendation = "release"
        elif score <= 50:
            risk_level = "medium"
            recommendation = "release_with_caution"
        elif score <= 75:
            risk_level = "high"
            recommendation = "investigate"
        else:
            risk_level = "critical"
            recommendation = "hold"

        return RiskScoreResponse(
            run_id=run_id,
            score=score,
            risk_level=risk_level,
            recommendation=recommendation,
            total_tests=total_count,
            passed_count=passed_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            factors=factors,
        )

    @post("/{run_id:uuid}/import/junit")
    async def import_junit(
        self,
        run_id: UUID,
        data: dict,
        db_session: AsyncSession,
    ) -> dict:
        import xml.etree.ElementTree as ET

        xml_content = data.get("xml_content")
        if not xml_content:
            raise ValueError("xml_content is required")

        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            raise ValueError(f"Invalid XML: {e}")

        # Find the test run to get suite_id
        stmt = select(TestRun).where(TestRun.id == run_id)
        result = await db_session.execute(stmt)
        run = result.scalar_one_or_none()
        if run is None:
            raise ValueError(f"Test run {run_id} not found")

        suite_id = run.suite_id

        # Get all test cases in this suite
        case_stmt = select(TestCase).where(TestCase.suite_id == suite_id)
        case_result = await db_session.execute(case_stmt)
        test_cases = case_result.scalars().all()
        title_to_case = {tc.title: tc for tc in test_cases}

        imported = 0
        skipped = 0
        errors = 0

        # Handle both <testsuites> and single <testsuite> formats
        testsuites = root.findall("testsuite")
        if testsuites:
            suite_elements = testsuites
        else:
            suite_elements = [root] if root.tag == "testsuite" else []

        for suite_elem in suite_elements:
            for testcase_elem in suite_elem.findall("testcase"):
                case_name = testcase_elem.get("name")
                if not case_name:
                    errors += 1
                    continue

                test_case = title_to_case.get(case_name)
                if test_case is None:
                    skipped += 1
                    continue

                # Check for failure or error
                failure = testcase_elem.find("failure")
                error = testcase_elem.find("error")
                if failure is not None or error is not None:
                    status = "failed"
                    error_elem = failure if failure is not None else error
                    error_message = error_elem.get("message", "") if error_elem is not None else ""
                    stack_trace = error_elem.text if error_elem is not None else ""
                else:
                    status = "passed"
                    error_message = None
                    stack_trace = None

                # Parse duration
                time_str = testcase_elem.get("time", "0")
                try:
                    duration_ms = float(time_str) * 1000
                except ValueError:
                    duration_ms = 0.0

                result = TestResult(
                    run_id=run_id,
                    test_case_id=test_case.id,
                    status=status,
                    duration_ms=duration_ms,
                    error_message=error_message,
                    stack_trace=stack_trace,
                )
                db_session.add(result)
                imported += 1

        await db_session.commit()
        return {"imported": imported, "skipped": skipped, "errors": errors}

    @get("/{run_id:uuid}/export")
    async def get_export(
        self,
        run_id: UUID,
        db_session: AsyncSession,
        format: str = "json",
    ) -> Response:
        import csv
        import io

        from app.models.entities import TestCase, TestResult

        stmt = (
            select(TestResult, TestCase.title)
            .join(TestCase, TestResult.test_case_id == TestCase.id)
            .where(TestResult.run_id == run_id)
        )
        result = await db_session.execute(stmt)
        rows = list(result.all())

        results = []
        for row in rows:
            results.append({
                "test_case_id": str(row.TestResult.test_case_id),
                "title": row.title,
                "status": row.TestResult.status,
                "duration_ms": row.TestResult.duration_ms,
                "error_message": row.TestResult.error_message,
            })

        if format == "csv":
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=["test_case_id", "title", "status", "duration_ms", "error_message"])
            writer.writeheader()
            for r in results:
                writer.writerow(r)
            csv_content = output.getvalue()
            return Response(
                content=csv_content,
                media_type="text/csv",
                headers={"Content-Disposition": f'attachment; filename="run-{run_id}.csv"'},
            )
        elif format == "parquet":
            return Response(
                content={"error": "Parquet export requires pandas+pyarrow. Install: uv add pandas pyarrow", "note": "Parquet export will be available after installing dependencies"},
                media_type="application/json",
                status_code=501,
            )
        else:
            return Response(
                content=results,
                media_type="application/json",
                headers={"Content-Disposition": f'attachment; filename="run-{run_id}.json"'},
            )
