"""OpenSearch full-text search service for test results."""

import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

INDEX_NAME = "test-results"
INDEX_MAPPING = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "properties": {
            "result_id": {"type": "keyword"},
            "run_id": {"type": "keyword"},
            "test_name": {"type": "text", "analyzer": "standard"},
            "error_message": {"type": "text", "analyzer": "standard"},
            "stack_trace": {"type": "text", "analyzer": "standard"},
            "status": {"type": "keyword"},
            "timestamp": {"type": "date"},
        }
    },
}


class SearchService:
    """Async OpenSearch client with graceful degradation."""

    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not settings.opensearch_url:
                return None
            try:
                from opensearchpy import AsyncOpenSearch

                self._client = AsyncOpenSearch(
                    hosts=[settings.opensearch_url],
                    use_ssl=False,
                    verify_certs=False,
                )
            except Exception as e:
                logger.warning(f"Failed to create OpenSearch client: {e}")
                return None
        return self._client

    async def ensure_index(self) -> None:
        """Create the index if it doesn't exist."""
        client = self._get_client()
        if client is None:
            return
        try:
            exists = await client.indices.exists(index=INDEX_NAME)
            if not exists:
                await client.indices.create(index=INDEX_NAME, body=INDEX_MAPPING)
                logger.info(f"Created OpenSearch index: {INDEX_NAME}")
        except Exception as e:
            logger.warning(f"Failed to ensure index: {e}")

    async def index_result(
        self,
        result_id: str,
        run_id: str,
        test_name: str,
        status: str,
        error_message: str = "",
        stack_trace: str = "",
        timestamp: str = "",
    ) -> bool:
        """Index a test result document. Returns True if successful."""
        client = self._get_client()
        if client is None:
            return False

        doc = {
            "result_id": result_id,
            "run_id": run_id,
            "test_name": test_name,
            "status": status,
            "error_message": error_message,
            "stack_trace": stack_trace,
            "timestamp": timestamp or "now",
        }

        try:
            await client.index(index=INDEX_NAME, id=result_id, body=doc, refresh=True)
            return True
        except Exception as e:
            logger.warning(f"Failed to index result {result_id}: {e}")
            return False

    async def search(
        self,
        query: str,
        status: str | None = None,
        run_id: str | None = None,
        size: int = 50,
    ) -> list[dict[str, Any]]:
        """Full-text search across test results. Returns list of matching docs."""
        client = self._get_client()
        if client is None:
            return []

        filters = []
        if status:
            filters.append({"term": {"status": status}})
        if run_id:
            filters.append({"term": {"run_id": run_id}})

        search_body: dict[str, Any] = {
            "size": size,
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["test_name^2", "error_message", "stack_trace"],
                                "fuzziness": "AUTO",
                            }
                        }
                    ],
                    "filter": filters,
                }
            },
        }

        try:
            response = await client.search(index=INDEX_NAME, body=search_body)
            return [hit["_source"] for hit in response.get("hits", {}).get("hits", [])]
        except Exception as e:
            logger.warning(f"Search failed: {e}")
            return []