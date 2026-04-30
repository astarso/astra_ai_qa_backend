"""Test service logic: Sanitizer and OrchestrationService."""

import uuid
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from app.models.entities import TestCase, TestSuite, TestRun
from app.services.sanitizer import Sanitizer
from app.services.orchestration import OrchestrationService, TestShard, RunRequest


class TestSanitizer:
    sanitizer = Sanitizer()

    def test_clean_api_key_patterns(self):
        data = {
            "api_key": "api_key: sk_test_1234567890abcdef",
            "secret": "secret_key: my_secret_key_1234567890ab",
        }
        cleaned = self.sanitizer.clean(data)
        assert cleaned["api_key"] == "api_key: [REDACTED]"
        assert cleaned["secret"] == "secret_key: [REDACTED]"

    def test_clean_bearer_token(self):
        data = {"auth": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"}
        cleaned = self.sanitizer.clean(data)
        assert cleaned["auth"] == "Bearer [REDACTED]"

    def test_clean_email_addresses(self):
        data = {"user": "john.doe@example.com", "contact": "admin@company.org"}
        cleaned = self.sanitizer.clean(data)
        assert cleaned["user"] == "[EMAIL_REDACTED]"
        assert cleaned["contact"] == "[EMAIL_REDACTED]"

    def test_clean_github_token(self):
        data = {"token": "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"}
        cleaned = self.sanitizer.clean(data)
        assert cleaned["token"] == "[GITHUB_TOKEN_REDACTED]"

    def test_clean_gitlab_token(self):
        data = {"token": "glpat-xxxxxxxxxxxxxxxxxxxx"}
        cleaned = self.sanitizer.clean(data)
        assert cleaned["token"] == "[GITLAB_TOKEN_REDACTED]"

    def test_clean_slack_token(self):
        data = {"token": "xoxb-1234567890abcdefghij"}
        cleaned = self.sanitizer.clean(data)
        assert cleaned["token"] == "[SLACK_TOKEN_REDACTED]"

    def test_clean_password_pattern(self):
        data = {"password": "password: super_secret_password_123"}
        cleaned = self.sanitizer.clean(data)
        assert cleaned["password"] == "password: [REDACTED]"

    def test_clean_preserves_non_string_values(self):
        data = {"count": 42, "active": True, "data": None}
        cleaned = self.sanitizer.clean(data)
        assert cleaned["count"] == 42
        assert cleaned["active"] is True
        assert cleaned["data"] is None

    def test_clean_preserves_clean_text(self):
        data = {"message": "This is a normal message with no secrets", "name": "Test"}
        cleaned = self.sanitizer.clean(data)
        assert cleaned["message"] == "This is a normal message with no secrets"
        assert cleaned["name"] == "Test"

    def test_clean_multiple_secrets_in_one_value(self):
        data = {"log": "User admin@example.com with token ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx made a request"}
        cleaned = self.sanitizer.clean(data)
        assert "[EMAIL_REDACTED]" in cleaned["log"]
        assert "[GITHUB_TOKEN_REDACTED]" in cleaned["log"]


class TestOrchestrationServiceSplitByLPT:
    @pytest.fixture
    def mock_session(self):
        return MagicMock()

    def _make_case(self, avg_ms):
        case = MagicMock(spec=TestCase)
        case.avg_duration_ms = avg_ms
        return case

    def test_split_empty_cases_returns_empty_shards(self, mock_session):
        svc = OrchestrationService(mock_session)
        shards = svc._split_by_lpt([], 3)
        assert shards == []

    def test_split_single_case_single_shard(self, mock_session):
        svc = OrchestrationService(mock_session)
        cases = [self._make_case(100.0)]
        shards = svc._split_by_lpt(cases, 3)
        assert len(shards) == 1
        assert shards[0].shard_id == 0
        assert len(shards[0].cases) == 1

    def test_split_multiple_cases_balanced(self, mock_session):
        svc = OrchestrationService(mock_session)
        cases = [
            self._make_case(100.0),
            self._make_case(200.0),
            self._make_case(50.0),
            self._make_case(150.0),
            self._make_case(80.0),
        ]
        shards = svc._split_by_lpt(cases, 3)
        assert len(shards) == 3
        all_cases = [c for s in shards for c in s.cases]
        assert len(all_cases) == 5

    def test_split_more_shards_than_cases(self, mock_session):
        svc = OrchestrationService(mock_session)
        cases = [self._make_case(100.0), self._make_case(200.0)]
        shards = svc._split_by_lpt(cases, 5)
        assert len(shards) == 2

    def test_split_zero_shard_count_defaults_to_one(self, mock_session):
        svc = OrchestrationService(mock_session)
        cases = [self._make_case(100.0)]
        shards = svc._split_by_lpt(cases, 0)
        assert len(shards) == 1

    def test_split_all_same_duration_balances(self, mock_session):
        svc = OrchestrationService(mock_session)
        cases = [self._make_case(100.0) for _ in range(6)]
        shards = svc._split_by_lpt(cases, 3)
        assert len(shards) == 3
        for shard in shards:
            assert len(shard.cases) == 2

    def test_split_longer_cases_first(self, mock_session):
        svc = OrchestrationService(mock_session)
        cases = [
            self._make_case(300.0),
            self._make_case(100.0),
            self._make_case(200.0),
        ]
        shards = svc._split_by_lpt(cases, 2)
        assert len(shards) == 2
        longest_shard = max(shards, key=lambda s: sum(c.avg_duration_ms for c in s.cases))
        assert any(c.avg_duration_ms == 300.0 for c in longest_shard.cases)