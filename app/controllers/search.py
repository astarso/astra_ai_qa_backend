"""Search controller — full-text search across test results."""

from litestar import Controller, get

from app.services.search import SearchService


class SearchController(Controller):
    """Full-text search endpoint."""

    path = "/api/v1/search"
    tags = ["Search"]
    exclude_from_auth = True

    @get()
    async def search(
        self,
        q: str = "",
        status: str | None = None,
        run_id: str | None = None,
    ) -> list[dict]:
        """Search test results by query string."""
        if not q:
            return []
        service = SearchService()
        results = await service.search(query=q, status=status, run_id=run_id)
        return results