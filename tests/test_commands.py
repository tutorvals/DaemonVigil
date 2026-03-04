"""Unit tests for command dispatch and handlers."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.commands import handle_command, handle_help, handle_clear
from src.storage import UserStorageManager


@pytest.fixture
def mock_bot():
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture
def tmp_storage(tmp_path, monkeypatch):
    """Set up temp storage directory."""
    monkeypatch.setattr("src.config.DATA_DIR", tmp_path)
    # Clear cache
    import src.storage as storage_mod
    with storage_mod._cache_lock:
        storage_mod._storage_cache.clear()
    yield tmp_path
    with storage_mod._cache_lock:
        storage_mod._storage_cache.clear()


# ---- Command dispatch ----

class TestCommandDispatch:
    @pytest.mark.asyncio
    async def test_status_dispatches(self, mock_bot, tmp_storage):
        with patch("src.commands.handle_status", new_callable=AsyncMock) as mock_status:
            result = await handle_command("status", mock_bot, "123")
            assert result is True
            mock_status.assert_called_once_with(mock_bot, "123")

    @pytest.mark.asyncio
    async def test_model_dispatches(self, mock_bot, tmp_storage):
        with patch("src.commands.handle_model", new_callable=AsyncMock) as mock_model:
            result = await handle_command("model sonnet", mock_bot, "123")
            assert result is True
            mock_model.assert_called_once_with("sonnet", mock_bot, "123")

    @pytest.mark.asyncio
    async def test_heartbeat_dispatches(self, mock_bot, tmp_storage):
        with patch("src.commands.handle_heartbeat", new_callable=AsyncMock) as mock_hb:
            result = await handle_command("heartbeat status", mock_bot, "123")
            assert result is True
            mock_hb.assert_called_once_with("status", mock_bot, "123")

    @pytest.mark.asyncio
    async def test_help_dispatches(self, mock_bot, tmp_storage):
        with patch("src.commands.handle_help", new_callable=AsyncMock) as mock_help:
            result = await handle_command("help", mock_bot, "123")
            assert result is True
            mock_help.assert_called_once_with(mock_bot, "123")

    @pytest.mark.asyncio
    async def test_clear_dispatches(self, mock_bot, tmp_storage):
        with patch("src.commands.handle_clear", new_callable=AsyncMock) as mock_clear:
            result = await handle_command("clear", mock_bot, "123")
            assert result is True
            mock_clear.assert_called_once_with(mock_bot, "123")

    @pytest.mark.asyncio
    async def test_unknown_command(self, mock_bot, tmp_storage):
        result = await handle_command("nonexistent", mock_bot, "123")
        assert result is False


# ---- Help command ----

class TestHandleHelp:
    @pytest.mark.asyncio
    async def test_sends_help_text(self, mock_bot):
        await handle_help(mock_bot, "456")
        mock_bot.send_message.assert_called_once()
        call_args = mock_bot.send_message.call_args
        assert "Available Commands" in call_args[0][0]
        assert call_args[1]["chat_id"] == 456


# ---- Clear command ----

class TestHandleClear:
    @pytest.mark.asyncio
    async def test_clears_user_storage(self, mock_bot, tmp_storage):
        from src.storage import get_user_storage

        # Add some data for this user
        user_storage = get_user_storage("789")
        user_storage.messages.add_message("user", "test msg")
        user_storage.scratchpad.add_note("test note")

        await handle_clear(mock_bot, "789")

        # Verify cleared
        assert len(user_storage.messages.get_recent_messages()) == 0
        assert len(user_storage.scratchpad.get_notes()) == 0

        # Verify response sent
        mock_bot.send_message.assert_called_once()
        call_args = mock_bot.send_message.call_args
        assert "Conversation cleared" in call_args[0][0]
        assert call_args[1]["chat_id"] == 789
