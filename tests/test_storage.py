"""Unit tests for multi-user storage classes."""
import json
import tempfile
import threading
from pathlib import Path

import pytest

from src.storage import (
    MessageStorage,
    ScratchpadStorage,
    UserRegistry,
    UserConfigStorage,
    UserStorageManager,
    get_user_storage,
    _storage_cache,
    _cache_lock,
)


@pytest.fixture(autouse=True)
def clean_cache():
    """Clear storage cache before each test."""
    with _cache_lock:
        _storage_cache.clear()
    yield
    with _cache_lock:
        _storage_cache.clear()


@pytest.fixture
def tmp_dir(tmp_path):
    return tmp_path


# ---- UserRegistry ----

class TestUserRegistry:
    def test_register_and_get(self, tmp_dir):
        registry = UserRegistry(tmp_dir / "users.json")
        user = registry.register_user("123", "alice", "Alice")

        assert user.user_id == "123"
        assert user.telegram_username == "alice"
        assert user.telegram_first_name == "Alice"
        assert user.status == "active"

        fetched = registry.get_user("123")
        assert fetched is not None
        assert fetched.user_id == "123"

    def test_register_duplicate(self, tmp_dir):
        registry = UserRegistry(tmp_dir / "users.json")
        registry.register_user("123", "alice", "Alice")
        dup = registry.register_user("123", "alice2", "Alice2")
        # Should return the existing user, not create a new one
        assert dup.telegram_username == "alice"

    def test_list_users(self, tmp_dir):
        registry = UserRegistry(tmp_dir / "users.json")
        registry.register_user("1", "a", "A")
        registry.register_user("2", "b", "B")

        users = registry.list_users(status="active")
        assert len(users) == 2

    def test_deactivate(self, tmp_dir):
        registry = UserRegistry(tmp_dir / "users.json")
        registry.register_user("1", "a", "A")
        registry.deactivate_user("1")

        active = registry.list_users(status="active")
        assert len(active) == 0

        inactive = registry.list_users(status="inactive")
        assert len(inactive) == 1

    def test_update_last_seen(self, tmp_dir):
        registry = UserRegistry(tmp_dir / "users.json")
        user = registry.register_user("1", "a", "A")
        original_seen = user.last_seen

        registry.update_last_seen("1")
        updated = registry.get_user("1")
        assert updated.last_seen >= original_seen

    def test_get_nonexistent(self, tmp_dir):
        registry = UserRegistry(tmp_dir / "users.json")
        assert registry.get_user("999") is None


# ---- UserConfigStorage ----

class TestUserConfigStorage:
    def test_default_config(self, tmp_dir):
        cfg = UserConfigStorage(tmp_dir / "config.json", user_id="123")
        config = cfg.get_config()

        assert config.user_id == "123"
        assert config.heartbeat_enabled is True
        assert config.timezone == "UTC"
        assert config.quiet_hours_enabled is False
        assert config.quiet_hours_start == "22:00"
        assert config.quiet_hours_end == "08:00"
        assert config.max_context_messages == 50

    def test_update_config(self, tmp_dir):
        cfg = UserConfigStorage(tmp_dir / "config.json", user_id="123")
        cfg.update_config(
            model="claude-3-haiku-20240307",
            heartbeat_enabled=False,
            timezone="Europe/Paris",
            quiet_hours_enabled=True,
        )

        config = cfg.get_config()
        assert config.model == "claude-3-haiku-20240307"
        assert config.heartbeat_enabled is False
        assert config.timezone == "Europe/Paris"
        assert config.quiet_hours_enabled is True

    def test_update_ignores_protected_fields(self, tmp_dir):
        cfg = UserConfigStorage(tmp_dir / "config.json", user_id="123")
        original = cfg.get_config()
        cfg.update_config(user_id="999", created_at="fake")

        config = cfg.get_config()
        assert config.user_id == "123"
        assert config.created_at == original.created_at

    def test_reset_to_defaults(self, tmp_dir):
        cfg = UserConfigStorage(tmp_dir / "config.json", user_id="123")
        cfg.update_config(model="changed", timezone="Europe/Paris", quiet_hours_enabled=True)
        cfg.reset_to_defaults()

        config = cfg.get_config()
        assert config.model != "changed"
        assert config.timezone == "UTC"
        assert config.quiet_hours_enabled is False

    def test_get_config_merges_new_defaults(self, tmp_dir):
        file_path = tmp_dir / "config.json"
        file_path.write_text(json.dumps({
            "user_id": "123",
            "model": "opus",
            "heartbeat_enabled": True,
            "heartbeat_interval_minutes": 15,
            "max_context_messages": 50,
            "created_at": "",
            "updated_at": "",
        }))

        cfg = UserConfigStorage(file_path, user_id="123")
        config = cfg.get_config()

        assert config.timezone == "UTC"
        assert config.quiet_hours_enabled is False


