# Multi-User Architecture Diagrams

## Current Single-User Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Telegram Bot                           │
│                  (Single TELEGRAM_CHAT_ID)                  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      Main Application                       │
│  ┌──────────────┐           ┌─────────────────────┐        │
│  │   Telegram   │           │    Heartbeat        │        │
│  │     Bot      │◄──────────┤    Scheduler        │        │
│  │              │           │   (Single Job)      │        │
│  └──────┬───────┘           └─────────────────────┘        │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────────────────┐                               │
│  │   Claude Integration    │                               │
│  └──────────┬──────────────┘                               │
└─────────────┼──────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Global Storage                           │
│  ┌─────────────────┐  ┌────────────────┐  ┌──────────────┐ │
│  │ messages.json   │  │scratchpad.json │  │api_usage.jsonl│ │
│  │                 │  │                │  │ (no user_id) │ │
│  │ - timestamp     │  │ - timestamp    │  │              │ │
│  │ - role          │  │ - note         │  │ - tokens     │ │
│  │ - content       │  │                │  │ - cost       │ │
│  └─────────────────┘  └────────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘

PROBLEMS:
❌ Single user only (hardcoded TELEGRAM_CHAT_ID)
❌ No user identification in data
❌ Single shared conversation
❌ One heartbeat schedule for all users
❌ Cannot track costs per user
```

---

## Proposed Multi-User Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Telegram Bot                           │
│              (Accepts messages from ANY user)               │
└────────────────┬───────────────────┬────────────────────────┘
                 │                   │
      User A     │        User B     │        User C
      (123456789)│        (987654321)│        (555555555)
                 │                   │
                 ▼                   ▼
┌─────────────────────────────────────────────────────────────┐
│                      Main Application                       │
│  ┌──────────────┐           ┌─────────────────────┐        │
│  │   Telegram   │           │   Multi-User        │        │
│  │     Bot      │◄──────────┤   Heartbeat         │        │
│  │              │           │   Scheduler         │        │
│  │  Extracts    │           │                     │        │
│  │  user_id     │           │  ┌──────────────┐  │        │
│  │  from msg    │           │  │ Job: User A  │  │        │
│  └──────┬───────┘           │  ├──────────────┤  │        │
│         │                   │  │ Job: User B  │  │        │
│         │                   │  ├──────────────┤  │        │
│         │                   │  │ Job: User C  │  │        │
│         │                   │  └──────────────┘  │        │
│         │                   └─────────────────────┘        │
│         ▼                                                   │
│  ┌─────────────────────────┐                               │
│  │   Claude Integration    │                               │
│  │  (with user_id param)   │                               │
│  └──────────┬──────────────┘                               │
└─────────────┼──────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│              Per-User Storage (Recommended)                 │
│                                                             │
│  users/                                                     │
│  ├── 123456789/                                            │
│  │   ├── messages.json       ← User A's conversation       │
│  │   ├── scratchpad.json     ← User A's notes             │
│  │   └── user_config.json    ← User A's settings          │
│  ├── 987654321/                                            │
│  │   ├── messages.json       ← User B's conversation       │
│  │   ├── scratchpad.json     ← User B's notes             │
│  │   └── user_config.json    ← User B's settings          │
│  └── 555555555/                                            │
│      ├── messages.json       ← User C's conversation       │
│      ├── scratchpad.json     ← User C's notes             │
│      └── user_config.json    ← User C's settings          │
│                                                             │
│  api_usage.jsonl             ← Shared, with user_id field  │
│  users.json                  ← User registry               │
│  scheduler_state.json        ← Heartbeat on/off per user   │
└─────────────────────────────────────────────────────────────┘

BENEFITS:
✅ Multiple users supported automatically
✅ Each user has isolated data
✅ Per-user API cost tracking
✅ Independent heartbeat schedules
✅ Per-user model preferences
✅ Scales to 100+ users
```

---

## Data Flow: User Message

### Current (Single User)
```
Telegram Message
       │
       ▼
  ┌─────────────────┐
  │ TelegramBot     │
  │ handle_message()│
  └────────┬────────┘
           │
           ├─────────────► storage.messages.add_message()
           │                (global storage)
           │
           ▼
  ┌─────────────────┐
  │ claude.respond  │
  │ _to_user()      │
  └────────┬────────┘
           │
           ├─────────────► storage.messages.get_recent()
           │                (global storage)
           │
           ▼
     Claude API
```

