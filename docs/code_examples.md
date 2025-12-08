# Multi-User Architecture - Code Examples

This document shows concrete code examples of the transformation from single-user to multi-user architecture.

---

## 1. Storage Layer Transformation

### Current: Global Storage (`src/storage.py`)

```python
# Lines 96-98 (current code)
# Global storage instances
messages = MessageStorage(config.MESSAGES_FILE)
scratchpad = ScratchpadStorage(config.SCRATCHPAD_FILE)

# Usage throughout codebase:
from src import storage
storage.messages.add_message("user", "Hello")
```

**Problem:** All users share the same storage instances.

### Proposed: User-Scoped Storage

```python
# New classes in src/storage.py

class UserStorageManager:
    """Manages storage for a specific user."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.user_dir = config.DATA_DIR / "users" / user_id
        self.user_dir.mkdir(parents=True, exist_ok=True)

        # Create user-specific storage instances
        self.messages = MessageStorage(self.user_dir / "messages.json")
        self.scratchpad = ScratchpadStorage(self.user_dir / "scratchpad.json")
        self.config = UserConfigStorage(self.user_dir / "user_config.json")


# Storage cache to avoid re-creating instances
_storage_cache: Dict[str, UserStorageManager] = {}
_cache_lock = threading.Lock()


def get_user_storage(user_id: str) -> UserStorageManager:
    """Get or create storage manager for a user (thread-safe, cached)."""
    with _cache_lock:
        if user_id not in _storage_cache:
            _storage_cache[user_id] = UserStorageManager(user_id)
        return _storage_cache[user_id]


# Usage throughout codebase:
from src.storage import get_user_storage

user_storage = get_user_storage(user_id)
user_storage.messages.add_message("user", "Hello")
```

---

## 2. User Registry

### New Class: `UserRegistry`

```python
# src/storage.py

class UserRegistry(JSONStorage):
    """Manages user registration and metadata."""

    def _get_empty_structure(self) -> Dict:
        return {"users": []}

    def register_user(
        self,
        user_id: str,
        username: str | None,
        first_name: str
    ) -> Dict:
        """Register a new user."""
        data = self.read()

        # Check if user already exists
        for user in data["users"]:
            if user["user_id"] == user_id:
                return user

        # Create new user entry
        new_user = {
            "user_id": user_id,
            "telegram_username": username,
            "telegram_first_name": first_name,
            "registered_at": datetime.utcnow().isoformat() + "Z",
            "last_seen": datetime.utcnow().isoformat() + "Z",
            "status": "active"
        }

        data["users"].append(new_user)
        self.write(data)

        logger.info(f"Registered new user: {user_id} (@{username})")
        return new_user

    def get_user(self, user_id: str) -> Dict | None:
        """Get user by ID."""
        data = self.read()
        for user in data["users"]:
            if user["user_id"] == user_id:
                return user
        return None

    def update_last_seen(self, user_id: str):
        """Update user's last_seen timestamp."""
        data = self.read()
        for user in data["users"]:
            if user["user_id"] == user_id:
                user["last_seen"] = datetime.utcnow().isoformat() + "Z"
                self.write(data)
                return

    def list_users(self, status: str = "active") -> List[Dict]:
        """List all users, optionally filtered by status."""
        data = self.read()
        if status:
            return [u for u in data["users"] if u.get("status") == status]
        return data["users"]


# Global registry instance
_user_registry = None

def get_user_registry() -> UserRegistry:
    """Get the user registry (singleton)."""
    global _user_registry
    if _user_registry is None:
        _user_registry = UserRegistry(config.DATA_DIR / "users.json")
    return _user_registry
```

---

## 3. User Configuration Storage

### New Class: `UserConfigStorage`

