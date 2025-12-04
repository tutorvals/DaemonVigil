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

```bash
git clone https://github.com/tutorvals/DaemonVigil.git
cd DaemonVigil
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Linux/Mac
# OR
venv\Scripts\activate     # On Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Secrets

Create a `.env` file with your API keys:

```bash
# Copy from example (if exists) or create new
touch .env
```

Add the following to `.env`:

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

You'll see logs in real-time. Press `Ctrl+C` to stop.

**Silent mode** (no startup/shutdown messages):

```bash
python main.py --silent
```

### Background (Production)

#### Option 1: Using tmux (Recommended)

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

#### Option 2: Using screen

```bash
# Start new screen session
screen -S daemon-vigil

# Inside screen, run the app
python main.py

# Detach from screen: Press Ctrl+A, then D
```

**To reconnect:**

```bash
screen -r daemon-vigil
```

#### Option 3: Using nohup

```bash
nohup python main.py > daemon_vigil.log 2>&1 &
```

**Find the process:**

```bash
ps aux | grep "python main.py"
# OR
pgrep -f "python main.py"
```

**Stop the process:**

```bash
kill <PID>
# OR
pkill -f "python main.py"
```

## Telegram Commands

All commands start with `...` (three dots).

### Status & Information

**`...status`** - Show current model, API costs, and context info
```
📊 Status Report

Model: claude-3-5-haiku-20241022

📚 Context:
Messages in history: 42
Scratchpad notes: 3
Last note: Vals mentioned working on daemonVigil

💰 API Costs:
Today:      $0.0045 (3 requests)
This Week:  $0.0213 (15 requests)
This Month: $0.0867 (52 requests)
```

### Model Switching

**`...model`** - Show current model and available options

**`...model <name>`** - Switch to a different model
```
...model sonnet    # Sonnet 4 (balanced)
...model opus      # Opus 4.5 (most powerful)
...model haiku     # Haiku 3.5 (fastest/cheapest)
```

**Available models:**
- `sonnet`, `sonnet-4`, `sonnet-4.5` - Balanced performance ($3/M in, $15/M out)
- `opus`, `opus-4`, `opus-4.5` - Most powerful ($15/M in, $75/M out)
- `haiku`, `haiku-3`, `haiku-3.5` - Fast and cheap ($0.80/M in, $4/M out)

### Heartbeat Control

**`...heartbeat test`** - Run manual heartbeat with debug output
- Shows Claude's reasoning
- Shows whether it would message or stay silent
- Doesn't actually send the message (dry run)

**`...heartbeat on`** - Enable automatic heartbeats
```
✅ Automatic heartbeats ENABLED
The bot will check in periodically as scheduled.
```

**`...heartbeat off`** - Disable automatic heartbeats
```
🔇 Automatic heartbeats DISABLED
The bot will not send scheduled check-ins.
```

**`...heartbeat status`** - Show heartbeat status
```
📊 Heartbeat Status

State: ✅ ENABLED
Interval: 15 minutes
Next run: 2025-12-04 15:45:00+00:00
```

## Logs

Logs are written to `daemon_vigil.log` in the project directory.

**View recent logs:**

```bash
tail -f daemon_vigil.log
```

**Search for heartbeats:**

```bash
grep "HEARTBEAT TRIGGERED" daemon_vigil.log
```

**Check for errors:**

```bash
grep "ERROR" daemon_vigil.log
```

## Updating

To update to the latest version:

```bash
# Stop the running instance first
# (Ctrl+C if foreground, or kill the process if background)

# Pull latest changes
git pull

# Restart
python main.py
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Daemon Vigil                      │
│                                                     │
│  ┌───────────┐    ┌───────────┐    ┌────────────┐  │
│  │ Scheduler │───▶│  Claude   │───▶│  Telegram  │  │
│  │ (15 min)  │    │   API     │    │    Bot     │  │
│  └───────────┘    └─────┬─────┘    └─────┬──────┘  │
│                         │                │         │
│                         ▼                ▼         │
│                   ┌───────────────────────┐        │
│                   │     JSON files        │        │
│                   │  - messages.json      │        │
│                   │  - scratchpad.json    │        │
│                   │  - api_usage.jsonl    │        │
│                   └───────────────────────┘        │
└─────────────────────────────────────────────────────┘
```

### Key Components

- **Scheduler**: Triggers heartbeat every N minutes
- **Claude API**: Makes decisions about whether to message
- **Telegram Bot**: Sends/receives messages
- **JSON Storage**: Persists conversation history and notes
- **Usage Tracker**: Logs API costs and token usage

## Troubleshooting

### Bot not responding to messages

**Check if running:**
```bash
ps aux | grep "python main.py"
```

**Check logs:**
```bash
tail -20 daemon_vigil.log
```

**Common issue**: Multiple instances running (Telegram Conflict error)
```bash
# Kill all instances
pkill -f "python main.py"

# Start fresh
python main.py
```

### Heartbeats not firing

**Check status:**
```
...heartbeat status
```

**Check if disabled:**
```
...heartbeat on
```

**Check logs:**
```bash
grep "HEARTBEAT TRIGGERED" daemon_vigil.log
```

### API errors

**Check API key:**
- Verify `.env` has valid `ANTHROPIC_API_KEY`

**Check credits:**
- Visit https://console.anthropic.com/ to check account balance

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

This is a personal project, but feel free to fork and adapt for your own use.

## License

MIT License - feel free to use and modify.