### Proposed (Multi-User)
```
Telegram Message
       │
       ▼
  ┌─────────────────────────┐
  │ TelegramBot             │
  │ handle_message()        │
  │                         │
  │ user_id = msg.chat.id   │ ← Extract user_id
  └────────┬────────────────┘
           │
           ├─────────────► user_storage = get_user_storage(user_id)
           │                user_storage.messages.add_message()
           │
           ▼
  ┌───────────────────────────┐
  │ claude.respond_to_user()  │
  │                           │
  │ + user_id                 │ ← Pass user context
  │ + user_storage            │
  │ + user_config             │
  └────────┬──────────────────┘
           │
           ├─────────────► user_storage.messages.get_recent()
           │                (user-specific)
           │
           ├─────────────► user_config.model
           │                (user's preferred model)
           │
           ▼
     Claude API
           │
           ▼
  usage_data["user_id"] = user_id  ← Track cost per user
```

---

## Storage Access Patterns

### Current Pattern (Global)
```python
# Global instances (single user)
from src import storage

storage.messages.add_message("user", "Hello")
messages = storage.messages.get_recent_messages(50)
```

### Proposed Pattern (Per-User)
```python
# User-scoped instances
from src.storage import get_user_storage

user_storage = get_user_storage(user_id)
user_storage.messages.add_message("user", "Hello")
messages = user_storage.messages.get_recent_messages(50)
```

### Storage Manager Caching
```python
# Internal caching to avoid re-reading files
_storage_cache = {
    "123456789": UserStorageManager(...),  # Cached
    "987654321": UserStorageManager(...),  # Cached
}

def get_user_storage(user_id: str) -> UserStorageManager:
    if user_id not in _storage_cache:
        _storage_cache[user_id] = UserStorageManager(user_id)
    return _storage_cache[user_id]
```

---

## Scheduler Transformation

### Current: Single Scheduler
```
HeartbeatScheduler
└── Job: "heartbeat"
    ├── Interval: 15 minutes (global)
    ├── Enabled: True/False (global)
    └── Calls: claude.process_heartbeat(telegram_bot)
               (no user context)
```

### Proposed: Multi-User Scheduler
```
MultiUserHeartbeatScheduler
├── Job: "heartbeat_123456789" (User A)
│   ├── Interval: 15 minutes (per-user)
│   ├── Enabled: True (per-user)
│   └── Calls: claude.process_heartbeat(bot, user_id="123456789", ...)
│
├── Job: "heartbeat_987654321" (User B)
│   ├── Interval: 30 minutes (per-user)
│   ├── Enabled: False (paused for this user)
│   └── Calls: claude.process_heartbeat(bot, user_id="987654321", ...)
│
└── Job: "heartbeat_555555555" (User C)
    ├── Interval: 10 minutes (per-user)
    ├── Enabled: True (per-user)
    └── Calls: claude.process_heartbeat(bot, user_id="555555555", ...)

States persisted in: scheduler_state.json
```

---

## API Usage Tracking

### Current Format (No User ID)
```jsonl
{"input_tokens": 1234, "output_tokens": 567, "total_cost": 0.012207, "model": "claude-opus-4-5-20251101", "timestamp": "2025-12-08T10:45:00Z", "request_type": "heartbeat"}
```
**Problem:** Cannot determine which user incurred this cost

### Proposed Format (With User ID)
```jsonl
{"user_id": "123456789", "input_tokens": 1234, "output_tokens": 567, "total_cost": 0.012207, "model": "claude-opus-4-5-20251101", "timestamp": "2025-12-08T10:45:00Z", "request_type": "heartbeat"}
{"user_id": "987654321", "input_tokens": 890, "output_tokens": 234, "total_cost": 0.00618, "model": "claude-sonnet-4-5-20250929", "timestamp": "2025-12-08T11:00:00Z", "request_type": "user_response"}
```

### Per-User Cost Reporting
```python
# Get cost for specific user
stats = usage_tracker.get_user_usage_stats(user_id="123456789", days=30)
# Returns: {"user_id": "123456789", "total_cost": 5.42, ...}

# Get cost across all users (admin view)
all_stats = usage_tracker.get_all_users_usage_stats(days=30)
# Returns: [
#   {"user_id": "123456789", "total_cost": 5.42, ...},
#   {"user_id": "987654321", "total_cost": 2.31, ...},
# ]
```

