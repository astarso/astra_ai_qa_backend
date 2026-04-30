"""Backup service for database and artifact backup."""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class BackupService:
    """
    Service for automated backup of database and artifacts.

    Supports:
    - PostgreSQL dump
    - MinIO artifact backup
    - Retention policies

    NOTE: Actual backup requires credentials and backup storage.
    This is a stub that logs the intent.
    """

    async def create_backup(self, backup_type: str = "full") -> dict:
        """
        Create a backup of database and/or artifacts.

        Args:
            backup_type: "full", "db_only", or "artifacts_only"

        Returns:
            dict with backup_id, status, timestamp
        """
        logger.info("Backup requested: type=%s", backup_type)

        backup_id = f"backup-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

        return {
            "backup_id": backup_id,
            "type": backup_type,
            "status": "stub",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "message": "Stub implementation — replace with actual backup (pg_dump, mc mirror)",
        }

    async def list_backups(self, limit: int = 10) -> list[dict]:
        """List recent backups."""
        logger.info("List backups requested: limit=%s", limit)
        return []