import pytest

from app.services.registry import RegistryService


@pytest.mark.asyncio
async def test_publish_artifact_returns_stub():
    service = RegistryService()
    result = await service.publish_artifact(
        artifact_path="/path/to/artifact.tar",
        registry_url="harbor.astracr.ru",
        repository="astra-qa/backend",
        tags=["v1.0.0", "latest"],
    )

    assert result["status"] == "stub"
    assert result["artifact_path"] == "/path/to/artifact.tar"
    assert result["registry_url"] == "harbor.astracr.ru"
    assert result["repository"] == "astra-qa/backend"
    assert result["tags"] == ["v1.0.0", "latest"]
    assert result["published_uri"] == "harbor.astracr.ru/astra-qa/backend:v1.0.0"


@pytest.mark.asyncio
async def test_publish_artifact_empty_tags():
    service = RegistryService()
    result = await service.publish_artifact(
        artifact_path="/path/to/artifact.tar",
        registry_url="harbor.astracr.ru",
        repository="astra-qa/backend",
        tags=[],
    )

    assert result["status"] == "stub"
    assert result["published_uri"] == ""