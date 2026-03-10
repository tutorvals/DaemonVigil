"""Unit tests for quiet-hours time helpers."""
from datetime import datetime, timezone

from src.storage import UserConfig
from src.time_utils import is_valid_timezone, is_within_quiet_hours, parse_hhmm


def make_config(**kwargs) -> UserConfig:
    base = {
        "user_id": "123",
        "timezone": "UTC",
        "quiet_hours_enabled": True,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00",
    }
    base.update(kwargs)
    return UserConfig(**base)


class TestParseHHMM:
    def test_accepts_valid_time(self):
        assert parse_hhmm("09:30") == (9, 30)

    def test_rejects_invalid_time(self):
        for value in ("9:30", "24:00", "12:60", "abcd"):
            try:
                parse_hhmm(value)
            except ValueError:
                pass
            else:
                raise AssertionError(f"{value} should be invalid")


class TestQuietHours:
    def test_overnight_window(self):
        config = make_config()
        assert is_within_quiet_hours(config, datetime(2026, 3, 10, 23, 30, tzinfo=timezone.utc)) is True
        assert is_within_quiet_hours(config, datetime(2026, 3, 10, 9, 0, tzinfo=timezone.utc)) is False

    def test_same_day_window(self):
        config = make_config(quiet_hours_start="13:00", quiet_hours_end="17:00")
        assert is_within_quiet_hours(config, datetime(2026, 3, 10, 14, 0, tzinfo=timezone.utc)) is True
        assert is_within_quiet_hours(config, datetime(2026, 3, 10, 18, 0, tzinfo=timezone.utc)) is False

    def test_disabled_window(self):
        config = make_config(quiet_hours_enabled=False)
        assert is_within_quiet_hours(config, datetime(2026, 3, 10, 23, 30, tzinfo=timezone.utc)) is False


class TestTimezoneValidation:
    def test_valid_timezone(self):
        assert is_valid_timezone("Europe/Paris") is True

    def test_invalid_timezone(self):
        assert is_valid_timezone("Mars/Olympus_Mons") is False
