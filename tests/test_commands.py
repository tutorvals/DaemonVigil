"""Unit tests for command dispatch and handlers."""
import pytest
from unittest.mock import AsyncMock, patch

from src.commands import (
    handle_clearmemory,
    handle_clear,
    handle_command,
    handle_help,
    handle_showmemory,
)


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
    async def test_quiet_hours_dispatches(self, mock_bot, tmp_storage):
        with patch("src.commands.handle_quiet_hours", new_callable=AsyncMock) as mock_qh:
            result = await handle_command("quiethours status", mock_bot, "123")
            assert result is True
            mock_qh.assert_called_once_with("status", mock_bot, "123")

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
    async def test_showmemory_dispatches(self, mock_bot, tmp_storage):
        with patch("src.commands.handle_showmemory", new_callable=AsyncMock) as mock_showmemory:
            result = await handle_command("showmemory", mock_bot, "123")
            assert result is True
            mock_showmemory.assert_called_once_with(mock_bot, "123")

    @pytest.mark.asyncio
    async def test_clearmemory_dispatches(self, mock_bot, tmp_storage):
        with patch("src.commands.handle_clearmemory", new_callable=AsyncMock) as mock_clearmemory:
            result = await handle_command("clearmemory", mock_bot, "123")
            assert result is True
            mock_clearmemory.assert_called_once_with(mock_bot, "123")

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
        assert "...quiethours status" in call_args[0][0]
        assert call_args[1]["chat_id"] == 456


class TestHandleQuietHours:
    @pytest.mark.asyncio
    async def test_status_shows_defaults(self, mock_bot, tmp_storage):
        from src.commands import handle_quiet_hours

        await handle_quiet_hours("status", mock_bot, "900")

        call_args = mock_bot.send_message.call_args
        assert "Quiet Hours Status" in call_args[0][0]
        assert "State: Disabled" in call_args[0][0]
        assert "Timezone: UTC" in call_args[0][0]
        assert call_args[1]["chat_id"] == 900

    @pytest.mark.asyncio
    async def test_set_and_enable_quiet_hours(self, mock_bot, tmp_storage):
        from src.commands import handle_quiet_hours
        from src.storage import get_user_storage

        await handle_quiet_hours("timezone Europe/Paris", mock_bot, "901")
        await handle_quiet_hours("set 22:00 08:00", mock_bot, "901")
        await handle_quiet_hours("on", mock_bot, "901")

        user_config = get_user_storage("901").config.get_config()
        assert user_config.timezone == "Europe/Paris"
        assert user_config.quiet_hours_start == "22:00"
        assert user_config.quiet_hours_end == "08:00"
        assert user_config.quiet_hours_enabled is True

    @pytest.mark.asyncio
    async def test_rejects_invalid_timezone(self, mock_bot, tmp_storage):
        from src.commands import handle_quiet_hours

        await handle_quiet_hours("timezone Mars/Olympus_Mons", mock_bot, "902")

        call_args = mock_bot.send_message.call_args
        assert "Invalid timezone" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_rejects_equal_quiet_hours(self, mock_bot, tmp_storage):
        from src.commands import handle_quiet_hours

        await handle_quiet_hours("set 08:00 08:00", mock_bot, "903")

        call_args = mock_bot.send_message.call_args
        assert "Invalid quiet-hours window" in call_args[0][0]


# ---- Clear command ----

class TestHandleClear:
    @pytest.mark.asyncio
    async def test_clears_only_messages(self, mock_bot, tmp_storage):
        from src.storage import get_user_storage

        # Add some data for this user
        user_storage = get_user_storage("789")
        user_storage.messages.add_message("user", "test msg")
        user_storage.scratchpad.add_note("test note")

        await handle_clear(mock_bot, "789")

        # Verify only messages cleared
        assert len(user_storage.messages.get_recent_messages()) == 0
        assert len(user_storage.scratchpad.get_notes()) == 1

        # Verify response sent
        mock_bot.send_message.assert_called_once()
        call_args = mock_bot.send_message.call_args
        assert "Conversation cleared" in call_args[0][0]
        assert call_args[1]["chat_id"] == 789


class TestHandleShowMemory:
    @pytest.mark.asyncio
    async def test_shows_empty_memory(self, mock_bot, tmp_storage):
        await handle_showmemory(mock_bot, "800")
        call_args = mock_bot.send_message.call_args
        assert "Scratchpad memory is empty." in call_args[0][0]
        assert call_args[1]["chat_id"] == 800

    @pytest.mark.asyncio
    async def test_shows_notes(self, mock_bot, tmp_storage):
        from src.storage import get_user_storage

        user_storage = get_user_storage("801")
        user_storage.scratchpad.add_note("remember this")

        await handle_showmemory(mock_bot, "801")

        call_args = mock_bot.send_message.call_args
        assert "Scratchpad Memory" in call_args[0][0]
        assert "remember this" in call_args[0][0]
        assert call_args[1]["chat_id"] == 801


class TestHandleClearMemory:
    @pytest.mark.asyncio
    async def test_clears_only_notes(self, mock_bot, tmp_storage):
        from src.storage import get_user_storage

        user_storage = get_user_storage("802")
        user_storage.messages.add_message("user", "keep this conversation")
        user_storage.scratchpad.add_note("delete this note")

        await handle_clearmemory(mock_bot, "802")

        assert len(user_storage.messages.get_recent_messages()) == 1
        assert len(user_storage.scratchpad.get_notes()) == 0

        call_args = mock_bot.send_message.call_args
        assert "Scratchpad memory cleared" in call_args[0][0]
        assert call_args[1]["chat_id"] == 802