```python
# src/storage.py

@dataclass
class UserConfig:
    """User configuration data class."""
    user_id: str
    model: str = "claude-opus-4-5-20251101"
    heartbeat_enabled: bool = True
    heartbeat_interval_minutes: int = 15
    max_context_messages: int = 50
    created_at: str = ""
    updated_at: str = ""


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
            "model": config.get_claude_model(),  # Inherit from global default
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
            if key in data and key != "user_id":  # Don't allow user_id change
                data[key] = value

        # Update timestamp
        data["updated_at"] = datetime.utcnow().isoformat() + "Z"

        self.write(data)
        logger.info(f"Updated config for user {self.user_id}: {kwargs}")

    def reset_to_defaults(self):
        """Reset config to default values."""
        self.write(self._get_empty_structure())


# Updated UserStorageManager.__init__
def __init__(self, user_id: str):
    self.user_id = user_id
    self.user_dir = config.DATA_DIR / "users" / user_id
    self.user_dir.mkdir(parents=True, exist_ok=True)

    self.messages = MessageStorage(self.user_dir / "messages.json")
    self.scratchpad = ScratchpadStorage(self.user_dir / "scratchpad.json")
    self.config = UserConfigStorage(
        self.user_dir / "user_config.json",
        user_id=user_id  # Pass user_id for default config
    )
```

---

## 4. Telegram Bot Transformation

### Current: `src/telegram_bot.py`

```python
# Lines 40-68 (current code)
async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages."""
    message_text = update.message.text
    chat_id = update.effective_chat.id

    # Check if this is a command
    if message_text.startswith("..."):
        command = message_text[3:].strip()
        handled = await commands.handle_command(command, self, chat_id)
        return

    # Not a command - process normally
    storage.messages.add_message("user", message_text)  # ❌ Global storage

    # Call the callback
    if self.on_user_message_callback:
        await self.on_user_message_callback(message_text, chat_id)
```

### Proposed: User-Aware Telegram Bot

```python
# Modified src/telegram_bot.py

async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages with user context."""
    message_text = update.message.text
    chat_id = update.effective_chat.id
    user_id = str(chat_id)  # ✅ Convert to string for consistency

    # Extract user info
    telegram_user = update.effective_user
    username = telegram_user.username
    first_name = telegram_user.first_name or "Unknown"

    # Auto-register user if new
    user_registry = get_user_registry()
    if not user_registry.get_user(user_id):
        user_registry.register_user(
            user_id=user_id,
            username=username,
            first_name=first_name
        )
        logger.info(f"✨ New user registered: {user_id} (@{username})")

        # Send welcome message
        await self.send_message(
            f"Welcome, {first_name}! I'm Daemon Vigil. "
            f"I'll check in with you periodically. "
            f"Type ...help for commands.",
            chat_id=chat_id
        )

    # Update last seen
    user_registry.update_last_seen(user_id)

    # Check if this is a command
    if message_text.startswith("..."):
        command = message_text[3:].strip()
        # ✅ Pass user_id to command handler
        handled = await commands.handle_command(command, self, user_id)
        return

    # Not a command - process normally
    # ✅ Use user-specific storage
    user_storage = get_user_storage(user_id)
    user_storage.messages.add_message("user", message_text)

    logger.info(f"💬 User {user_id}: {message_text[:50]}...")

    # Call the callback with user_id
    if self.on_user_message_callback:
        # ✅ Changed signature: (message, user_id) instead of (message, chat_id)
        await self.on_user_message_callback(message_text, user_id)
```

---

## 5. Claude Integration Transformation

### Current: `src/claude.py`

```python
# Lines 189-227 (current code - simplified)
async def respond_to_user(user_message: str, telegram_bot) -> None:
    """Respond to a user message."""

    # Load recent messages from global storage
    recent_messages = storage.messages.get_recent_messages(
        config.MAX_CONTEXT_MESSAGES
    )  # ❌ Global storage

    # Load scratchpad notes from global storage
    notes = storage.scratchpad.get_notes()  # ❌ Global storage

    # Use global model config
    model = config.get_claude_model()  # ❌ Global config

    # Call Claude...
    response = client.messages.create(model=model, ...)

    # Track usage without user_id
    usage_data = usage_tracker.calculate_cost(...)
    usage_data["request_type"] = "user_response"
    # ❌ No user_id in usage data
    usage_tracker.log_api_usage(usage_data)

    # Send response
    await telegram_bot.send_message(response_text)
    storage.messages.add_message("assistant", response_text)  # ❌ Global
```

