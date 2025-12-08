"""JSON storage helpers for messages and scratchpad."""
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import threading
import logging
from dataclasses import dataclass, asdict

from . import config

logger = logging.getLogger(__name__)


class JSONStorage:
    """Thread-safe JSON file storage."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.lock = threading.Lock()
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Create the JSON file with empty structure if it doesn't exist."""
        if not self.file_path.exists():
            with self.lock:
                self.file_path.write_text(json.dumps(self._get_empty_structure(), indent=2))

    def _get_empty_structure(self) -> Dict:
        """Override in subclasses to define empty structure."""
        return {}

    def read(self) -> Dict:
        """Read the entire JSON file."""
        with self.lock:
            with open(self.file_path, 'r') as f:
                return json.load(f)

    def write(self, data: Dict):
        """Write the entire JSON file."""
        with self.lock:
            with open(self.file_path, 'w') as f:
                json.dump(data, f, indent=2)


class MessageStorage(JSONStorage):
    """Storage for conversation messages."""

    def _get_empty_structure(self) -> Dict:
        return {"messages": []}

    def add_message(self, role: str, content: str):
        """Add a message to the conversation history."""
        data = self.read()
        data["messages"].append({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "role": role,
            "content": content
        })
        self.write(data)

    def get_recent_messages(self, limit: int = None) -> List[Dict[str, Any]]:
        """Get recent messages, optionally limited to last N messages."""
        data = self.read()
        messages = data.get("messages", [])
        if limit:
            return messages[-limit:]
        return messages

    def clear_messages(self):
        """Clear all messages (use with caution)."""
        self.write({"messages": []})


class ScratchpadStorage(JSONStorage):
    """Storage for Claude's notes."""

    def _get_empty_structure(self) -> Dict:
        return {"notes": []}

    def add_note(self, note: str):
        """Add a note to the scratchpad."""
        data = self.read()
        data["notes"].append({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "note": note
        })
        self.write(data)

    def get_notes(self) -> List[Dict[str, Any]]:
        """Get all notes."""
        data = self.read()
        return data.get("notes", [])

    def clear_notes(self):
        """Clear all notes (use with caution)."""
        self.write({"notes": []})


# ============================================================================
# Multi-User Storage Classes
# ============================================================================

@dataclass
class User:
    """User data model."""
    user_id: str
    telegram_username: Optional[str]
    telegram_first_name: str
    registered_at: str
    last_seen: str
    status: str = "active"  # "active" | "inactive" | "banned"


@dataclass
class UserConfig:
    """User configuration data model."""
    user_id: str
    model: str = "claude-opus-4-5-20251101"
    heartbeat_enabled: bool = True
    heartbeat_interval_minutes: int = 15
    max_context_messages: int = 50
    created_at: str = ""
    updated_at: str = ""


class UserRegistry(JSONStorage):
    """Manages user registration and metadata."""

    def _get_empty_structure(self) -> Dict:
        return {"users": []}

    def register_user(
        self,
        user_id: str,
        username: Optional[str],
        first_name: str
    ) -> User:
        """Register a new user."""
        data = self.read()

        # Check if user already exists
        for user in data["users"]:
            if user["user_id"] == user_id:
                logger.info(f"User {user_id} already registered")
                return User(**user)

        # Create new user entry
        now = datetime.utcnow().isoformat() + "Z"
        new_user = {
            "user_id": user_id,
            "telegram_username": username,
            "telegram_first_name": first_name,
            "registered_at": now,
            "last_seen": now,
            "status": "active"
        }

        data["users"].append(new_user)
        self.write(data)

        logger.info(f"✨ Registered new user: {user_id} (@{username})")
        return User(**new_user)

    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        data = self.read()
        for user in data["users"]:
            if user["user_id"] == user_id:
                return User(**user)
        return None

    def update_last_seen(self, user_id: str):
        """Update user's last_seen timestamp."""
        data = self.read()
        for user in data["users"]:
            if user["user_id"] == user_id:
                user["last_seen"] = datetime.utcnow().isoformat() + "Z"
                self.write(data)
                return
        logger.warning(f"User {user_id} not found for last_seen update")

    def list_users(self, status: Optional[str] = "active") -> List[User]:
        """List all users, optionally filtered by status."""
        data = self.read()
        users = data.get("users", [])
        if status:
            users = [u for u in users if u.get("status") == status]
        return [User(**u) for u in users]

    def deactivate_user(self, user_id: str):
        """Deactivate a user."""
        data = self.read()
        for user in data["users"]:
            if user["user_id"] == user_id:
                user["status"] = "inactive"
                self.write(data)
                logger.info(f"Deactivated user: {user_id}")
                return
        logger.warning(f"User {user_id} not found for deactivation")


