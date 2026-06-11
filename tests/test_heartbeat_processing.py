"""Tests for heartbeat processing behavior."""

from unittest.mock import AsyncMock, patch

import pytest

from src.claude import process_heartbeat
from src.storage import get_user_storage, _cache_lock, _storage_cache


@pytest.fixture(autouse=True)
def clean_storage_cache(tmp_path, monkeypatch):
    monkeypatch.setattr("src.config.DATA_DIR", tmp_path)
    with _cache_lock:
        _storage_cache.clear()
    yield
    with _cache_lock:
        _storage_cache.clear()


@pytest.mark.asyncio
async def test_process_heartbeat_uses_plain_json_first_attempt():
    user_id = "123"
    user_storage = get_user_storage(user_id)
    user_storage.messages.add_message("user", "Need a nudge later")
    user_config = user_storage.config.get_config()

    telegram_bot = AsyncMock()
    sdk_response = {
        "result": '{"action":"stay_silent","reasoning":"Too soon to follow up"}',
        "assistant_text": "",
        "structured_output": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
        "modelUsage": {"input_tokens": 1, "output_tokens": 1},
        "subtype": "success",
    }

    with patch("src.claude._run_claude_sdk", new=AsyncMock(return_value=sdk_response)) as mock_run:
        result = await process_heartbeat(
            telegram_bot=telegram_bot,
            user_id=user_id,
            user_storage=user_storage,
            user_config=user_config,
        )

    assert result["error"] is None
    assert result["tool_called"] is False
    assert result["reasoning"] == "Too soon to follow up"
    assert mock_run.await_count == 1
    assert mock_run.await_args.kwargs["json_schema"] is None
