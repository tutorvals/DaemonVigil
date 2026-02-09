# Daemon Vigil
A proactive AI companion that checks in with you via Telegram. Unlike reactive chatbots, Daemon Vigil runs on a heartbeat - periodically waking up, assessing context, and **deciding** whether to send a message.

## Features
- **Proactive Check-ins**: Claude decides whether to message or stay silent
- **Heartbeat System**: Runs every 15 minutes (configurable)
- **Time Awareness**: All messages timestamped, Claude can track time gaps
- **Cost Tracking**: Monitor API usage and costs per day/week/month
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
Create a `.env` file with your API keys:

```env
ANTHROPIC_API_KEY=sk-ant-api03-...
TELEGRAM_BOT_TOKEN=123456789:ABC...
TELEGRAM_CHAT_ID=123456789
```

**Getting API Keys:**
- **Anthropic API Key**: Get from https://console.anthropic.com/
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
claude_model: claude-3-5-haiku-20241022  # Model to use
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
...model sonnet    # Sonnet 4 (balanced)
...model opus      # Opus 4.5 (most powerful)
...model haiku     # Haiku 3.5 (fastest/cheapest)
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
- Deletes all messages and Claude's notes
- Starts fresh with no memory of previous conversations

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
├── DESIGN_COMMANDS.md       # Command system design
├── DESIGN_SCHEDULER.md      # Scheduler design
├── data/                    # Data directory (not in git)
│   ├── messages.json        # Conversation history
│   ├── scratchpad.json      # Claude's notes
│   └── api_usage.jsonl      # Usage tracking
├── src/                     # Source code
│   ├── claude.py            # Claude API integration
│   ├── commands.py          # Command handlers
│   ├── config.py            # Configuration loading
│   ├── scheduler.py         # Heartbeat scheduler
│   ├── storage.py           # JSON storage
│   ├── telegram_bot.py      # Telegram integration
│   └── usage_tracker.py     # Cost tracking
└── prompts/
    └── system.md            # System prompt for Claude
```

## Contributing
This is a personal project, feel free to fork and adapt for your own use.

## License
MIT License - feel free to use and modify.