### Proposed: User-Aware Claude Integration

```python
# Modified src/claude.py

async def respond_to_user(
    user_message: str,
    telegram_bot,
    user_id: str,                     # ✅ NEW
    user_storage: UserStorageManager,  # ✅ NEW
    user_config: UserConfig            # ✅ NEW
) -> None:
    """Respond to a user message with full user context."""

    logger.info(f"🤖 Responding to user {user_id}: {user_message[:50]}...")

    # ✅ Load user's recent messages (not global)
    recent_messages = user_storage.messages.get_recent_messages(
        user_config.max_context_messages
    )

    # ✅ Load user's scratchpad notes
    notes = user_storage.scratchpad.get_notes()

    # Build conversation for Claude with timestamps
    messages = []
    for msg in recent_messages:
        timestamp = format_timestamp(msg["timestamp"])
        content_with_time = f"[{timestamp}] {msg['content']}"
        messages.append({
            "role": msg["role"],
            "content": content_with_time
        })

    # Build system prompt with context
    context_parts = [f"## Current Time: {get_current_time_str()}", ""]

    if notes:
        context_parts.append("## Your Notes (Scratchpad):")
        for note in notes[-10:]:
            timestamp = format_timestamp(note['timestamp'])
            context_parts.append(f"- [{timestamp}] {note['note']}")
        context_parts.append("")

    system_prompt = load_system_prompt()
    full_system_prompt = f"{system_prompt}\n\n" + "\n".join(context_parts)

    # ✅ Use user's preferred model
    model = user_config.model

    try:
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            system=full_system_prompt,
            messages=messages
        )

        # ✅ Track usage WITH user_id
        usage_data = usage_tracker.calculate_cost(
            model=model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens
        )
        usage_data["request_type"] = "user_response"
        usage_data["user_id"] = user_id  # ✅ Include user_id
        usage_data["user_message_preview"] = user_message[:50]
        usage_tracker.log_api_usage(usage_data)

        logger.info(
            f"💰 Cost for user {user_id}: ${usage_data['total_cost']:.6f} "
            f"({response.usage.input_tokens} in, {response.usage.output_tokens} out)"
        )

        # Extract response
        response_text = ""
        for block in response.content:
            if block.type == "text":
                response_text += block.text

        if response_text:
            # ✅ Send to specific user (not hardcoded chat_id)
            await telegram_bot.send_message(response_text, chat_id=int(user_id))

            # ✅ Log to user's conversation history
            user_storage.messages.add_message("assistant", response_text)
        else:
            logger.warning(f"Empty response for user {user_id}")

    except Exception as e:
        logger.error(f"Error responding to user {user_id}: {e}", exc_info=True)
        raise


# Similar transformation for process_heartbeat():
async def process_heartbeat(
    telegram_bot,
    user_id: str,                     # ✅ NEW
    user_storage: UserStorageManager,  # ✅ NEW
    user_config: UserConfig,           # ✅ NEW
    debug: bool = False
) -> dict:
    """Process heartbeat for a specific user."""

    logger.info(f"💓 Heartbeat for user {user_id}")

    # ✅ Load user's context
    recent_messages = user_storage.messages.get_recent_messages(
        user_config.max_context_messages
    )
    notes = user_storage.scratchpad.get_notes()

    # Build context and call Claude...
    model = user_config.model
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=full_system_prompt,
        messages=messages,
        tools=TOOLS
    )

    # ✅ Track usage with user_id
    usage_data = usage_tracker.calculate_cost(...)
    usage_data["request_type"] = "heartbeat"
    usage_data["user_id"] = user_id
    usage_tracker.log_api_usage(usage_data)

    # If Claude decided to send a message...
    if message:
        await telegram_bot.send_message(message, chat_id=int(user_id))
        user_storage.messages.add_message("assistant", message)

    return result
```

---

## 6. Multi-User Scheduler

### Current: `src/scheduler.py`

