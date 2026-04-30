import pytest

from app.services.backup import BackupService


@pytest.mark.asyncio
async def test_create_backup_full():
    service = BackupService()
    result = await service.create_backup(backup_type="full")

    assert result["status"] == "stub"
    assert result["type"] == "full"
    assert "backup_id" in result
    assert result["backup_id"].startswith("backup-")
    assert "created_at" in result


@pytest.mark.asyncio
async def test_create_backup_db_only():
    service = BackupService()
    result = await service.create_backup(backup_type="db_only")

    assert result["status"] == "stub"
    assert result["type"] == "db_only"


@pytest.mark.asyncio
async def test_create_backup_artifacts_only():
    service = BackupService()
    result = await service.create_backup(backup_type="artifacts_only")

    assert result["status"] == "stub"
    assert result["type"] == "artifacts_only"


@pytest.mark.asyncio
async def test_list_backups():
    service = BackupService()
    result = await service.list_backups(limit=5)

    assert isinstance(result, list)
    assert len(result) == 0