# ---- UserStorageManager ----

class TestUserStorageManager:
    def test_directory_creation(self, tmp_dir, monkeypatch):
        monkeypatch.setattr("src.config.DATA_DIR", tmp_dir)
        mgr = UserStorageManager("user1")

        assert (tmp_dir / "users" / "user1").is_dir()
        assert mgr.messages is not None
        assert mgr.scratchpad is not None
        assert mgr.config is not None

    def test_per_user_isolation(self, tmp_dir, monkeypatch):
        monkeypatch.setattr("src.config.DATA_DIR", tmp_dir)
        mgr1 = UserStorageManager("user1")
        mgr2 = UserStorageManager("user2")

        mgr1.messages.add_message("user", "hello from user1")
        mgr2.messages.add_message("user", "hello from user2")

        msgs1 = mgr1.messages.get_recent_messages()
        msgs2 = mgr2.messages.get_recent_messages()

        assert len(msgs1) == 1
        assert msgs1[0]["content"] == "hello from user1"
        assert len(msgs2) == 1
        assert msgs2[0]["content"] == "hello from user2"


# ---- get_user_storage caching ----

class TestGetUserStorage:
    def test_caching(self, tmp_dir, monkeypatch):
        monkeypatch.setattr("src.config.DATA_DIR", tmp_dir)
        s1 = get_user_storage("test_user")
        s2 = get_user_storage("test_user")
        assert s1 is s2

    def test_different_users(self, tmp_dir, monkeypatch):
        monkeypatch.setattr("src.config.DATA_DIR", tmp_dir)
        s1 = get_user_storage("user_a")
        s2 = get_user_storage("user_b")
        assert s1 is not s2


# ---- MessageStorage / ScratchpadStorage ----

class TestMessageStorage:
    def test_add_and_get(self, tmp_dir):
        ms = MessageStorage(tmp_dir / "messages.json")
        ms.add_message("user", "hello")
        ms.add_message("assistant", "hi there")

        msgs = ms.get_recent_messages()
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["content"] == "hi there"

    def test_limit(self, tmp_dir):
        ms = MessageStorage(tmp_dir / "messages.json")
        for i in range(10):
            ms.add_message("user", f"msg {i}")

        msgs = ms.get_recent_messages(limit=3)
        assert len(msgs) == 3
        assert msgs[0]["content"] == "msg 7"

    def test_clear(self, tmp_dir):
        ms = MessageStorage(tmp_dir / "messages.json")
        ms.add_message("user", "hello")
        ms.clear_messages()
        assert len(ms.get_recent_messages()) == 0


class TestScratchpadStorage:
    def test_add_and_get(self, tmp_dir):
        sp = ScratchpadStorage(tmp_dir / "scratchpad.json")
        sp.add_note("test note")

        notes = sp.get_notes()
        assert len(notes) == 1
        assert notes[0]["note"] == "test note"

    def test_clear(self, tmp_dir):
        sp = ScratchpadStorage(tmp_dir / "scratchpad.json")
        sp.add_note("note1")
        sp.clear_notes()
        assert len(sp.get_notes()) == 0
