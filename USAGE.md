# Daemon Vigil - Quick Usage Guide

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Create a `.env` file with:
   ```
   TELEGRAM_BOT_TOKEN=123456789:ABC...
   TELEGRAM_CHAT_ID=123456789
   ```
3. Make sure Claude Code is installed and authenticated locally.
4. (Optional) Edit `config.yaml` to change heartbeat interval, model, or context size.

## Running

```bash
python main.py            # foreground
python main.py --silent   # foreground, no startup/shutdown messages
```

## Telegram Commands

| Command | Description |
|---|---|
| `...status` | Show model, costs, and context info |
| `...model` | Show current model |
| `...model sonnet/opus/haiku` | Switch model |
| `...heartbeat test` | Dry-run a heartbeat |
| `...heartbeat on/off` | Enable/disable automatic heartbeats |
| `...heartbeat status` | Show heartbeat state and next run time |
| `...clear` | Clear conversation history |
| `...showmemory` | Show scratchpad memory |
| `...clearmemory` | Clear scratchpad memory |

## Logs

Logs go to `daemon_vigil.log`. View with `tail -f daemon_vigil.log`.