```python
# Current: Single scheduler for all users
class HeartbeatScheduler:
    def __init__(self, telegram_bot):
        self.telegram_bot = telegram_bot
        self.scheduler = AsyncIOScheduler()
        self.enabled = True  # ❌ Global enabled/disabled state

    async def heartbeat_job(self):
        """Single job for all users."""
        if not self.enabled:
            return

        # ❌ No user context - processes for hardcoded TELEGRAM_CHAT_ID
        await claude.process_heartbeat(self.telegram_bot)

    def start(self):
        interval_minutes = config.HEARTBEAT_INTERVAL_MINUTES  # ❌ Global
        self.scheduler.add_job(
            self.heartbeat_job,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id='heartbeat',  # ❌ Single job
            # ...
        )
```

### Proposed: Multi-User Scheduler

```python
# New: src/scheduler.py

class MultiUserHeartbeatScheduler:
    """Manages heartbeat schedules for multiple users."""

    def __init__(self, telegram_bot):
        self.telegram_bot = telegram_bot
        self.scheduler = AsyncIOScheduler()

        # ✅ Per-user enabled state
        self.user_states: Dict[str, bool] = {}
        self.state_lock = threading.Lock()

    async def heartbeat_job(self, user_id: str):
        """
        Heartbeat job for a SPECIFIC user.

        Args:
            user_id: The user to process heartbeat for
        """
        try:
            logger.info(f"💓 Heartbeat job triggered for user {user_id}")

            # ✅ Check if enabled for THIS user
            if not self.is_enabled(user_id):
                logger.info(f"Heartbeat disabled for user {user_id}, skipping")
                return

            # ✅ Load user-specific storage and config
            user_storage = get_user_storage(user_id)
            user_config = user_storage.config.get_config()

            # ✅ Process heartbeat with user context
            await claude.process_heartbeat(
                telegram_bot=self.telegram_bot,
                user_id=user_id,
                user_storage=user_storage,
                user_config=user_config
            )

            logger.info(f"✅ Heartbeat completed for user {user_id}")

        except Exception as e:
            logger.error(f"❌ Error in heartbeat for user {user_id}: {e}", exc_info=True)

    def add_user(
        self,
        user_id: str,
        interval_minutes: int = 15,
        enabled: bool = True
    ):
        """
        Add a user to the scheduler with their own interval.

        Args:
            user_id: User to add
            interval_minutes: Heartbeat interval for this user
            enabled: Whether heartbeats are enabled for this user
        """
        job_id = f"heartbeat_{user_id}"  # ✅ Unique job ID per user

        self.scheduler.add_job(
            self.heartbeat_job,
            trigger=IntervalTrigger(minutes=interval_minutes),
            args=[user_id],  # ✅ Pass user_id to job
            id=job_id,
            replace_existing=True,
            max_instances=1,
            coalesce=True
        )

        with self.state_lock:
            self.user_states[user_id] = enabled

        logger.info(
            f"✅ Added user {user_id} to scheduler "
            f"(interval: {interval_minutes}m, enabled: {enabled})"
        )

    def remove_user(self, user_id: str):
        """Remove a user from the scheduler."""
        job_id = f"heartbeat_{user_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed user {user_id} from scheduler")

        with self.state_lock:
            self.user_states.pop(user_id, None)

    def pause_user(self, user_id: str):
        """Pause heartbeats for a specific user (job continues, but skipped)."""
        with self.state_lock:
            self.user_states[user_id] = False
        logger.info(f"⏸️  Paused heartbeats for user {user_id}")

    def resume_user(self, user_id: str):
        """Resume heartbeats for a specific user."""
        with self.state_lock:
            self.user_states[user_id] = True
        logger.info(f"▶️  Resumed heartbeats for user {user_id}")

    def is_enabled(self, user_id: str) -> bool:
        """Check if heartbeats are enabled for a user."""
        with self.state_lock:
            return self.user_states.get(user_id, True)

    def get_user_status(self, user_id: str) -> dict:
        """Get scheduler status for a specific user."""
        job_id = f"heartbeat_{user_id}"
        job = self.scheduler.get_job(job_id)

        return {
            "enabled": self.is_enabled(user_id),
            "next_run": job.next_run_time if job else None,
            "job_exists": job is not None
        }

    def start(self):
        """Start scheduler and load all active users."""
        logger.info("🚀 Starting multi-user scheduler...")

        # ✅ Load all registered users from user registry
        user_registry = get_user_registry()
        active_users = user_registry.list_users(status="active")

        for user_data in active_users:
            user_id = user_data["user_id"]

            # Load user's config
            user_storage = get_user_storage(user_id)
            user_config = user_storage.config.get_config()

            # Add user with their custom interval and enabled state
            self.add_user(
                user_id=user_id,
                interval_minutes=user_config.heartbeat_interval_minutes,
                enabled=user_config.heartbeat_enabled
            )

        self.scheduler.start()
        logger.info(f"✅ Multi-user scheduler started with {len(active_users)} users")

    def stop(self):
        """Stop the scheduler."""
        logger.info("Stopping multi-user scheduler...")
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")
```

