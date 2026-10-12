# DaemonVigil v2 (Vigil)

Asked for (Vals, 2026-10-12): rebuild DaemonVigil as an always-on Claude Code on the VPS, reached through
Telegram, proactive, aware of how Vals works, able to talk to the laptop land-coordinator through a dedicated
bridge that carries only session-to-session messages. Runs as the existing user `vals` (Vals, 2026-10-12).
Design and code: Claude, 2026-10-12, TENTATIVE until Vals reviews. v1 (Python, repo root) stays untouched and
running until the switch.

## How the pieces fit

```
Vals' phone ──Telegram──> [official telegram channel plugin] ─┐
                                                               ├─> claude session "vigil" (tmux, ~/vigil, VPS)
heartbeat timer ─> ~/vigil/spool/inbox ─> [vigil-bridge, vps] ─┘        │ send_to_coordinator
                                                                         v
                                           ~/vigil/spool/outbox <── fetch/put ── ssh (restricted key, forced
                                                                         command bridge-ssh.py) <── [vigil-bridge,
                                                                         laptop] inside land-coordinator (laptop)
```

- `bridge/vigil-bridge.ts`: a Claude Code channel (MCP server over stdio, research preview). Same file both sides,
  `BRIDGE_MODE=vps|laptop`. VPS: pushes spool files (heartbeat, coordinator) into the session, tool
  `send_to_coordinator`. Laptop: polls the VPS every 60 s, tool `send_to_vigil`, logs everything to
  `~/.local/state/vigil-bridge/messages.jsonl`.
- `bridge/bridge-ssh.py`: forced command for the laptop's bridge key on the VPS; knows only `fetch` and `put`.
- `heartbeat/`: a systemd timer (30 min, quiet hours 23-08 Europe/Paris) drops one event in the spool; skipped when
  the previous one is unread or `~/vigil/state/heartbeat-off` exists.
- `workspace/`: the session's `CLAUDE.md`, `.mcp.json` and `.claude/settings.json` (symlinked into `~/vigil` by
  `install.sh`, so `git pull` updates them).
- `scripts/sync-context.sh` (laptop): copies a snapshot of Vals' workflow docs to `~/vigil/context/`.

## Bridge threat model

Goal: a compromised VPS must not get command execution on the laptop.
- The laptop only connects out (ssh to the VPS); nothing listens on the laptop. The VPS answers `fetch` with JSON
  text; the laptop parses it, strips control characters, caps size and pushes it as a labelled channel event.
- The bridge never declares `claude/channel/permission`, so nothing from the VPS can approve a laptop tool call.
- Remaining risk: prompt injection of the coordinator (text that tries to talk it into acting). Guarded by the
  coordinator's rules (agent messages are never Vals' consent) and its own permission prompts. Low but not zero;
  the received log makes it auditable.
- SSH client hardening: dedicated key, `StrictHostKeyChecking=yes`, no agent/X11/port forwarding.
- The bridge key on the VPS is `restrict` + forced command: a stolen laptop key only reaches the spool.

Alternatives considered: a git repo as mailbox (simple, but needs a GitHub write key on the VPS and minutes of
latency); an HTTPS relay on the VPS behind an SSH tunnel (more code, an open port, same trust result); Remote
Control (gives the VPS nothing, but it's Vals-to-session, not session-to-session).

## Permissions (`workspace/.claude/settings.json`)

Free: edits in `memory/`, `notes/`, `scratch/`, web search/fetch, a few read-only commands, the two reply tools.
Everything else prompts (relayed to Telegram as "yes <id>"). Denied: sudo/su/ssh/scp/crontab, reading `~/.ssh`,
credentials and `.env` files, editing its own settings, `~/.claude`, systemd units and the bridge code.
Caveat: deny rules bind Claude's tools, not the OS. Running as `vals` (in the sudo group, password needed; owns v1's
and discord-bridge's `.env`, the Claude login, the GitHub key), an approved Bash command can read them. Claude Code's
Bash sandbox (bubblewrap, needs `sudo apt install bubblewrap socat`) would make the file denies real: proposed.

## Go live (live ops, each step needs Vals' OK)

1. `git pull` on the VPS, `bash v2/install.sh` (no sudo; installs Bun 1.4.2, links units, starts nothing).
2. Vals by hand: BotFather token (new bot, v1 keeps its own), then in `tmux new -s vigil` from `~/vigil`:
   `claude`, `/plugin install telegram@claude-plugins-official`, `/telegram:configure <token>`, exit; start with
   `scripts/run-session.sh`, confirm the development-channel dialog and the `.mcp.json` server, DM the bot,
   `/telegram:access pair <code>`, `/telegram:access policy allowlist`.
3. Bridge key: laptop `ssh-keygen -t ed25519 -f ~/.ssh/vigil_bridge -N ''`; VPS `~/.ssh/authorized_keys` gets
   `command="python3 /home/vals/daemonVigil/v2/bridge/bridge-ssh.py",restrict <pubkey> vigil-bridge`.
4. Laptop coordinator: add `vigil-bridge` (mode laptop) to the workspace `.mcp.json` and launch it with
   `--dangerously-load-development-channels server:vigil-bridge`.
5. `systemctl --user enable --now vigil-heartbeat.timer vigil-session.service`; later stop v1
   (`bash stop.sh`, disable `daemon-vigil`) and migrate its history to `~/vigil/memory/archive/`.

## Restarts

The development-channel flag shows a confirmation dialog at every start (research preview). After a reboot or
crash: `ssh` in, `tmux attach -t vigil`, confirm. Automating that keypress is possible but bypasses a safety
dialog; not done.
