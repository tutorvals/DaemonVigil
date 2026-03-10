# Daemon Vigil

Daemon Vigil is a proactive Telegram companion backed by Claude. Instead of waiting for commands, it runs on a heartbeat, reviews recent context for each user, and decides whether to send a check-in or stay silent.

## What It Does

- Receives Telegram messages and replies through Claude
- Runs scheduled per-user heartbeat checks
- Stores per-user conversation history, scratchpad notes, and preferences
- Supports per-user model selection, heartbeat interval, timezone, and quiet hours
- Tracks usage and estimated cost across requests

## Architecture Summary

- `main.py`: application entrypoint
- `src/telegram_bot.py`: Telegram polling and inbound message handling
- `src/claude.py`: Claude Agent SDK integration using local Claude Code auth
- `src/scheduler.py`: per-user APScheduler heartbeat jobs
- `src/storage.py`: JSON-backed user registry and per-user storage
- `src/commands.py`: Telegram `...` command handlers
- `data/users/<user_id>/`: per-user messages, scratchpad, and config
- `data/users.json`: user registry

## Prerequisites

- Python 3.10+ recommended
- A Telegram bot token from `@BotFather`
- Claude Code installed locally and already authenticated
- A Unix-like environment if you want to use `start.sh` and `stop.sh`

This project does not use an Anthropic API key in normal operation. It calls Claude through `claude-agent-sdk`, which in turn relies on your local Claude Code login.

## Quickstart

### 1. Clone the repo

```bash
git clone https://github.com/tutorvals/DaemonVigil.git
cd DaemonVigil
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create `.env`

Create a `.env` file in the project root:

```env
TELEGRAM_BOT_TOKEN=123456789:ABC...
TELEGRAM_CHAT_ID=123456789
```

Notes:

- `TELEGRAM_BOT_TOKEN` is required.
- `TELEGRAM_CHAT_ID` is optional for normal message handling, but useful for startup/shutdown notifications and older single-user workflows.
- In multi-user mode, any Telegram user who messages the bot is auto-registered.

### 5. Adjust `config.yaml` if needed

Default config:

```yaml
claude_model: opus
heartbeat_interval_minutes: 15
max_context_messages: 50
```

These values act as defaults for newly created users. Each user then gets their own `data/users/<user_id>/user_config.json`.

### 6. Make sure Claude Code works locally

Before running the bot, confirm your Claude Code setup is already authenticated on the same machine/account that will run Daemon Vigil.

### 7. Start the bot

Foreground:

```bash
python main.py
```

Foreground without startup/shutdown Telegram notifications:

```bash
python main.py --silent
```

Background helper script:

```bash
bash start.sh
```

Stop the background process:

```bash
bash stop.sh
```

### 8. First-run check

1. Send `/start` or any normal message to your bot in Telegram.
2. Confirm you receive a reply.
3. Run `...help` and `...heartbeat status`.
4. Check logs with `tail -f daemon_vigil.log`.

## Telegram Setup Notes

To get a bot token:

1. Open Telegram and message `@BotFather`.
2. Run `/newbot`.
3. Copy the token into `.env` as `TELEGRAM_BOT_TOKEN`.

To get your chat ID:

1. Send a message to your bot.
2. Open `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`.
3. Find the chat id in the JSON response.

## Runtime Behavior

- The bot uses Telegram long polling, not webhooks.
- On first message from a new user, that user is auto-registered in [data/users.json](/home/tutorvals/claudeCodeLand/daemonVigil/data/users.json).
- Each user gets separate files under [data/users](/home/tutorvals/claudeCodeLand/daemonVigil/data/users).
- Heartbeats are scheduled per active user.
- Quiet hours suppress scheduled heartbeats, but not direct replies to incoming messages.
- Usage is logged to [data/api_usage.jsonl](/home/tutorvals/claudeCodeLand/daemonVigil/data/api_usage.jsonl).

## Telegram Commands

All bot commands start with `...`.

### General

- `...help`: show available commands
- `...status`: show usage/cost information

### Model

- `...model`: show current model
- `...model sonnet`
- `...model sonnet-4.5`
- `...model opus`
- `...model haiku`

### Heartbeats

- `...heartbeat test`: dry-run a heartbeat and show Claude's reasoning
- `...heartbeat on`: enable scheduled heartbeats
- `...heartbeat off`: disable scheduled heartbeats
- `...heartbeat status`: show heartbeat status
- `...heartbeat interval <minutes>`: set the user's heartbeat interval

### Quiet Hours

- `...quiethours status`
- `...quiethours on`
- `...quiethours off`
- `...quiethours set <HH:MM> <HH:MM>`
- `...quiethours timezone <Area/City>`

Example:

```text
...quiethours timezone Europe/Paris
...quiethours set 22:00 08:00
...quiethours on
```

### Conversation State

- `...clear`: clear conversation history only
- `...showmemory`: show scratchpad notes
- `...clearmemory`: clear scratchpad notes only

## Data Layout

```text
daemonVigil/
├── main.py
├── config.yaml
├── .env
├── daemon_vigil.log
├── data/
│   ├── api_usage.jsonl
│   ├── billing_thresholds.json
│   ├── users.json
│   └── users/
│       └── <user_id>/
│           ├── messages.json
│           ├── scratchpad.json
│           └── user_config.json
├── prompts/
│   └── system.md
└── src/
```

## Migration From Older Single-User Storage

If you have an older checkout that stored global `messages.json` and `scratchpad.json`, use:

```bash
python scripts/migrate_to_multi_user.py
```

That script expects `TELEGRAM_CHAT_ID` to be present in `.env`.

## Development

Run tests with the project virtualenv:

```bash
./venv/bin/pytest -q
```

## README Gaps That Were Fixed

The previous README was usable as a rough overview, but it had several accuracy gaps:

- It described the app mostly as single-user even though the code is multi-user.
- It did not document quiet-hours commands.
- It implied `TELEGRAM_CHAT_ID` was always required, while the code treats it as optional.
- It did not clearly state that local Claude Code authentication is a real runtime prerequisite.
- It documented `tmux`, but the repo already ships `start.sh` and `stop.sh` as the simpler default path.

## Next Documentation Improvements

- Add a dedicated troubleshooting section for Telegram auth, Claude auth, and empty replies.
- Add an example `.env.example`.
- Document the expected Python version explicitly in the project metadata.
- Document deployment steps separately from local quickstart.
