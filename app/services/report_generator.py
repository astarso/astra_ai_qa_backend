import asyncio
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML


class ReportGeneratorService:
    def __init__(self) -> None:
        template_dir = Path(__file__).parent.parent / "templates"
        self._env = Environment(loader=FileSystemLoader(str(template_dir)))

    async def generate_report(
        self,
        run_id: str,
        branch: str,
        commit_sha: str,
        status: str,
        total_tests: int,
        passed_count: int,
        failed_count: int,
        failed_tests: list[dict],
        ai_summary: str = "",
    ) -> bytes:
        pass_rate = round(passed_count / total_tests * 100, 1) if total_tests > 0 else 0.0

        context = {
            "run_id": run_id,
            "branch": branch,
            "commit_sha": commit_sha,
            "status": status,
            "pass_rate": pass_rate,
            "total_tests": total_tests,
            "passed_count": passed_count,
            "failed_count": failed_count,
            "duration_minutes": 0.0,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "ai_summary": ai_summary,
            "failed_tests": failed_tests,
        }

        template = self._env.get_template("report.html")
        html_content = template.render(**context)

        pdf_bytes = await asyncio.to_thread(self._render_pdf, html_content)
        return pdf_bytes

    def _render_pdf(self, html_content: str) -> bytes:
        from io import BytesIO

        buffer = BytesIO()
        HTML(string=html_content).write_pdf(buffer)
        return buffer.getvalue()
