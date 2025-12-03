"""JSON storage helpers for messages and scratchpad."""
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import threading

from . import config


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


# Global storage instances
messages = MessageStorage(config.MESSAGES_FILE)
scratchpad = ScratchpadStorage(config.SCRATCHPAD_FILE)
