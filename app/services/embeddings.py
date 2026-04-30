from collections import OrderedDict
from typing import Self

import asyncio

from gigachat import GigaChat

from app.config import settings


class EmbeddingService:
    def __init__(self, max_cache_size: int = 1000) -> None:
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._max_cache_size = max_cache_size

    async def encode(self, text: str) -> list[float]:
        cached = self._cache.get(text)
        if cached is not None:
            self._cache.move_to_end(text)
            return cached

        credentials = settings.llm_api_key.get_secret_value()

        def _sync_encode() -> list[float]:
            with GigaChat(credentials=credentials, verify_ssl_certs=False) as client:
                response = client.embeddings([text], model="Embeddings")
                return response.data[0].embedding

        embedding = await asyncio.to_thread(_sync_encode)

        self._cache[text] = embedding
        if len(self._cache) > self._max_cache_size:
            self._cache.popitem(last=False)

        return embedding

    def clear_cache(self) -> None:
        self._cache.clear()

    @classmethod
    def instance(cls) -> Self:
        if not hasattr(cls, "_instance"):
            cls._instance = cls()
        return cls._instance
