# Daemon Vigil
A proactive AI companion that checks in via Telegram. Unlike a reactive chatbot, Daemon Vigil runs on a heartbeat, reviews recent context, and decides whether to send a message.

## Features
- **Proactive Check-ins**: Claude decides whether to message or stay silent
- **Heartbeat System**: Runs every 15 minutes (configurable)
- **Time Awareness**: All messages timestamped, Claude can track time gaps
- **Usage Tracking**: Monitor token usage and estimated costs per day/week/month
- **Per-User Storage**: Separate history, memory, and config per Telegram user
- **Model Switching**: Easily switch between Sonnet, Opus, Haiku
- **Command System**: Control bot behavior via Telegram commands

## Setup

### 1. Clone the Repository
git clone https://github.com/tutorvals/DaemonVigil.git

### 2. Create Virtual Environment
python3 -m venv venv
source venv/bin/activate  # On Linux/Mac
# OR
venv\Scripts\activate     # On Windows

### 3. Install Dependencies
pip install -r requirements.txt

### 4. Configure Secrets
Create a `.env` file with:

```env
TELEGRAM_BOT_TOKEN=123456789:ABC...
TELEGRAM_CHAT_ID=123456789
```

Daemon Vigil uses local Claude Code authentication via the Python Agent SDK. It does not require an Anthropic API key for normal operation.

**Getting Telegram credentials:**
- **Telegram Bot Token**:
  1. Open Telegram and search for `@BotFather`
  2. Send `/newbot` and follow prompts
  3. Copy the token
- **Telegram Chat ID**:
  1. Message your bot in Telegram
  2. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
  3. Find `"chat":{"id":123456789}` in the response

### 5. Configure Settings (Optional)
Edit `config.yaml` to customize:
```yaml
heartbeat_interval_minutes: 15        # How often to check in
max_context_messages: 50              # Conversation history size
claude_model: opus                    # Model alias to use
```

## Running

### Foreground (Testing)
Run directly in your terminal:
```bash
python main.py
```

**Silent mode** (no startup/shutdown messages):
```bash
python main.py --silent
```

### Background (Production) Using tmux 
```bash
# Start new tmux session
tmux new -s daemon-vigil

# Inside tmux, run the app
python main.py

# Detach from tmux: Press Ctrl+B, then D
# App keeps running in background
```

**To reconnect later:**
```bash
tmux attach -t daemon-vigil
```

**To list all tmux sessions:**
```bash
tmux ls
```

**To kill the session:**
```bash
tmux kill-session -t daemon-vigil
```

## Telegram Commands
All commands start with `...` (three dots).

### Status & Information
**`...status`** - Show current model, API costs, and context info

**`...help`** - Show list of available commands

### Model Switching
**`...model`** - Show current model and available options

**`...model <name>`** - Switch to a different model
```
...model sonnet    # balanced
...model opus      # strongest
...model haiku     # cheapest
```

### Heartbeat Control
**`...heartbeat test`** - Run manual heartbeat with debug output
- Shows Claude's reasoning
- Shows whether it would message or stay silent
- Doesn't actually send the message (dry run)

**`...heartbeat on`** - Enable automatic heartbeats

**`...heartbeat off`** - Disable automatic heartbeats

**`...heartbeat status`** - Show heartbeat status

**`...heartbeat interval <minutes>`** - Change heartbeat interval
```
...heartbeat interval 30    # Check in every 30 minutes
...heartbeat interval 60    # Check in every hour
```

### Conversation Management
**`...clear`** - Clear conversation history
- Keeps scratchpad memory intact

**`...showmemory`** - Show scratchpad memory

**`...clearmemory`** - Clear scratchpad memory

## Logs
Logs are written to `daemon_vigil.log` in the project directory.

## Files & Directories
```
daemon-vigil/
├── main.py                  # Entry point
├── config.yaml              # Configuration
├── .env                     # Secrets (not in git)
├── daemon_vigil.log         # Log file (not in git)
├── requirements.txt         # Python dependencies
├── README.md                # This file
├── data/                    # Data directory (not in git)
│   ├── api_usage.jsonl      # Usage tracking
│   ├── users.json           # User registry
│   └── users/<user_id>/     # Per-user data
├── src/                     # Source code
│   ├── claude.py            # Claude SDK integration
│   ├── commands.py          # Command handlers
│   ├── config.py            # Configuration loading
│   ├── scheduler.py         # Heartbeat scheduler
│   ├── storage.py           # Per-user JSON storage
│   ├── telegram_bot.py      # Telegram integration
│   └── usage_tracker.py     # Cost tracking
└── prompts/
    └── system.md            # System prompt for Claude
```

## Runtime Model
- The app uses `claude_agent_sdk` with Claude Code auth from your local machine.
- Calls are configured to be stateless and minimal:
  - no persisted session
  - no Claude Code tools
  - no CLAUDE.md/project settings injection
  - Claude Code auto-memory disabled
- The context sent to Claude is built by the app from:
  - `prompts/system.md`
  - current time
  - recent conversation history
  - per-user scratchpad notes

## Contributing
This is a personal project, feel free to fork and adapt for your own use.

## License
MIT License - feel free to use and modify.
