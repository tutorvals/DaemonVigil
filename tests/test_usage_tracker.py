"""Unit tests for usage tracker."""
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.usage_tracker import (
    calculate_cost,
    log_api_usage,
    check_threshold_crossed,
    get_user_usage_stats,
    USAGE_FILE,
)


class TestCalculateCost:
    def test_known_model(self):
        result = calculate_cost("claude-sonnet-4-20250514", 1000, 500)
        assert result["input_tokens"] == 1000
        assert result["output_tokens"] == 500
        assert result["total_cost"] > 0
        assert "timestamp" in result

    def test_unknown_model_falls_back(self):
        result = calculate_cost("unknown-model", 1000, 500)
        # Should use sonnet pricing as default
        expected = calculate_cost("claude-sonnet-4-20250514", 1000, 500)
        assert result["total_cost"] == expected["total_cost"]


class TestCheckThresholdCrossed:
    def test_no_crossing(self):
        assert check_threshold_crossed(0.5, 0.8, []) is None

    def test_crossing_first_dollar(self):
        result = check_threshold_crossed(0.8, 1.2, [])
        assert result == 1

    def test_crossing_multiple(self):
        result = check_threshold_crossed(0.5, 3.5, [])
        assert result == 3  # Returns highest

    def test_already_notified(self):
        result = check_threshold_crossed(0.8, 1.2, [1])
        assert result is None

    def test_skips_notified_returns_next(self):
        result = check_threshold_crossed(0.5, 2.5, [1])
        assert result == 2


class TestLogApiUsage:
    def test_logs_with_user_id(self, tmp_path, monkeypatch):
        usage_file = tmp_path / "api_usage.jsonl"
        monkeypatch.setattr("src.usage_tracker.USAGE_FILE", usage_file)

        data = {
            "input_tokens": 100,
            "output_tokens": 50,
            "total_cost": 0.001,
            "model": "test",
            "timestamp": "2025-01-01T00:00:00Z",
            "user_id": "123"
        }
        log_api_usage(data)

        lines = usage_file.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["user_id"] == "123"

    def test_adds_unknown_user_id_if_missing(self, tmp_path, monkeypatch):
        usage_file = tmp_path / "api_usage.jsonl"
        monkeypatch.setattr("src.usage_tracker.USAGE_FILE", usage_file)

        data = {
            "input_tokens": 100,
            "output_tokens": 50,
            "total_cost": 0.001,
            "model": "test",
            "timestamp": "2025-01-01T00:00:00Z",
        }
        log_api_usage(data)

        entry = json.loads(usage_file.read_text().strip())
        assert entry["user_id"] == "unknown"


class TestGetUserUsageStats:
    def test_filters_by_user(self, tmp_path, monkeypatch):
        usage_file = tmp_path / "api_usage.jsonl"
        monkeypatch.setattr("src.usage_tracker.USAGE_FILE", usage_file)

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        entries = [
            {"user_id": "123", "input_tokens": 100, "output_tokens": 50, "total_cost": 0.01, "timestamp": now},
            {"user_id": "456", "input_tokens": 200, "output_tokens": 100, "total_cost": 0.02, "timestamp": now},
            {"user_id": "123", "input_tokens": 300, "output_tokens": 150, "total_cost": 0.03, "timestamp": now},
        ]
        with open(usage_file, 'w') as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        stats = get_user_usage_stats("123", days=1)
        assert stats["user_id"] == "123"
        assert stats["request_count"] == 2
        assert stats["total_cost"] == 0.04
        assert stats["input_tokens"] == 400

    def test_empty_file(self, tmp_path, monkeypatch):
        usage_file = tmp_path / "api_usage.jsonl"
        monkeypatch.setattr("src.usage_tracker.USAGE_FILE", usage_file)
        # File doesn't exist
        stats = get_user_usage_stats("123", days=1)
        assert stats["request_count"] == 0
        assert stats["total_cost"] == 0.0
