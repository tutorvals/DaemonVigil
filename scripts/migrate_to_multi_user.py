#!/usr/bin/env python3
"""
Migrate single-user data to multi-user format.

Prerequisites:
  - Stop Daemon Vigil if running
  - Ensure TELEGRAM_CHAT_ID is set in .env

Usage:
  python scripts/migrate_to_multi_user.py

What it does:
  1. Creates data/users/<chat_id>/ directory
  2. Moves messages.json and scratchpad.json into per-user directory
  3. Creates user_config.json with current settings
  4. Creates data/users.json (user registry)
  5. Adds user_id to all api_usage.jsonl entries
  6. Creates .backup files for rollback
"""

import json
import shutil
import sys
from pathlib import Path
from datetime import datetime
import os

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))

from src import config


def migrate():
    """Perform migration from single-user to multi-user format."""
    print("=" * 60)
    print("Daemon Vigil - Multi-User Migration Script")
    print("=" * 60)
    print()

    data_dir = config.DATA_DIR

    # Get user ID from environment
    user_id = os.getenv("TELEGRAM_CHAT_ID")
    if not user_id or user_id == "None":
        print("❌ ERROR: TELEGRAM_CHAT_ID not set in .env")
        print()
        print("Please set it to your Telegram chat ID before migrating.")
        print("To find your chat ID:")
        print("  1. Message your bot in Telegram")
        print("  2. Check the logs for your chat ID")
        print("  3. Add it to .env file as TELEGRAM_CHAT_ID=<your_id>")
        print()
        return False

    user_id = str(user_id)
    print(f"Migrating data for user ID: {user_id}")
    print()

    # Create users directory
    users_dir = data_dir / "users"
    users_dir.mkdir(exist_ok=True)
    print(f"✅ Created users directory: {users_dir}")

    user_dir = users_dir / user_id
    user_dir.mkdir(exist_ok=True)
    print(f"✅ Created user directory: {user_dir}")
    print()

    # Migrate messages.json
    print("📝 Migrating messages.json...")
    old_messages = data_dir / "messages.json"
    new_messages = user_dir / "messages.json"

    if old_messages.exists():
        shutil.copy(old_messages, new_messages)
        backup_messages = data_dir / "messages.json.backup"
        shutil.move(old_messages, backup_messages)
        print(f"   ✅ Migrated to {new_messages}")
        print(f"   💾 Backup created: {backup_messages}")
    else:
        # Create empty
        new_messages.write_text(json.dumps({"messages": []}, indent=2))
        print(f"   ✅ Created empty messages.json")

    # Migrate scratchpad.json
    print()
    print("📝 Migrating scratchpad.json...")
    old_scratchpad = data_dir / "scratchpad.json"
    new_scratchpad = user_dir / "scratchpad.json"

    if old_scratchpad.exists():
        shutil.copy(old_scratchpad, new_scratchpad)
        backup_scratchpad = data_dir / "scratchpad.json.backup"
        shutil.move(old_scratchpad, backup_scratchpad)
        print(f"   ✅ Migrated to {new_scratchpad}")
        print(f"   💾 Backup created: {backup_scratchpad}")
    else:
        new_scratchpad.write_text(json.dumps({"notes": []}, indent=2))
        print(f"   ✅ Created empty scratchpad.json")

    # Create user_config.json
    print()
    print("⚙️  Creating user_config.json...")
    user_config_file = user_dir / "user_config.json"
    now = datetime.utcnow().isoformat() + "Z"
    user_config = {
        "user_id": user_id,
        "model": config.get_claude_model(),
        "heartbeat_enabled": True,
        "heartbeat_interval_minutes": config.HEARTBEAT_INTERVAL_MINUTES,
        "max_context_messages": config.MAX_CONTEXT_MESSAGES,
        "created_at": now,
        "updated_at": now
    }
    user_config_file.write_text(json.dumps(user_config, indent=2))
    print(f"   ✅ Created {user_config_file}")

    # Create users.json (user registry)
    print()
    print("👥 Creating users.json (user registry)...")
    users_json = data_dir / "users.json"
    users_data = {
        "users": [
            {
                "user_id": user_id,
                "telegram_username": "user",  # Update manually if needed
                "telegram_first_name": "User",
                "registered_at": now,
                "last_seen": now,
                "status": "active"
            }
        ]
    }
    users_json.write_text(json.dumps(users_data, indent=2))
    print(f"   ✅ Created {users_json}")
    print()
    print("   ℹ️  Note: You can manually edit users.json to update username/name")

    # Migrate api_usage.jsonl - add user_id to all entries
    print()
    print("💰 Migrating api_usage.jsonl...")
    old_usage = data_dir / "api_usage.jsonl"

    if old_usage.exists():
        backup_usage = data_dir / "api_usage.jsonl.backup"
        shutil.copy(old_usage, backup_usage)
        print(f"   💾 Backup created: {backup_usage}")

        # Read all lines, add user_id, write back
        lines = []
        updated_count = 0
        error_count = 0

        with open(old_usage, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    # Only add user_id if not already present
                    if "user_id" not in entry:
                        entry["user_id"] = user_id
                        updated_count += 1
                    lines.append(json.dumps(entry) + '\n')
                except json.JSONDecodeError:
                    # Keep malformed lines as-is
                    lines.append(line)
                    error_count += 1

        with open(old_usage, 'w') as f:
            f.writelines(lines)

        print(f"   ✅ Updated {updated_count} entries with user_id")
        if error_count > 0:
            print(f"   ⚠️  {error_count} malformed lines kept as-is")
    else:
        print(f"   ℹ️  No api_usage.jsonl found (will be created on first API call)")

    # Summary
    print()
    print("=" * 60)
    print("✅ Migration complete!")
    print("=" * 60)
    print()
    print("Summary:")
    print(f"  • User directory created: {user_dir}")
    print(f"  • Migrated messages and scratchpad")
    print(f"  • Created user config")
    print(f"  • Created user registry")
    print(f"  • Updated API usage logs")
    print()
    print("Backups created:")
    if old_messages.exists() or (data_dir / "messages.json.backup").exists():
        print(f"  • {data_dir / 'messages.json.backup'}")
    if old_scratchpad.exists() or (data_dir / "scratchpad.json.backup").exists():
        print(f"  • {data_dir / 'scratchpad.json.backup'}")
    if old_usage.exists():
        print(f"  • {data_dir / 'api_usage.jsonl.backup'}")
    print()
    print("Next steps:")
    print("  1. Review the migrated files in data/users/" + user_id)
    print("  2. Start Daemon Vigil normally - it will use the new multi-user system")
    print("  3. Test by sending a message to the bot")
    print("  4. If everything works, you can delete the .backup files")
    print()

    return True


if __name__ == "__main__":
    try:
        success = migrate()
        sys.exit(0 if success else 1)
    except Exception as e:
        print()
        print(f"❌ Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
