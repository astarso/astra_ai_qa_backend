"""Integration tests for wiring: JiraService and NotificationService calls."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from uuid import uuid4

from litestar.testing import AsyncTestClient


@pytest.mark.asyncio
async def test_create_defect_calls_jira_service_when_no_jira_key(test_client: AsyncTestClient):
    """Test that create_defect calls JiraService when jira_key is not provided."""
    payload = {
        "title": "Test Defect Without Jira Key",
        "description": "Testing auto Jira creation",
        "severity": 3,
    }

    with patch("app.services.jira_integration.JiraService") as mock_jira_cls:
        mock_jira_instance = AsyncMock()
        mock_jira_instance.create_bug.return_value = "AST-999"
        mock_jira_cls.return_value = mock_jira_instance

        response = await test_client.post("/api/v1/defects", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["jira_key"] == "AST-999"

        mock_jira_instance.create_bug.assert_called_once()
        call_kwargs = mock_jira_instance.create_bug.call_args.kwargs
        assert call_kwargs["project_key"] == "AST"
        assert call_kwargs["summary"] == "Test Defect Without Jira Key"
        assert call_kwargs["priority_name"] == "Medium"


@pytest.mark.asyncio
async def test_create_defect_does_not_call_jira_service_when_jira_key_provided(test_client: AsyncTestClient):
    """Test that create_defect does NOT call JiraService when jira_key IS provided."""
    payload = {
        "title": "Test Defect With Jira Key",
        "description": "Testing skip Jira when key exists",
        "severity": 2,
        "jira_key": "PROJ-123",
    }

    with patch("app.services.jira_integration.JiraService") as mock_jira_cls:
        mock_jira_instance = AsyncMock()
        mock_jira_instance.create_bug.return_value = "AST-999"
        mock_jira_cls.return_value = mock_jira_instance

        response = await test_client.post("/api/v1/defects", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["jira_key"] == "PROJ-123"

        mock_jira_instance.create_bug.assert_not_called()


@pytest.mark.asyncio
async def test_create_defect_jira_failure_does_not_break_defect_creation(test_client: AsyncTestClient):
    """Test that JiraService failure doesn't break defect creation."""
    payload = {
        "title": "Test Defect With Jira Failure",
        "description": "Testing graceful Jira failure",
        "severity": 4,
    }

    with patch("app.services.jira_integration.JiraService") as mock_jira_cls:
        mock_jira_instance = AsyncMock()
        mock_jira_instance.create_bug.side_effect = Exception("Jira connection error")
        mock_jira_cls.return_value = mock_jira_instance

        response = await test_client.post("/api/v1/defects", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["jira_key"] is None
        assert data["title"] == "Test Defect With Jira Failure"


@pytest.mark.asyncio
async def test_severity_mapping_to_jira_priority(test_client: AsyncTestClient):
    """Test that severity 1 (CRITICAL) maps to Highest priority."""
    payload = {
        "title": "Critical Defect",
        "description": "This should map to Highest priority",
        "severity": 1,
    }

    with patch("app.services.jira_integration.JiraService") as mock_jira_cls:
        mock_jira_instance = AsyncMock()
        mock_jira_instance.create_bug.return_value = "AST-1"
        mock_jira_cls.return_value = mock_jira_instance

        response = await test_client.post("/api/v1/defects", json=payload)
        assert response.status_code == 201

        call_kwargs = mock_jira_instance.create_bug.call_args.kwargs
        assert call_kwargs["priority_name"] == "Highest"


@pytest.mark.asyncio
async def test_recompute_run_status_calls_notification_service_on_failure():
    """Test that _recompute_run_status calls NotificationService when status is 'failed'."""
    from app.services.orchestration import OrchestrationService
    from unittest.mock import patch, AsyncMock, MagicMock
    from app.models.entities import TestRun, TestResult, TestSuite

    mock_session = AsyncMock()
    mock_repo = AsyncMock()

    run_id = uuid4()
    mock_run = MagicMock()
    mock_run.id = run_id
    mock_run.commit_sha = "abc123"
    mock_run.branch = "main"
    mock_run.status = "failed"

    mock_repo.collect_statuses.return_value = ["passed", "failed", "passed"]
    mock_repo.get.return_value = mock_run
    mock_repo.update_run_status = AsyncMock()
    mock_repo.save = AsyncMock()

    with patch("app.services.notifications.NotificationService") as mock_notif_cls:
        mock_notifier_instance = AsyncMock()
        mock_notifier_instance.notify.return_value = False
        mock_notif_cls.return_value = mock_notifier_instance

        service = OrchestrationService(mock_session)
        service._repo = mock_repo

        await service._recompute_run_status(run_id)

        mock_notif_cls.assert_called_once_with()
        mock_notifier_instance.notify.assert_called_once()
        call_args = mock_notifier_instance.notify.call_args
        assert "FAILED" in call_args[0][0]
        assert str(run_id) in call_args[0][0]


@pytest.mark.asyncio
async def test_recompute_run_status_does_not_notify_on_passed():
    """Test that notification is NOT sent when status is 'passed'."""
    from app.services.orchestration import OrchestrationService
    from unittest.mock import patch, AsyncMock, MagicMock

    mock_session = AsyncMock()
    mock_repo = AsyncMock()

    run_id = uuid4()
    mock_run = MagicMock()
    mock_run.id = run_id
    mock_run.commit_sha = "abc123"
    mock_run.branch = "main"

    mock_repo.collect_statuses.return_value = ["passed", "passed", "passed"]
    mock_repo.get.return_value = mock_run
    mock_repo.update_run_status = AsyncMock()
    mock_repo.save = AsyncMock()

    with patch("app.services.notifications.NotificationService") as mock_notif_cls:
        mock_notifier_instance = AsyncMock()
        mock_notif_cls.return_value = mock_notifier_instance

        service = OrchestrationService(mock_session)
        service._repo = mock_repo

        await service._recompute_run_status(run_id)

        mock_notif_cls.assert_not_called()
