from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    def __init__(self, session: AsyncSession, model_class: type[T]) -> None:
        self._session = session
        self._model_class = model_class

    async def get(self, id: UUID) -> T | None:
        stmt = select(self._model_class).where(self._model_class.id == id)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def save(self, entity: T) -> T:
        self._session.add(entity)
        await self._session.flush()
        await self._session.refresh(entity)
        return entity

    async def save_many(self, entities: list[T]) -> list[T]:
        self._session.add_all(entities)
        await self._session.flush()
        for entity in entities:
            await self._session.refresh(entity)
        return entities

    async def list_all(self, offset: int = 0, limit: int = 100) -> list[T]:
        stmt = select(self._model_class).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, id: UUID) -> bool:
        stmt = delete(self._model_class).where(self._model_class.id == id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0
