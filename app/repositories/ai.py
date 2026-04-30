from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AIAnalysis
from app.repositories.base import BaseRepository


class AIRepository(BaseRepository[AIAnalysis]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AIAnalysis)

    async def find_nearest(
        self, embedding: list[float], threshold: float = 0.92
    ) -> AIAnalysis | None:
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        sql = text("""
            SELECT *,
                   1 - (error_embedding <=> :embedding::vector) AS cosine_distance
            FROM ai_analyses
            WHERE error_embedding IS NOT NULL
            ORDER BY error_embedding <=> :embedding::vector
            LIMIT 1
        """)

        result = await self._session.execute(sql, {"embedding": embedding_str})
        row = result.fetchone()

        if row is None:
            return None

        cosine_dist = row._mapping["cosine_distance"]

        if cosine_dist < threshold:
            return None

        analysis = await self.get(row.id)
        return analysis
