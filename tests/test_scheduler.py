"""Unit tests for MultiUserHeartbeatScheduler."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.scheduler import MultiUserHeartbeatScheduler


@pytest.fixture
def mock_bot():
    return AsyncMock()


@pytest.fixture
def scheduler(mock_bot):
    """Create scheduler without starting it."""
    s = MultiUserHeartbeatScheduler(mock_bot)
    return s


class TestMultiUserScheduler:
    def test_add_user(self, scheduler):
        scheduler.scheduler = MagicMock()
        scheduler.scheduler.get_job.return_value = MagicMock(next_run_time=None)

        scheduler.add_user("123", interval_minutes=10, enabled=True)

        scheduler.scheduler.add_job.assert_called_once()
        assert scheduler.is_enabled("123") is True

    def test_remove_user(self, scheduler):
        scheduler.scheduler = MagicMock()
        scheduler.scheduler.get_job.return_value = MagicMock(next_run_time=None)

        scheduler.add_user("123", interval_minutes=10)
        scheduler.remove_user("123")

        assert "123" not in scheduler.user_states

    def test_pause_user(self, scheduler):
        scheduler.user_states["123"] = True
        scheduler.pause_user("123")
        assert scheduler.is_enabled("123") is False

    def test_resume_user(self, scheduler):
        scheduler.user_states["123"] = False
        scheduler.resume_user("123")
        assert scheduler.is_enabled("123") is True

    def test_is_enabled_default(self, scheduler):
        # Unknown user defaults to True
        assert scheduler.is_enabled("unknown") is True

    def test_get_user_status(self, scheduler):
        scheduler.scheduler = MagicMock()
        scheduler.scheduler.get_job.return_value = None
        scheduler.user_states["123"] = True

        status = scheduler.get_user_status("123")
        assert status["enabled"] is True
        assert status["next_run"] is None
        assert status["job_exists"] is False

    def test_get_user_status_with_job(self, scheduler):
        mock_job = MagicMock()
        mock_job.next_run_time = "2025-01-01T00:00:00"
        scheduler.scheduler = MagicMock()
        scheduler.scheduler.get_job.return_value = mock_job
        scheduler.user_states["123"] = False

        status = scheduler.get_user_status("123")
        assert status["enabled"] is False
        assert status["next_run"] == "2025-01-01T00:00:00"
        assert status["job_exists"] is True