---

## 7. Main Application Transformation

### Current: `main.py`

```python
# Current code (simplified)
class DaemonVigil:
    def __init__(self):
        self.bot = TelegramBot(on_user_message_callback=self.on_user_message)
        self.scheduler = HeartbeatScheduler(self.bot)  # ❌ Single-user

    async def on_user_message(self, message: str, chat_id: int):
        """Handle user message - no user context."""
        await claude.respond_to_user(
            user_message=message,
            telegram_bot=self.bot
        )  # ❌ No user_id passed

    async def start(self):
        await self.bot.start()
        self.scheduler.start()  # ❌ Starts single job
```

### Proposed: Multi-User Main Application

```python
# Modified main.py

from src.scheduler import MultiUserHeartbeatScheduler  # ✅ New import
from src.storage import get_user_storage  # ✅ New import

class DaemonVigil:
    _instance = None

    def __init__(self):
        logger.info("🔷 Initializing Daemon Vigil (Multi-User)")

        # Initialize Telegram bot with user-aware callback
        self.bot = TelegramBot(on_user_message_callback=self.on_user_message)

        # ✅ Initialize multi-user scheduler
        self.scheduler = MultiUserHeartbeatScheduler(self.bot)

        DaemonVigil._instance = self

    async def on_user_message(self, message: str, user_id: str):
        """
        Handle user message with full user context.

        Args:
            message: The message text
            user_id: The user ID (Telegram chat ID as string)
        """
        try:
            # ✅ Get user-specific storage and config
            user_storage = get_user_storage(user_id)
            user_config = user_storage.config.get_config()

            logger.info(f"📨 Processing message from user {user_id}")

            # ✅ Respond with user context
            await claude.respond_to_user(
                user_message=message,
                telegram_bot=self.bot,
                user_id=user_id,
                user_storage=user_storage,
                user_config=user_config
            )

        except Exception as e:
            logger.error(f"❌ Error responding to user {user_id}: {e}", exc_info=True)

            # Send error message to user
            try:
                await self.bot.send_message(
                    "Sorry, I encountered an error processing your message. "
                    "Please try again or contact support.",
                    chat_id=int(user_id)
                )
            except:
                pass  # Best effort

    async def start(self):
        """Start the multi-user daemon."""
        logger.info("🚀 Starting Daemon Vigil (Multi-User)...")

        # Start Telegram bot (accepts messages from any user)
        await self.bot.start()

        # ✅ Start multi-user scheduler (loads all active users)
        self.scheduler.start()

        logger.info("✅ Daemon Vigil is running (Multi-User Mode)")
        logger.info("📡 Accepting messages from any Telegram user")
        logger.info("💓 Heartbeats active for all registered users")
        logger.info("Press Ctrl+C to stop")

    async def stop(self):
        """Stop the daemon gracefully."""
        logger.info("🛑 Stopping Daemon Vigil...")

        self.scheduler.stop()
        await self.bot.stop()

        logger.info("✅ Daemon Vigil stopped")

    @classmethod
    def get_instance(cls):
        """Get the singleton instance."""
        return cls._instance
```

---

## 8. Usage Tracker Transformation

### Current: `src/usage_tracker.py`