class UserConfigStorage(JSONStorage):
    """Storage for user-specific configuration."""

    def __init__(self, file_path: Path, user_id: str):
        self.user_id = user_id
        super().__init__(file_path)

    def _get_empty_structure(self) -> Dict:
        """Create default config for new user."""
        now = datetime.utcnow().isoformat() + "Z"
        return {
            "user_id": self.user_id,
            "model": config.get_claude_model(),
            "heartbeat_enabled": True,
            "heartbeat_interval_minutes": config.HEARTBEAT_INTERVAL_MINUTES,
            "max_context_messages": config.MAX_CONTEXT_MESSAGES,
            "created_at": now,
            "updated_at": now
        }

    def get_config(self) -> UserConfig:
        """Get user configuration as dataclass."""
        data = self.read()
        return UserConfig(**data)

    def update_config(self, **kwargs):
        """Update specific config fields."""
        data = self.read()

        # Update specified fields
        for key, value in kwargs.items():
            if key in data and key not in ["user_id", "created_at"]:
                data[key] = value

        # Update timestamp
        data["updated_at"] = datetime.utcnow().isoformat() + "Z"

        self.write(data)
        logger.info(f"Updated config for user {self.user_id}: {kwargs}")

    def reset_to_defaults(self):
        """Reset config to default values."""
        self.write(self._get_empty_structure())
        logger.info(f"Reset config to defaults for user {self.user_id}")


class UserStorageManager:
    """Manages storage for a specific user."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.user_dir = config.DATA_DIR / "users" / user_id
        self.user_dir.mkdir(parents=True, exist_ok=True)

        # Create user-specific storage instances
        self.messages = MessageStorage(self.user_dir / "messages.json")
        self.scratchpad = ScratchpadStorage(self.user_dir / "scratchpad.json")
        self.config = UserConfigStorage(
            self.user_dir / "user_config.json",
            user_id=user_id
        )

        logger.debug(f"Initialized storage for user {user_id}")


# Storage cache to avoid re-creating instances
_storage_cache: Dict[str, UserStorageManager] = {}
_cache_lock = threading.Lock()


def get_user_storage(user_id: str) -> UserStorageManager:
    """
    Get or create storage manager for a user (thread-safe, cached).

    Args:
        user_id: User ID (Telegram chat ID as string)

    Returns:
        UserStorageManager instance for the user
    """
    with _cache_lock:
        if user_id not in _storage_cache:
            _storage_cache[user_id] = UserStorageManager(user_id)
        return _storage_cache[user_id]


# Global user registry instance
_user_registry: Optional[UserRegistry] = None


def get_user_registry() -> UserRegistry:
    """Get the user registry (singleton)."""
    global _user_registry
    if _user_registry is None:
        _user_registry = UserRegistry(config.DATA_DIR / "users.json")
    return _user_registry


# ============================================================================
# Legacy Global Storage Instances (deprecated, kept for backwards compatibility)
# ============================================================================
# These will be removed after migration is complete
messages = MessageStorage(config.MESSAGES_FILE)
scratchpad = ScratchpadStorage(config.SCRATCHPAD_FILE)
