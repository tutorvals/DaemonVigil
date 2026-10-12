# DaemonVigil v2 (Vigil)

Asked for (Vals, 2026-10-12): rebuild DaemonVigil as an always-on Claude Code on the VPS, reached through
Telegram, proactive, aware of how Vals works, able to talk to the laptop land-coordinator through a dedicated
bridge that carries only session-to-session messages. Runs as the existing user `vals` (Vals, 2026-10-12).
Design and code: Claude, 2026-10-12; Vals approved the plan 2026-10-12. v1 (Python bot, 2025-2026) is in
`archive/v1/`, stopped on the VPS 2026-10-12; its data was copied to `~/vigil/memory/archive/v1-data/`.

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
- `heartbeat/`: a systemd timer (30 min, quiet hours 01-11 Europe/Paris, editable in `~/vigil/heartbeat.env`) drops one event in the spool; skipped when
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

Free: edits in `~/vigil/{memory,notes,scratch}`, web search, `date`, `ls`, the heartbeat on/off file, the two reply
tools. Everything else prompts (relayed to Telegram as "yes <id>"), including WebFetch (a URL can carry data out).
Denied: sudo/su/ssh/scp/crontab, reading `~/.ssh`, credentials and `.env` files, editing `~/.claude`, the vigil
`.claude/`, `.mcp.json`, `CLAUDE.md`, all of `~/daemonVigil/` (the symlink targets, scripts and units),
`~/vigil/heartbeat.env` (also parsed, never sourced). Path rules use `Edit(...)` only (Claude Code ignores
`Write(path)` rules). Project allow rules apply only after the workspace trust dialog is accepted (headless test,
2026-10-12). The VPS only pulls from GitHub; nothing in v2 pushes (audit S3.1: its GitHub key is account-wide).
Caveat: deny rules bind Claude's tools, not the OS: running as `vals`, an approved Bash command can read the
`.env` files, the Claude login and the GitHub key. Vals declined the Bash sandbox (2026-10-12: "I trust claudes quite
a bit these days").

## Install and go live

1. VPS: `cd ~/daemonVigil && git pull && bash install.sh` (no sudo; Bun 1.4.2 in `~/.bun/bin`, `~/vigil`, units
   linked). `systemctl --user enable --now vigil-heartbeat.timer; systemctl --user enable vigil-session`.
2. Telegram plugin: `claude plugin marketplace add anthropics/claude-plugins-official` and
   `claude plugin install telegram@claude-plugins-official`. Token in `~/.claude/channels/telegram/.env`
   (`TELEGRAM_BOT_TOKEN=...`, mode 600).
3. First start (by hand): `tmux new -s vigil ~/daemonVigil/scripts/run-session.sh`; confirm the
   trust, development-channel and `.mcp.json` dialogs, then pair: DM the bot, `/telegram:access pair <code>`,
   `/telegram:access policy allowlist`. Afterwards `systemctl --user start vigil-session` runs it.
4. Bridge key: laptop `~/.ssh/vigil_bridge`; VPS `~/.ssh/authorized_keys` has
   `command="python3 /home/vals/daemonVigil/bridge/bridge-ssh.py",restrict <pubkey> vigil-bridge`.
5. Laptop coordinator (optional, B3): merge `laptop/mcp.json` into `~/claudeCodeLand/.mcp.json` and launch with
   `claude -n land-coordinator --dangerously-load-development-channels server:vigil-bridge`. Without it, the
   coordinator can still read vigil's messages: `ssh -i ~/.ssh/vigil_bridge vals@167.233.85.125 fetch`.

## Restarts

The development-channel flag shows a confirmation dialog at every start (research preview). After a reboot or
crash: `ssh` in, `tmux attach -t vigil`, confirm, detach (`Ctrl-b d`). Vals chose manual confirmation (2026-10-12).
