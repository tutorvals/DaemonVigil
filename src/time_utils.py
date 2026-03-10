"""Helpers for per-user timezone and quiet-hours logic."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .storage import UserConfig


def is_valid_timezone(timezone_name: str) -> bool:
    """Return True when the timezone can be loaded by zoneinfo."""
    try:
        ZoneInfo(timezone_name)
        return True
    except ZoneInfoNotFoundError:
        return False


def parse_hhmm(value: str) -> tuple[int, int]:
    """Parse a 24-hour HH:MM string."""
    if len(value) != 5 or value[2] != ":":
        raise ValueError("Time must use HH:MM format")

    hour = int(value[:2])
    minute = int(value[3:])
    if hour not in range(24) or minute not in range(60):
        raise ValueError("Time must use HH:MM format")

    return hour, minute


def get_local_now(timezone_name: str, now_utc: datetime | None = None) -> datetime:
    """Convert a UTC datetime to the user's local timezone."""
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    elif now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    else:
        now_utc = now_utc.astimezone(timezone.utc)

    return now_utc.astimezone(ZoneInfo(timezone_name))


def is_within_quiet_hours(user_config: UserConfig, now_utc: datetime | None = None) -> bool:
    """Return True when the user's local time is inside the configured quiet window."""
    if not user_config.quiet_hours_enabled:
        return False

    start_hour, start_minute = parse_hhmm(user_config.quiet_hours_start)
    end_hour, end_minute = parse_hhmm(user_config.quiet_hours_end)
    local_now = get_local_now(user_config.timezone, now_utc)
    current_minutes = local_now.hour * 60 + local_now.minute
    start_minutes = start_hour * 60 + start_minute
    end_minutes = end_hour * 60 + end_minute

    if start_minutes == end_minutes:
        return False
    if start_minutes < end_minutes:
        return start_minutes <= current_minutes < end_minutes
    return current_minutes >= start_minutes or current_minutes < end_minutes


def next_quiet_hours_end(user_config: UserConfig, now_utc: datetime | None = None) -> datetime | None:
    """Return the next local datetime when quiet hours end, or None when inactive."""
    if not user_config.quiet_hours_enabled:
        return None

    local_now = get_local_now(user_config.timezone, now_utc)
    if not is_within_quiet_hours(user_config, now_utc):
        return None

    start_hour, start_minute = parse_hhmm(user_config.quiet_hours_start)
    end_hour, end_minute = parse_hhmm(user_config.quiet_hours_end)
    start_minutes = start_hour * 60 + start_minute
    end_minutes = end_hour * 60 + end_minute

    end_local = local_now.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
    if start_minutes < end_minutes:
        if end_local <= local_now:
            end_local += timedelta(days=1)
    elif local_now.hour * 60 + local_now.minute >= start_minutes:
        end_local += timedelta(days=1)

    return end_local
