# Daemon Vigil

A proactive AI companion that checks in via Telegram. Runs on a heartbeat — periodically waking up, assessing context, and deciding whether to send a message.

## Stack
- **Language**: Python 3
- **APIs**: Anthropic (Claude), Telegram Bot API
- **Config**: `config.yaml` + `.env` for secrets
- **Venv**: `venv/` in project directory

## Commands
- `python main.py` — run in foreground
- `python main.py --silent` — run without startup/shutdown messages
- `bash start.sh` — start in background (writes PID to `.daemon_vigil.pid`)
- `bash stop.sh` — stop background process

## Key Files
- `main.py` — entry point
- `config.yaml` — configuration (heartbeat interval, model, context size)
- `src/` — source code (claude, telegram, scheduler, commands, storage, usage tracking)
- `prompts/system.md` — system prompt for Claude
- `data/` — runtime data (messages, scratchpad, API usage)

## Telegram Commands
All commands start with `...` (three dots): `...status`, `...help`, `...model <name>`, `...heartbeat <on|off|test|status|interval N>`, `...clear`

## Deployment (VPS: vals@77.42.16.53)

Remote path: `~/daemonVigil`
Origin: `git@github.com:tutorvals/DaemonVigil.git`

### Deploy steps (from local)
1. Push: `git push` (from local daemonVigil/)
2. Pull on VPS: `ssh vals@77.42.16.53 "cd ~/daemonVigil && git pull"`
3. Stop: `ssh vals@77.42.16.53 "cd ~/daemonVigil && bash stop.sh"`
4. Start: `ssh vals@77.42.16.53 "cd ~/daemonVigil && bash start.sh"`

### Quick full deploy
Push, pull, restart in sequence.
