# Daemon Vigil (v2: "Vigil")

An always-on Claude Code session on the VPS, reached through Telegram (official channel plugin), with a heartbeat
timer so it can reach out first, and a text-only bridge to the land-coordinator session on the laptop.
Rebuilt 2026-10-12 (Vals asked for a modern-stack rebuild; plan and history: `notes/v2-plan.md`,
`../coordination/briefs/vigil-v2.md`). v1 (Python bot) lives in `archive/v1/` (its own CLAUDE.md), not running.

Read `README.md` first: how the pieces fit, threat model, permissions, install, restarts.

## Layout

- `bridge/`: `vigil-bridge.ts` (Claude Code channel, Bun; `BRIDGE_MODE=vps|laptop`), `bridge-ssh.py` (VPS forced command)
- `heartbeat/`: timer script + settings example (parsed, never sourced)
- `workspace/`: the vigil agent's own `CLAUDE.md`, `.mcp.json`, `.claude/settings.json` (symlinked into `~/vigil`)
- `systemd/`: user units (session in tmux, heartbeat service + timer)
- `scripts/`: `run-session.sh` (VPS), `sync-context.sh` (laptop -> VPS workflow docs)
- `laptop/mcp.json`: the laptop-side bridge entry for the land-coordinator
- `install.sh`: VPS install, no sudo, idempotent

## Deployment (VPS: vals@167.233.85.125)

Remote path `~/daemonVigil`, origin `git@github.com:tutorvals/DaemonVigil.git` (branch `agentSDKUse`). The VPS
only pulls. Deploy: push locally, then `ssh vals@167.233.85.125 "cd ~/daemonVigil && git pull && bash install.sh"`.
Config changes in `workspace/` apply at the session's next start: `systemctl --user restart vigil-session`, then
confirm the development-channel dialog in `tmux attach -t vigil`.

## Rules for working here

- Test the bridge locally before deploying (see the progress log in the brief for the test harness approach).
- Permission path rules use `Edit(...)` only; `/x` anchors at the session's working directory (`~/vigil`).
- Never commit tokens; the Telegram token lives only in `~/.claude/channels/telegram/.env` on the VPS.