```python
# Current (lines 51-59)
def log_api_usage(usage_data: Dict) -> None:
    """Log API usage to JSONL file."""
    with open(USAGE_FILE, 'a') as f:
        f.write(json.dumps(usage_data) + '\n')
    # ❌ No user_id in usage_data

# Current (lines 62-112)
def get_usage_stats(days: int) -> Dict:
    """Get usage statistics for the last N days."""
    # ❌ Returns stats for ALL users combined (no filtering)
    # ...
    for line in f:
        entry = json.loads(line)
        # No user_id check
        total_cost += entry["total_cost"]
    # ...
```

### Proposed: User-Aware Usage Tracker

```python
# Modified src/usage_tracker.py

def log_api_usage(usage_data: Dict) -> None:
    """
    Log API usage to JSONL file.

    Args:
        usage_data: Must include 'user_id' field for per-user tracking
    """
    # ✅ Validate user_id presence
    if "user_id" not in usage_data:
        logger.warning("⚠️  Usage data missing user_id - cannot log properly")
        # Still log, but flag it
        usage_data["user_id"] = "unknown"

    with open(USAGE_FILE, 'a') as f:
        f.write(json.dumps(usage_data) + '\n')


def get_user_usage_stats(user_id: str, days: int) -> Dict:
    """
    Get usage statistics for a SPECIFIC user over last N days.

    Args:
        user_id: User ID to filter by
        days: Number of days to look back

    Returns:
        dict with aggregated usage statistics for that user
    """
    if not USAGE_FILE.exists():
        return {
            "user_id": user_id,
            "total_cost": 0.0,
            "total_tokens": 0,
            "request_count": 0,
            "input_tokens": 0,
            "output_tokens": 0
        }

    from datetime import timezone
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0.0
    request_count = 0

    with open(USAGE_FILE, 'r') as f:
        for line in f:
            try:
                entry = json.loads(line)

                # ✅ Filter by user_id
                if entry.get("user_id") != user_id:
                    continue

                entry_time = datetime.fromisoformat(
                    entry["timestamp"].replace('Z', '+00:00')
                )

                if entry_time < cutoff_date:
                    continue

                total_input_tokens += entry["input_tokens"]
                total_output_tokens += entry["output_tokens"]
                total_cost += entry["total_cost"]
                request_count += 1

            except (json.JSONDecodeError, KeyError, ValueError):
                continue

    return {
        "user_id": user_id,
        "total_cost": round(total_cost, 4),
        "total_tokens": total_input_tokens + total_output_tokens,
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "request_count": request_count
    }


def get_all_users_usage_stats(days: int) -> List[Dict]:
    """
    Get usage statistics for ALL users (admin function).

    Args:
        days: Number of days to look back

    Returns:
        List of dicts with per-user stats, sorted by cost descending
    """
    if not USAGE_FILE.exists():
        return []

    from datetime import timezone
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    # ✅ Aggregate stats by user_id
    user_stats = defaultdict(lambda: {
        "total_cost": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
        "request_count": 0
    })

    with open(USAGE_FILE, 'r') as f:
        for line in f:
            try:
                entry = json.loads(line)
                user_id = entry.get("user_id")

                if not user_id or user_id == "unknown":
                    continue

                entry_time = datetime.fromisoformat(
                    entry["timestamp"].replace('Z', '+00:00')
                )

                if entry_time < cutoff_date:
                    continue

                user_stats[user_id]["total_cost"] += entry["total_cost"]
                user_stats[user_id]["input_tokens"] += entry["input_tokens"]
                user_stats[user_id]["output_tokens"] += entry["output_tokens"]
                user_stats[user_id]["request_count"] += 1

            except (json.JSONDecodeError, KeyError, ValueError):
                continue

    # Convert to list and sort by cost
    result = []
    for user_id, stats in user_stats.items():
        result.append({
            "user_id": user_id,
            "total_cost": round(stats["total_cost"], 4),
            "total_tokens": stats["input_tokens"] + stats["output_tokens"],
            "input_tokens": stats["input_tokens"],
            "output_tokens": stats["output_tokens"],
            "request_count": stats["request_count"]
        })

    result.sort(key=lambda x: x["total_cost"], reverse=True)
    return result


# ✅ Update format_usage_report to accept user_id
def format_usage_report(user_id: str) -> str:
    """
    Format a usage report for a SPECIFIC user.

    Args:
        user_id: User ID to generate report for

    Returns:
        Formatted string with usage statistics for that user
    """
    # ✅ Get user-specific storage and config
    user_storage = get_user_storage(user_id)
    user_config = user_storage.config.get_config()

    # ✅ Get user-specific usage stats
    today_stats = get_user_usage_stats(user_id, 1)
    week_stats = get_user_usage_stats(user_id, 7)
    month_stats = get_user_usage_stats(user_id, 30)

    report = "📊 Status Report\n\n"
    report += f"Model: {user_config.model}\n\n"

    # Heartbeat status (from scheduler)
    app = DaemonVigil.get_instance()
    if app and app.scheduler:
        status = app.scheduler.get_user_status(user_id)  # ✅ User-specific
        report += "💓 Heartbeat:\n"
        report += f"State: {'✅ Enabled' if status['enabled'] else '🔇 Disabled'}\n"
        report += f"Interval: {user_config.heartbeat_interval_minutes} minutes\n"
        if status['next_run']:
            report += f"Next run: {status['next_run'].strftime('%H:%M:%S UTC')}\n"
        report += "\n"

    # ✅ User-specific context information
    messages = user_storage.messages.get_recent_messages()
    notes = user_storage.scratchpad.get_notes()

    report += "📚 Context:\n"
    report += f"Messages in history: {len(messages)}\n"
    report += f"Scratchpad notes: {len(notes)}\n"

    if notes:
        last_note = notes[-1]
        note_preview = last_note['note']
        if len(note_preview) > 80:
            note_preview = note_preview[:77] + "..."
        report += f"Last note: {note_preview}\n"

    report += "\n💰 API Costs (Your Usage Only):\n"

    if today_stats["request_count"] == 0:
        report += "No API usage recorded yet\n"
    else:
        report += f"Today:      ${today_stats['total_cost']:.4f} ({today_stats['request_count']} requests)\n"
        report += f"This Week:  ${week_stats['total_cost']:.4f} ({week_stats['request_count']} requests)\n"
        report += f"This Month: ${month_stats['total_cost']:.4f} ({month_stats['request_count']} requests)\n"

        report += "\n📈 Usage Today:\n"
        report += f"Total tokens: {today_stats['total_tokens']:,} "
        report += f"({today_stats['input_tokens']:,} in, {today_stats['output_tokens']:,} out)"

    return report
```

