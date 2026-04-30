import logging
from uuid import UUID

from app.tasks.broker import broker

logger = logging.getLogger(__name__)


@broker.task(task_name="run_suite_shard")
async def run_suite_shard(run_id: str, shard_index: int, test_case_ids: list[str]) -> None:
    """Task: run a test shard — worker picks this up from RabbitMQ."""
    logger.info(
        "Shard %d for run %s scheduled with %d test cases",
        shard_index,
        run_id,
        len(test_case_ids),
    )


@broker.task(task_name="analyze_run_failures")
async def analyze_run_failures(run_id: str) -> None:
    """Task: AI analysis of test run failures."""
    from app.db import async_session
    from app.models.entities import TestResult
    from app.repositories.ai import AIRepository
    from app.services.ai_analyzer import AIAnalyzerService
    from app.services.embeddings import EmbeddingService
    from sqlalchemy import select

    logger.info("Starting AI analysis for run %s", run_id)

    async with async_session() as session:
        stmt = select(TestResult).where(
            TestResult.run_id == UUID(run_id),
            TestResult.status == "failed",
        )
        result = await session.execute(stmt)
        failed_results = list(result.scalars().all())

        if not failed_results:
            logger.info("No failed results found for run %s", run_id)
            return

        logger.info("Found %d failed results for run %s", len(failed_results), run_id)

        for test_result in failed_results:
            try:
                ai_repo = AIRepository(session)
                embedding_service = EmbeddingService()
                analyzer = AIAnalyzerService(ai_repo=ai_repo, embedding_service=embedding_service)
                await analyzer.analyze(test_result)
                await session.commit()
                logger.info("Analyzed result %s", test_result.id)
            except Exception as e:
                logger.error("Failed to analyze result %s: %s", test_result.id, e)
                await session.rollback()