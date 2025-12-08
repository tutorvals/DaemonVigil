# Multi-User Architecture Proposal
## DaemonVigil - Supporting Multiple Users

**Date:** 2025-12-08
**Branch:** `claude/multi-user-architecture-01JmVKRM2XUhkXFGe5Djx5u2`

---

## Table of Contents
1. [Current Architecture Analysis](#current-architecture-analysis)
2. [Multi-User Requirements](#multi-user-requirements)
3. [Proposed Architecture](#proposed-architecture)
4. [Data Model Changes](#data-model-changes)
5. [Component Refactoring Plan](#component-refactoring-plan)
6. [Migration Strategy](#migration-strategy)
7. [Implementation Phases](#implementation-phases)
8. [Security Considerations](#security-considerations)

---

## 1. Current Architecture Analysis

### 1.1 Single-User Design
The current system is designed for a single user ("Vals") with:
- Hardcoded `TELEGRAM_CHAT_ID` in environment variables
- Global storage instances (messages, scratchpad)
- Single heartbeat scheduler
- No user identification in data structures

### 1.2 Data Storage Patterns

#### Conversations (`data/messages.json`)
```json
{
  "messages": [
    {
      "timestamp": "2025-12-08T10:30:42Z",
      "role": "user",
      "content": "Hey, how's it going?"
    }
  ]
}
```
**Issues for Multi-User:**
- No `user_id` field
- Single shared file
- No user isolation

#### API Usage (`data/api_usage.jsonl`)
```jsonl
{"input_tokens": 1234, "output_tokens": 567, "total_cost": 0.012207, "model": "claude-opus-4-5-20251101", "timestamp": "2025-12-08T10:45:00Z", "request_type": "heartbeat"}
```
**Issues for Multi-User:**
- No `user_id` field
- Cannot track costs per user
- Cannot generate per-user usage reports

#### Scratchpad (`data/scratchpad.json`)
```json
{
  "notes": [
    {
      "timestamp": "2025-12-08T10:45:00Z",
      "note": "Vals mentioned working on daemonVigil architecture"
    }
  ]
}
```
**Issues for Multi-User:**
- No `user_id` field
- Single shared file
- No user-specific notes

### 1.3 Component Dependencies

```
main.py (DaemonVigil)
├── TelegramBot (telegram_bot.py)
│   ├── Uses: storage.messages (global)
│   └── Sends to: config.TELEGRAM_CHAT_ID (single user)
├── HeartbeatScheduler (scheduler.py)
│   ├── Single scheduler instance
│   └── Calls: claude.process_heartbeat()
└── Claude (claude.py)
    ├── Uses: storage.messages (global)
    ├── Uses: storage.scratchpad (global)
    └── Logs: usage_tracker (no user_id)
```

**Key Issues:**
1. Global storage instances prevent per-user data isolation
2. Single scheduler cannot manage multiple users' heartbeat schedules
3. No user context passed through the call chain
4. Commands (commands.py) operate on global state

---

## 2. Multi-User Requirements

### 2.1 Functional Requirements
1. **User Isolation:** Each user has separate conversations, notes, and settings
2. **Per-User API Costs:** Track usage and costs per user for billing/monitoring
3. **Independent Heartbeats:** Each user has their own heartbeat schedule and enabled/disabled state
4. **Per-User Configuration:** Model preferences, heartbeat intervals can differ per user
5. **Concurrent Operations:** Multiple users can interact simultaneously without conflicts
6. **User Registration:** System must identify and register new Telegram users

### 2.2 Non-Functional Requirements
1. **Data Consistency:** Thread-safe operations for concurrent user access
2. **Performance:** Should scale to 10-100 users on single server
3. **Backwards Compatibility:** Migrate existing single-user data to multi-user format
4. **Monitoring:** Admin visibility into all users' status and costs
5. **Privacy:** Users cannot access each other's data

### 2.3 Out of Scope (for initial implementation)
- User authentication (Telegram ID is sufficient)
- User permissions/roles
- Cross-user features (user groups, sharing)
- Database migration (keep file-based for now)
- Multi-server deployment

---

## 3. Proposed Architecture

### 3.1 Architecture Options

#### Option A: Separate Files Per User (Recommended)
```
data/
├── users/
│   ├── 123456789/              # Telegram chat ID
│   │   ├── messages.json       # User's conversation
│   │   ├── scratchpad.json     # User's notes
│   │   └── config.json         # User's settings
│   ├── 987654321/
│   │   ├── messages.json
│   │   ├── scratchpad.json
│   │   └── config.json
├── api_usage.jsonl             # Shared, with user_id field
└── users.json                  # User registry
```

**Pros:**
- Clean separation of user data
- Easy to backup/restore per user
- Simple file permissions model
- Scales well (filesystem handles directories efficiently)
- Easy to delete user data (GDPR compliance)

**Cons:**
- More files to manage
- Slightly more complex file I/O

#### Option B: Shared Files with User ID Fields
```
data/
├── messages.json    # Contains all users' messages with user_id
├── scratchpad.json  # Contains all users' notes with user_id
├── api_usage.jsonl  # Contains all users' usage with user_id
└── users.json       # User registry
```

**Example messages.json:**
```json
{
  "123456789": {
    "messages": [...]
  },
  "987654321": {
    "messages": [...]
  }
}
```

**Pros:**
- Fewer files
- Atomic writes across all users
- Easier to implement global operations

**Cons:**
- File grows unbounded (not scalable)
- Higher lock contention (all users share same file lock)
- Cannot selectively back up/restore users
- Risk of data corruption affects all users

#### Option C: Hybrid (Separate Conversations, Shared Usage)
```
data/
├── users/
│   ├── 123456789/
│   │   ├── messages.json
│   │   └── scratchpad.json
├── user_configs.json   # All user settings in one file
├── api_usage.jsonl     # Shared, with user_id
└── users.json          # User registry
```

**Pros:**
- Balance between isolation and shared resources
- API usage naturally shared (for admin reporting)
- User configs centralized (easier to update defaults)

**Cons:**
- Mixed patterns (some data separated, some shared)
- Less consistent than Option A

### 3.2 Recommended Architecture: Option A (Separate Files)

#### Data Structure
```
data/
├── users/
│   ├── 123456789/
│   │   ├── messages.json       # User's conversation history
│   │   ├── scratchpad.json     # Claude's notes about user
│   │   └── user_config.json    # User-specific settings
│   ├── 987654321/
│   │   ├── messages.json
│   │   ├── scratchpad.json
│   │   └── user_config.json
├── api_usage.jsonl             # Global, with user_id field
├── users.json                  # User registry/metadata
└── scheduler_state.json        # Heartbeat states (NEW)
```

#### User Registry (`users.json`)
```json
{
  "users": [
    {
      "user_id": "123456789",
      "telegram_username": "vals",
      "telegram_first_name": "Vals",
      "registered_at": "2025-12-08T10:00:00Z",
      "last_seen": "2025-12-08T15:30:00Z",
      "status": "active"
    }
  ]
}
```

#### User Config (`users/{user_id}/user_config.json`)
```json
{
  "user_id": "123456789",
  "model": "claude-opus-4-5-20251101",
  "heartbeat_enabled": true,
  "heartbeat_interval_minutes": 15,
  "max_context_messages": 50,
  "created_at": "2025-12-08T10:00:00Z",
  "updated_at": "2025-12-08T15:30:00Z"
}
```

#### API Usage (Enhanced)
```jsonl
{"user_id": "123456789", "input_tokens": 1234, "output_tokens": 567, "total_cost": 0.012207, "model": "claude-opus-4-5-20251101", "timestamp": "2025-12-08T10:45:00Z", "request_type": "heartbeat"}
{"user_id": "987654321", "input_tokens": 890, "output_tokens": 234, "total_cost": 0.00618, "model": "claude-sonnet-4-5-20250929", "timestamp": "2025-12-08T11:00:00Z", "request_type": "user_response"}
```

#### Scheduler State (`scheduler_state.json`) - NEW
```json
{
  "123456789": {
    "enabled": true,
    "last_run": "2025-12-08T15:30:00Z",
    "next_run": "2025-12-08T15:45:00Z"
  },
  "987654321": {
    "enabled": false,
    "last_run": "2025-12-08T14:00:00Z",
    "next_run": null
  }
}
```

---

## 4. Data Model Changes

### 4.1 New Data Structures

#### User Model
```python
@dataclass
class User:
    user_id: str                    # Telegram chat ID (as string)
    telegram_username: str | None
    telegram_first_name: str
    registered_at: str              # ISO timestamp
    last_seen: str                  # ISO timestamp
    status: str                     # "active" | "inactive" | "banned"
```

#### User Config Model
```python
@dataclass
class UserConfig:
    user_id: str
    model: str = "claude-opus-4-5-20251101"
    heartbeat_enabled: bool = True
    heartbeat_interval_minutes: int = 15
    max_context_messages: int = 50
    created_at: str
    updated_at: str
```

### 4.2 Storage Layer Changes

#### Current (Global)
```python
# src/storage.py (lines 96-98)
messages = MessageStorage(config.MESSAGES_FILE)
scratchpad = ScratchpadStorage(config.SCRATCHPAD_FILE)
```

#### Proposed (User-Scoped)
```python
# src/storage.py
class UserStorageManager:
    """Manages storage for a specific user."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.user_dir = config.DATA_DIR / "users" / user_id
        self.user_dir.mkdir(parents=True, exist_ok=True)

        self.messages = MessageStorage(self.user_dir / "messages.json")
        self.scratchpad = ScratchpadStorage(self.user_dir / "scratchpad.json")
        self.config = UserConfigStorage(self.user_dir / "user_config.json")

# Global storage cache
_storage_cache: Dict[str, UserStorageManager] = {}
_cache_lock = threading.Lock()

def get_user_storage(user_id: str) -> UserStorageManager:
    """Get or create storage for a user (cached)."""
    with _cache_lock:
        if user_id not in _storage_cache:
            _storage_cache[user_id] = UserStorageManager(user_id)
        return _storage_cache[user_id]
```

### 4.3 Enhanced Message Structure
Add `user_id` to all time-series data for auditability:

```python
# In MessageStorage.add_message()
data["messages"].append({
    "timestamp": datetime.utcnow().isoformat() + "Z",
    "role": role,
    "content": content,
    "user_id": self.user_id  # NEW: for audit trail
})
```

---

## 5. Component Refactoring Plan

### 5.1 Storage Layer (`src/storage.py`)

#### Changes Required:
1. **Add `UserStorageManager` class** to encapsulate user-specific storage
2. **Add `UserRegistry` class** to manage users.json
3. **Add `UserConfigStorage` class** for per-user config
4. **Replace global instances** with factory function `get_user_storage(user_id)`
5. **Add caching** to avoid re-reading user files on every message

#### New Classes:
```python
class UserRegistry(JSONStorage):
    """Manages user registration and metadata."""

    def register_user(self, user_id: str, username: str, first_name: str) -> User
    def get_user(self, user_id: str) -> User | None
    def update_last_seen(self, user_id: str)
    def list_users(self) -> List[User]
    def deactivate_user(self, user_id: str)

class UserConfigStorage(JSONStorage):
    """Storage for user-specific configuration."""

    def get_config(self) -> UserConfig
    def update_config(self, **kwargs)
    def reset_to_defaults(self)

class UserStorageManager:
    """Aggregates all storage for a user."""

    def __init__(self, user_id: str)
    # Properties: messages, scratchpad, config
```

#### Backwards Compatibility:
- Keep `MessageStorage` and `ScratchpadStorage` classes unchanged
- They now operate on user-specific files instead of global files
- Old code using `storage.messages` will fail gracefully with clear error

---

### 5.2 Telegram Bot (`src/telegram_bot.py`)

#### Changes Required:
1. **Extract `user_id` from all messages** (`update.effective_chat.id`)
2. **Pass `user_id` through callback chain**
3. **Auto-register new users** on first message
4. **Remove hardcoded `TELEGRAM_CHAT_ID`**

#### Modified Methods:
```python
async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages."""
    message_text = update.message.text
    chat_id = update.effective_chat.id
    user_id = str(chat_id)  # Use as string for consistency

    # Auto-register user if new
    user_registry = get_user_registry()
    if not user_registry.get_user(user_id):
        user_registry.register_user(
            user_id=user_id,
            username=update.effective_user.username,
            first_name=update.effective_user.first_name
        )
        logger.info(f"Registered new user: {user_id}")

    # Update last seen
    user_registry.update_last_seen(user_id)

    # Handle commands
    if message_text.startswith("..."):
        command = message_text[3:].strip()
        await commands.handle_command(command, self, user_id)  # NEW: pass user_id
        return

    # Get user-specific storage
    user_storage = get_user_storage(user_id)
    user_storage.messages.add_message("user", message_text)

    # Call callback with user_id
    if self.on_user_message_callback:
        await self.on_user_message_callback(message_text, user_id)  # Changed signature
```

#### New Signature:
```python
# OLD
on_user_message_callback: Callable[[str, int], Awaitable[None]]
# Signature: async def callback(message: str, chat_id: int)

# NEW
on_user_message_callback: Callable[[str, str], Awaitable[None]]
# Signature: async def callback(message: str, user_id: str)
```

---

### 5.3 Scheduler (`src/scheduler.py`)

#### Current Problem:
- Single `HeartbeatScheduler` instance
- Single `enabled` flag shared across all users
- Single job in APScheduler

#### Proposed Solution: Multi-User Scheduler

```python
class MultiUserHeartbeatScheduler:
    """Manages heartbeat schedules for multiple users."""

    def __init__(self, telegram_bot):
        self.telegram_bot = telegram_bot
        self.scheduler = AsyncIOScheduler()
        self.user_states: Dict[str, bool] = {}  # user_id -> enabled
        self.state_lock = threading.Lock()

    async def heartbeat_job(self, user_id: str):
        """Heartbeat job for a specific user."""
        try:
            if not self.is_enabled(user_id):
                return

            # Get user-specific storage
            user_storage = get_user_storage(user_id)
            user_config = user_storage.config.get_config()

            # Process heartbeat with user context
            await claude.process_heartbeat(
                telegram_bot=self.telegram_bot,
                user_id=user_id,
                user_storage=user_storage,
                user_config=user_config
            )

        except Exception as e:
            logger.error(f"Error in heartbeat for user {user_id}: {e}")

    def add_user(self, user_id: str, interval_minutes: int = 15, enabled: bool = True):
        """Add a user to the scheduler."""
        job_id = f"heartbeat_{user_id}"

        self.scheduler.add_job(
            self.heartbeat_job,
            trigger=IntervalTrigger(minutes=interval_minutes),
            args=[user_id],
            id=job_id,
            replace_existing=True,
            max_instances=1
        )

        with self.state_lock:
            self.user_states[user_id] = enabled

        logger.info(f"Added user {user_id} to scheduler (interval: {interval_minutes}m)")

    def remove_user(self, user_id: str):
        """Remove a user from the scheduler."""
        job_id = f"heartbeat_{user_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        with self.state_lock:
            self.user_states.pop(user_id, None)

    def pause_user(self, user_id: str):
        """Pause heartbeats for a specific user."""
        with self.state_lock:
            self.user_states[user_id] = False

    def resume_user(self, user_id: str):
        """Resume heartbeats for a specific user."""
        with self.state_lock:
            self.user_states[user_id] = True

    def is_enabled(self, user_id: str) -> bool:
        """Check if heartbeats are enabled for user."""
        with self.state_lock:
            return self.user_states.get(user_id, True)

    def get_user_status(self, user_id: str) -> dict:
        """Get scheduler status for a user."""
        job_id = f"heartbeat_{user_id}"
        job = self.scheduler.get_job(job_id)

        return {
            "enabled": self.is_enabled(user_id),
            "next_run": job.next_run_time if job else None,
            "job_exists": job is not None
        }

    def start(self):
        """Start the scheduler and load all users."""
        # Load all registered users
        user_registry = get_user_registry()
        for user in user_registry.list_users():
            if user.status == "active":
                user_storage = get_user_storage(user.user_id)
                user_config = user_storage.config.get_config()

                self.add_user(
                    user_id=user.user_id,
                    interval_minutes=user_config.heartbeat_interval_minutes,
                    enabled=user_config.heartbeat_enabled
                )

        self.scheduler.start()
        logger.info("Multi-user scheduler started")

    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
```

#### Scheduler State Persistence:
Currently, enabled/disabled state is lost on restart. With multiple users, we need persistence:

```python
class SchedulerStateStorage(JSONStorage):
    """Persist scheduler state across restarts."""

    def save_state(self, user_id: str, enabled: bool, last_run: str):
        data = self.read()
        data[user_id] = {
            "enabled": enabled,
            "last_run": last_run,
            "updated_at": datetime.utcnow().isoformat() + "Z"
        }
        self.write(data)

    def load_state(self) -> Dict[str, dict]:
        return self.read()
```

---

### 5.4 Claude Integration (`src/claude.py`)

#### Changes Required:
1. **Add `user_id` parameter** to `process_heartbeat()` and `respond_to_user()`
2. **Use user-specific storage** instead of global `storage.messages`
3. **Load user-specific config** for model selection
4. **Pass `user_id` to usage tracking**

#### Modified Functions:
```python
async def process_heartbeat(
    telegram_bot,
    user_id: str,                    # NEW
    user_storage: UserStorageManager, # NEW
    user_config: UserConfig,          # NEW
    debug: bool = False
) -> dict:
    """Process a heartbeat cycle for a specific user."""

    logger.info(f"Processing heartbeat for user {user_id}")

    # Load user's recent messages (not global)
    recent_messages = user_storage.messages.get_recent_messages(
        user_config.max_context_messages
    )

    # Load user's scratchpad notes
    notes = user_storage.scratchpad.get_notes()

    # Build context...
    # Call Claude API with user's model preference
    model = user_config.model
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=full_system_prompt,
        messages=messages,
        tools=TOOLS
    )

    # Track usage WITH user_id
    usage_data = usage_tracker.calculate_cost(
        model=model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens
    )
    usage_data["request_type"] = "heartbeat"
    usage_data["user_id"] = user_id  # NEW
    usage_tracker.log_api_usage(usage_data)

    # If message sent, store in user's conversation
    if message:
        await telegram_bot.send_message(message, chat_id=int(user_id))
        user_storage.messages.add_message("assistant", message)

    return result


async def respond_to_user(
    user_message: str,
    telegram_bot,
    user_id: str,                    # NEW
    user_storage: UserStorageManager, # NEW
    user_config: UserConfig           # NEW
) -> None:
    """Respond to a user message with user context."""

    logger.info(f"Responding to user {user_id}: {user_message[:50]}...")

    # Load user's recent messages
    recent_messages = user_storage.messages.get_recent_messages(
        user_config.max_context_messages
    )

    # Load user's notes
    notes = user_storage.scratchpad.get_notes()

    # Build conversation...
    model = user_config.model
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=full_system_prompt,
        messages=messages
    )

    # Track usage WITH user_id
    usage_data = usage_tracker.calculate_cost(
        model=model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens
    )
    usage_data["request_type"] = "user_response"
    usage_data["user_id"] = user_id  # NEW
    usage_tracker.log_api_usage(usage_data)

    # Send response
    await telegram_bot.send_message(response_text, chat_id=int(user_id))
    user_storage.messages.add_message("assistant", response_text)
```

---

### 5.5 Usage Tracker (`src/usage_tracker.py`)

#### Changes Required:
1. **Add `user_id` field to all logged usage**
2. **Add `get_user_usage_stats(user_id, days)` function**
3. **Update `format_usage_report()` to accept `user_id` parameter**
4. **Add admin function `get_all_users_usage_stats(days)`**

#### Enhanced Functions:
```python
def log_api_usage(usage_data: Dict) -> None:
    """
    Log API usage to JSONL file.

    Args:
        usage_data: Dict containing usage and cost information
                   MUST include 'user_id' field
    """
    if "user_id" not in usage_data:
        logger.warning("Usage data missing user_id - cannot log")
        return

    with open(USAGE_FILE, 'a') as f:
        f.write(json.dumps(usage_data) + '\n')


def get_user_usage_stats(user_id: str, days: int) -> Dict:
    """
    Get usage statistics for a specific user over last N days.

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

                # Filter by user_id
                if entry.get("user_id") != user_id:
                    continue

                entry_time = datetime.fromisoformat(entry["timestamp"].replace('Z', '+00:00'))

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
    Get usage statistics for all users.

    Args:
        days: Number of days to look back

    Returns:
        List of usage stats per user, sorted by total_cost descending
    """
    if not USAGE_FILE.exists():
        return []

    from datetime import timezone
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    # Aggregate by user_id
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

                if not user_id:
                    continue

                entry_time = datetime.fromisoformat(entry["timestamp"].replace('Z', '+00:00'))

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


def format_usage_report(user_id: str) -> str:
    """
    Format a usage report for a specific user.

    Args:
        user_id: User ID to generate report for

    Returns:
        Formatted string with usage statistics
    """
    user_storage = get_user_storage(user_id)
    user_config = user_storage.config.get_config()

    today_stats = get_user_usage_stats(user_id, 1)
    week_stats = get_user_usage_stats(user_id, 7)
    month_stats = get_user_usage_stats(user_id, 30)

    report = "📊 Status Report\n\n"
    report += f"Model: {user_config.model}\n\n"

    # Heartbeat status (from scheduler)
    # ... (similar to current, but for specific user)

    # Context information
    messages = user_storage.messages.get_recent_messages()
    notes = user_storage.scratchpad.get_notes()

    report += "📚 Context:\n"
    report += f"Messages in history: {len(messages)}\n"
    report += f"Scratchpad notes: {len(notes)}\n"

    # ... rest similar to current implementation

    return report
```

---

### 5.6 Commands (`src/commands.py`)

#### Changes Required:
1. **Add `user_id` parameter to all command handlers**
2. **Operate on user-specific storage/config**
3. **Update command signatures**

#### Modified Functions:
```python
async def handle_command(command: str, bot, user_id: str) -> bool:
    """
    Handle special commands that start with '...'

    Args:
        command: Command string without the '...' prefix
        bot: TelegramBot instance
        user_id: User ID executing the command

    Returns:
        True if command was handled, False if unknown
    """
    parts = command.split()
    if not parts:
        return False

    cmd = parts[0].lower()

    if cmd == "status":
        report = usage_tracker.format_usage_report(user_id)  # Pass user_id
        await bot.send_message(report, chat_id=int(user_id))
        return True

    elif cmd == "model":
        if len(parts) < 2:
            current = get_user_storage(user_id).config.get_config().model
            await bot.send_message(
                f"Current model: {current}\n\nUsage: ...model <model_name>",
                chat_id=int(user_id)
            )
            return True

        new_model = parts[1]
        # Update user-specific config
        get_user_storage(user_id).config.update_config(model=new_model)
        await bot.send_message(f"Model updated to: {new_model}", chat_id=int(user_id))
        return True

    elif cmd == "heartbeat":
        # ... handle heartbeat commands for specific user
        return True

    return False
```

---

### 5.7 Main Application (`main.py`)

#### Changes Required:
1. **Replace `HeartbeatScheduler` with `MultiUserHeartbeatScheduler`**
2. **Update callback to pass `user_id`**
3. **Initialize multi-user scheduler on startup**

#### Modified Code:
```python
class DaemonVigil:
    _instance = None

    def __init__(self):
        # ... logging setup ...

        # Initialize Telegram bot with user-aware callback
        self.bot = TelegramBot(on_user_message_callback=self.on_user_message)

        # Initialize multi-user scheduler
        self.scheduler = MultiUserHeartbeatScheduler(self.bot)

        DaemonVigil._instance = self

    async def on_user_message(self, message: str, user_id: str):
        """Handle user message with user context."""
        try:
            # Get user-specific storage and config
            user_storage = get_user_storage(user_id)
            user_config = user_storage.config.get_config()

            # Respond to user
            await claude.respond_to_user(
                user_message=message,
                telegram_bot=self.bot,
                user_id=user_id,
                user_storage=user_storage,
                user_config=user_config
            )
        except Exception as e:
            logger.error(f"Error responding to user {user_id}: {e}", exc_info=True)
            await self.bot.send_message(
                "Sorry, I encountered an error. Please try again.",
                chat_id=int(user_id)
            )

    async def start(self):
        """Start the daemon."""
        logger.info("Starting Daemon Vigil...")

        # Start Telegram bot
        await self.bot.start()

        # Start multi-user scheduler
        self.scheduler.start()

        logger.info("Daemon Vigil is running")
        logger.info("Press Ctrl+C to stop")

    async def stop(self):
        """Stop the daemon gracefully."""
        logger.info("Stopping Daemon Vigil...")

        self.scheduler.stop()
        await self.bot.stop()

        logger.info("Daemon Vigil stopped")
```

---

## 6. Migration Strategy

### 6.1 Data Migration Script

Create `scripts/migrate_to_multi_user.py`:

```python
"""
Migrate single-user data to multi-user format.

This script:
1. Reads existing messages.json, scratchpad.json
2. Creates user directory structure
3. Migrates data to first user (from TELEGRAM_CHAT_ID)
4. Backs up old files
"""

import json
import shutil
from pathlib import Path
from datetime import datetime

# Load config
from src import config

def migrate():
    """Perform migration."""
    data_dir = config.DATA_DIR

    # Get user ID from environment
    user_id = str(config.TELEGRAM_CHAT_ID)
    if not user_id or user_id == "None":
        print("ERROR: TELEGRAM_CHAT_ID not set in .env")
        print("Please set it to your Telegram chat ID before migrating")
        return False

    print(f"Migrating data for user: {user_id}")

    # Create users directory
    users_dir = data_dir / "users"
    users_dir.mkdir(exist_ok=True)

    user_dir = users_dir / user_id
    user_dir.mkdir(exist_ok=True)
    print(f"Created user directory: {user_dir}")

    # Migrate messages.json
    old_messages = data_dir / "messages.json"
    new_messages = user_dir / "messages.json"

    if old_messages.exists():
        shutil.copy(old_messages, new_messages)
        shutil.move(old_messages, data_dir / "messages.json.backup")
        print(f"Migrated messages.json -> {new_messages}")
    else:
        # Create empty
        new_messages.write_text(json.dumps({"messages": []}, indent=2))
        print(f"Created empty messages.json")

    # Migrate scratchpad.json
    old_scratchpad = data_dir / "scratchpad.json"
    new_scratchpad = user_dir / "scratchpad.json"

    if old_scratchpad.exists():
        shutil.copy(old_scratchpad, new_scratchpad)
        shutil.move(old_scratchpad, data_dir / "scratchpad.json.backup")
        print(f"Migrated scratchpad.json -> {new_scratchpad}")
    else:
        new_scratchpad.write_text(json.dumps({"notes": []}, indent=2))
        print(f"Created empty scratchpad.json")

    # Create user_config.json
    user_config_file = user_dir / "user_config.json"
    user_config = {
        "user_id": user_id,
        "model": config.get_claude_model(),
        "heartbeat_enabled": True,
        "heartbeat_interval_minutes": config.HEARTBEAT_INTERVAL_MINUTES,
        "max_context_messages": config.MAX_CONTEXT_MESSAGES,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "updated_at": datetime.utcnow().isoformat() + "Z"
    }
    user_config_file.write_text(json.dumps(user_config, indent=2))
    print(f"Created user_config.json")

    # Create users.json (user registry)
    users_json = data_dir / "users.json"
    users_data = {
        "users": [
            {
                "user_id": user_id,
                "telegram_username": "vals",  # Update manually if needed
                "telegram_first_name": "Vals",
                "registered_at": datetime.utcnow().isoformat() + "Z",
                "last_seen": datetime.utcnow().isoformat() + "Z",
                "status": "active"
            }
        ]
    }
    users_json.write_text(json.dumps(users_data, indent=2))
    print(f"Created users.json")

    # Migrate api_usage.jsonl - add user_id to all entries
    old_usage = data_dir / "api_usage.jsonl"
    if old_usage.exists():
        backup_usage = data_dir / "api_usage.jsonl.backup"
        shutil.copy(old_usage, backup_usage)

        # Read all lines, add user_id, write back
        lines = []
        with open(old_usage, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    entry["user_id"] = user_id  # Add user_id
                    lines.append(json.dumps(entry) + '\n')
                except:
                    lines.append(line)  # Keep malformed lines as-is

        with open(old_usage, 'w') as f:
            f.writelines(lines)

        print(f"Updated api_usage.jsonl with user_id field")

    print("\n✅ Migration complete!")
    print(f"\nBackups created:")
    print(f"  - {data_dir / 'messages.json.backup'}")
    print(f"  - {data_dir / 'scratchpad.json.backup'}")
    print(f"  - {data_dir / 'api_usage.jsonl.backup'}")

    return True

if __name__ == "__main__":
    migrate()
```

### 6.2 Migration Steps

1. **Backup existing data:**
   ```bash
   cp -r data/ data_backup/
   ```

2. **Set TELEGRAM_CHAT_ID in .env** (if not already set)

3. **Run migration script:**
   ```bash
   python scripts/migrate_to_multi_user.py
   ```

4. **Verify migration:**
   ```bash
   ls -la data/users/<your_chat_id>/
   # Should see: messages.json, scratchpad.json, user_config.json
   ```

5. **Test with new code:**
   - Start bot with new multi-user code
   - Send test message
   - Verify ...status command works
   - Check logs for errors

6. **Remove backups after successful testing:**
   ```bash
   rm data/*.backup
   ```

---

## 7. Implementation Phases

### Phase 1: Foundation (Storage & Models)
**Goal:** Create multi-user storage infrastructure

**Tasks:**
1. Create `User` and `UserConfig` dataclasses
2. Implement `UserRegistry` class
3. Implement `UserConfigStorage` class
4. Implement `UserStorageManager` class
5. Add `get_user_storage(user_id)` factory function
6. Write unit tests for new storage classes

**Deliverable:** New storage layer that supports per-user data

**Duration:** 1-2 days

---

### Phase 2: Component Refactoring
**Goal:** Update all components to use user-scoped storage

**Tasks:**
1. Update `telegram_bot.py`:
   - Extract user_id from messages
   - Auto-register new users
   - Pass user_id through callbacks
2. Update `claude.py`:
   - Add user_id parameters
   - Use user-specific storage
   - Load user-specific config
3. Update `usage_tracker.py`:
   - Add user_id to all logs
   - Implement per-user stats functions
4. Update `commands.py`:
   - Add user_id parameters
   - Operate on user-specific storage

**Deliverable:** All components user-aware (except scheduler)

**Duration:** 2-3 days

---

### Phase 3: Multi-User Scheduler
**Goal:** Support independent heartbeat schedules per user

**Tasks:**
1. Implement `MultiUserHeartbeatScheduler` class
2. Add per-user job management
3. Implement scheduler state persistence
4. Update `main.py` to use new scheduler
5. Test concurrent heartbeats for multiple users

**Deliverable:** Fully functional multi-user scheduler

**Duration:** 2-3 days

---

### Phase 4: Migration & Testing
**Goal:** Migrate existing data and validate multi-user system

**Tasks:**
1. Write migration script
2. Test migration with sample data
3. Create test users in Telegram
4. Test concurrent user interactions
5. Verify cost tracking per user
6. Load test (simulate 10+ users)

**Deliverable:** Production-ready multi-user system

**Duration:** 2-3 days

---

### Phase 5: Admin Features (Optional)
**Goal:** Add admin tools for managing multiple users

**Tasks:**
1. Add `...admin users` command - list all users
2. Add `...admin stats` command - aggregate stats across users
3. Add `...admin user <user_id>` command - view specific user details
4. Create web dashboard (optional, future)

**Deliverable:** Admin tools for multi-user management

**Duration:** 2-4 days (optional)

---

## 8. Security Considerations

### 8.1 User Isolation
- Each user's data stored in separate directory
- File permissions: `0700` for user directories (owner read/write/execute only)
- No shared mutable state between users (except scheduler)

### 8.2 Rate Limiting (Future)
Currently no rate limiting. Considerations:
- Per-user API request rate limiting (e.g., 100 requests/day)
- Per-user cost caps (e.g., $10/month max)
- Global rate limiting for server protection

### 8.3 Access Control
- User can only access their own data via commands
- No cross-user data access (enforced by storage layer)
- Admin commands require special authorization (future)

### 8.4 Data Privacy
- No logging of message contents to shared logs (only to user's messages.json)
- API usage logs include user_id but not message content
- Consider GDPR: users should be able to request data deletion

### 8.5 Input Validation
- Sanitize user_id (must be numeric string)
- Validate file paths (prevent directory traversal)
- Sanitize command inputs

---

## 9. Performance Considerations

### 9.1 Storage Performance
- **Caching:** User storage objects cached in-memory
- **Lazy Loading:** User data loaded only when accessed
- **File Locking:** Per-file locks minimize contention
- **Scalability:** File-based storage scales to ~100 users

### 9.2 Scheduler Performance
- APScheduler handles hundreds of jobs efficiently
- Each user gets independent job (no shared state contention)
- Jobs are coalesced (if multiple pile up, only one runs)

### 9.3 Memory Usage
- Each user's storage object: ~1KB (config) + conversation size
- 100 users * 50 messages * 200 bytes = ~1MB total
- Acceptable for single-server deployment

### 9.4 Bottlenecks
- **Claude API rate limits:** Most likely bottleneck
- **File I/O:** Not a bottleneck for 100 users
- **Telegram API:** Rate limited to 30 messages/second globally

---

## 10. Future Enhancements

### 10.1 Database Migration
If scaling beyond 100 users:
- Migrate to SQLite or PostgreSQL
- Keep same storage interface (abstract implementation)
- Benefits: ACID transactions, indexes, queries

### 10.2 User Features
- User preferences (timezone, language, tone)
- Custom system prompts per user
- User-specific tools (e.g., calendar integration)
- User groups (shared scratchpad, group chats)

### 10.3 Admin Features
- Web dashboard for monitoring
- User management (activate/deactivate)
- Cost analytics and billing
- Usage alerts (notify admin if user exceeds budget)

### 10.4 Advanced Scheduling
- Per-user "active hours" (only heartbeat during certain times)
- Custom heartbeat intervals per user
- Event-based triggers (not just time-based)

---

## 11. Summary

### Key Changes Required:
1. **Storage:** Per-user directories with isolated data files
2. **Telegram Bot:** Extract user_id, auto-register users, pass context
3. **Scheduler:** Multi-user scheduler with independent jobs
4. **Claude:** Accept user_id, load user-specific config/storage
5. **Usage Tracking:** Add user_id to all logs, per-user reporting
6. **Commands:** Operate on user-specific data

### Migration Path:
1. Create new storage classes (non-breaking)
2. Refactor components to accept user_id
3. Replace global storage with user-scoped storage
4. Migrate existing single-user data
5. Test with multiple users
6. Deploy

### Estimated Effort:
- **Phase 1-4:** 8-12 days development
- **Phase 5 (optional):** 2-4 days
- **Total:** ~2-3 weeks for full multi-user support

### Benefits:
- ✅ Clean per-user data isolation
- ✅ Independent heartbeat schedules
- ✅ Per-user cost tracking and reporting
- ✅ Scales to 100+ users on single server
- ✅ Backwards compatible (via migration script)
- ✅ Maintains file-based simplicity (no database yet)

---

## Next Steps

1. **Review this proposal** with stakeholders
2. **Choose architecture option** (recommended: Option A)
3. **Begin Phase 1** (storage layer implementation)
4. **Create feature branch** for multi-user work
5. **Implement incrementally** with tests at each phase

---

**Document Version:** 1.0
**Last Updated:** 2025-12-08
**Author:** Claude (Daemon Vigil Architect)