---

## 9. Commands Transformation

### Current: `src/commands.py`

```python
# Current (simplified)
async def handle_command(command: str, bot, chat_id: int) -> bool:
    """Handle special commands."""
    parts = command.split()
    cmd = parts[0].lower()

    if cmd == "status":
        # ❌ Global report (all users combined)
        report = usage_tracker.format_usage_report()
        await bot.send_message(report, chat_id=chat_id)
        return True

    elif cmd == "model":
        # ❌ Changes global config
        new_model = parts[1]
        config.set_claude_model(new_model)
        await bot.send_message(f"Model updated to: {new_model}", chat_id=chat_id)
        return True
```

### Proposed: User-Aware Commands

```python
# Modified src/commands.py

async def handle_command(command: str, bot, user_id: str) -> bool:
    """
    Handle special commands that start with '...'

    Args:
        command: Command string without the '...' prefix
        bot: TelegramBot instance
        user_id: User ID executing the command (✅ NEW)

    Returns:
        True if command was handled, False if unknown
    """
    parts = command.split()
    if not parts:
        return False

    cmd = parts[0].lower()

    # ✅ Get user-specific storage
    user_storage = get_user_storage(user_id)
    user_config = user_storage.config.get_config()

    if cmd == "status":
        # ✅ Generate report for THIS user only
        report = usage_tracker.format_usage_report(user_id)
        await bot.send_message(report, chat_id=int(user_id))
        return True

    elif cmd == "model":
        if len(parts) < 2:
            # Show current model for THIS user
            await bot.send_message(
                f"Your current model: {user_config.model}\n\n"
                f"Available models:\n"
                f"- claude-opus-4-5-20251101 (most capable)\n"
                f"- claude-sonnet-4-5-20250929 (balanced)\n"
                f"- claude-3-5-haiku-20241022 (fast)\n\n"
                f"Usage: ...model <model_name>",
                chat_id=int(user_id)
            )
            return True

        new_model = parts[1]

        # ✅ Update THIS user's config only
        user_storage.config.update_config(model=new_model)

        await bot.send_message(
            f"✅ Your model updated to: {new_model}",
            chat_id=int(user_id)
        )
        return True

    elif cmd == "heartbeat":
        if len(parts) < 2:
            # Show status for THIS user
            app = DaemonVigil.get_instance()
            if app and app.scheduler:
                status = app.scheduler.get_user_status(user_id)
                msg = f"💓 Your heartbeat status:\n"
                msg += f"State: {'✅ Enabled' if status['enabled'] else '🔇 Disabled'}\n"
                msg += f"Interval: {user_config.heartbeat_interval_minutes} minutes\n"
                if status['next_run']:
                    msg += f"Next run: {status['next_run'].strftime('%H:%M:%S UTC')}"
                await bot.send_message(msg, chat_id=int(user_id))
            return True

        subcmd = parts[1].lower()

        app = DaemonVigil.get_instance()
        if not app or not app.scheduler:
            await bot.send_message("Scheduler not available", chat_id=int(user_id))
            return True

        if subcmd == "on":
            # ✅ Enable for THIS user only
            app.scheduler.resume_user(user_id)
            user_storage.config.update_config(heartbeat_enabled=True)
            await bot.send_message("✅ Heartbeat enabled", chat_id=int(user_id))
            return True

        elif subcmd == "off":
            # ✅ Disable for THIS user only
            app.scheduler.pause_user(user_id)
            user_storage.config.update_config(heartbeat_enabled=False)
            await bot.send_message("🔇 Heartbeat disabled", chat_id=int(user_id))
            return True

        elif subcmd == "test":
            # ✅ Test heartbeat for THIS user
            await bot.send_message("🧪 Testing heartbeat...", chat_id=int(user_id))

            result = await claude.process_heartbeat(
                telegram_bot=bot,
                user_id=user_id,
                user_storage=user_storage,
                user_config=user_config,
                debug=True
            )

            if result["error"]:
                await bot.send_message(
                    f"❌ Error: {result['error']}",
                    chat_id=int(user_id)
                )
            elif result["tool_called"]:
                await bot.send_message(
                    f"✅ Heartbeat test complete. Claude decided to send message:\n\n"
                    f"{result['message_sent']}",
                    chat_id=int(user_id)
                )
            else:
                await bot.send_message(
                    "✅ Heartbeat test complete. Claude chose not to send a message.",
                    chat_id=int(user_id)
                )
            return True

    return False
```

---

## Summary: Key Transformation Patterns

1. **Global → User-Scoped Storage**
   - `storage.messages` → `get_user_storage(user_id).messages`
   - `storage.scratchpad` → `get_user_storage(user_id).scratchpad`

2. **Global → User-Specific Config**
   - `config.get_claude_model()` → `user_config.model`
   - `config.HEARTBEAT_INTERVAL_MINUTES` → `user_config.heartbeat_interval_minutes`

3. **Function Signatures: Add User Context**
   - Old: `async def respond_to_user(message, bot)`
   - New: `async def respond_to_user(message, bot, user_id, user_storage, user_config)`

4. **Callbacks: Pass user_id**
   - Old: `callback(message, chat_id)`
   - New: `callback(message, user_id)`

5. **Usage Tracking: Include user_id**
   - Old: `usage_data = {"cost": ..., "tokens": ...}`
   - New: `usage_data = {"cost": ..., "tokens": ..., "user_id": user_id}`

6. **Scheduler: Per-User Jobs**
   - Old: Single job `"heartbeat"`
   - New: Multiple jobs `"heartbeat_{user_id}"`

7. **Auto-Registration**
   - New users automatically registered on first message
   - User directory created on-demand