---

## Command Execution Flow

### Current (Global State)
```
User sends: "...status"
       │
       ▼
  ┌────────────────┐
  │ commands.py    │
  │ handle_command │
  └────────┬───────┘
           │
           ├─────► usage_tracker.format_usage_report()
           │        (returns global stats)
           │
           ├─────► storage.messages.get_recent_messages()
           │        (returns global messages)
           │
           └─────► config.get_claude_model()
                    (returns global model)
```

### Proposed (User-Scoped State)
```
User A sends: "...status"
       │
       ▼
  ┌────────────────────────┐
  │ commands.py            │
  │ handle_command()       │
  │                        │
  │ + user_id="123456789"  │ ← User context
  └────────┬───────────────┘
           │
           ├─────► usage_tracker.format_usage_report(user_id)
           │        (returns User A's stats only)
           │
           ├─────► user_storage.messages.get_recent_messages()
           │        (returns User A's messages only)
           │
           └─────► user_storage.config.get_config().model
                    (returns User A's model preference)

Result: User A sees ONLY their own data
```

---

## Migration Process

```
                BEFORE MIGRATION
┌───────────────────────────────────────────┐
│ data/                                     │
│ ├── messages.json        (single user)    │
│ ├── scratchpad.json      (single user)    │
│ └── api_usage.jsonl      (no user_id)     │
└───────────────────────────────────────────┘
                    │
                    │ Run migration script
                    │ (reads TELEGRAM_CHAT_ID from .env)
                    ▼
                AFTER MIGRATION
┌───────────────────────────────────────────┐
│ data/                                     │
│ ├── users/                                │
│ │   └── 123456789/  ← Migrated from old  │
│ │       ├── messages.json                 │
│ │       ├── scratchpad.json               │
│ │       └── user_config.json (new)        │
│ ├── users.json (new - user registry)     │
│ ├── api_usage.jsonl (updated with user_id)│
│ ├── messages.json.backup                  │
│ ├── scratchpad.json.backup                │
│ └── api_usage.jsonl.backup                │
└───────────────────────────────────────────┘

New users joining after migration are
automatically registered in users.json
and get their own directory.
```

---

## Scalability & Performance

### File Count by User Count

```
Users │ Total Files │ Storage Size (estimate)
──────┼─────────────┼────────────────────────
   1  │      5      │ ~100 KB
  10  │     32      │ ~1 MB
  50  │    152      │ ~5 MB
 100  │    302      │ ~10 MB

Each user adds:
- 3 files (messages, scratchpad, config)
- ~50-100 KB per user (depends on message history)

File-based storage is efficient up to ~100 users.
Beyond that, consider database migration.
```

### Concurrent Access Patterns

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  User A     │  │  User B     │  │  User C     │
│  Message    │  │  Message    │  │  Heartbeat  │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │
       ▼                ▼                ▼
┌──────────────────────────────────────────────┐
│            TelegramBot (async)               │
└──────┬───────────────┬───────────┬───────────┘
       │               │           │
       ▼               ▼           ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ User A      │ │ User B      │ │ User C      │
│ Storage     │ │ Storage     │ │ Storage     │
│ (isolated)  │ │ (isolated)  │ │ (isolated)  │
└─────────────┘ └─────────────┘ └─────────────┘

✅ No lock contention between users
✅ Parallel processing of user messages
✅ Each storage has its own file lock
```

---

## Summary

| Aspect | Current | Proposed |
|--------|---------|----------|
| **Users** | 1 (hardcoded) | Unlimited (auto-register) |
| **Storage** | Global files | Per-user directories |
| **Conversations** | Shared | Isolated per user |
| **API Costs** | Global | Tracked per user |
| **Heartbeats** | Single schedule | Per-user schedules |
| **Configuration** | Global config.yaml | Per-user config.json |
| **Scalability** | N/A | ~100 users per server |
| **File Count** | 3 files | 3 + (3 × users) files |

**Key Insight:** The architecture transforms from a single-user daemon
into a multi-tenant system while maintaining file-based simplicity.
