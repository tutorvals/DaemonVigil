# DaemonVigil v2: plan (checkpoint 1, 2026-10-12)

Asked for (Vals, 2026-10-12): rebuild DaemonVigil on a modern stack: an always-on Claude Code on the Hetzner VPS,
pinged through Telegram, doing local work with approval, knowing how Vals works (land-coordinator), maybe bridging
to the laptop session. Everything below is Claude's proposal (TENTATIVE). Research: web, 2026-10-12, mostly
third-party write-ups; verify against code.claude.com docs before building. No VPS check was run yet.

## 1. What exists now (keep / port / drop)

| Feature | Verdict | Why |
|---|---|---|
| Telegram chat with Claude (python-telegram-bot + Agent SDK, ~2.2k lines) | drop the code | Claude Code Channels (Telegram plugin) does this first-party |
| Proactive heartbeat (APScheduler, Claude decides to speak or stay silent) | port | The distinctive feature; Channels has no proactive loop. Redo as a cron/systemd timer that pushes a "heartbeat" event into the session |
| Quiet hours + timezone | port (simple) | Check inside the heartbeat timer |
| Scratchpad memory | port as files | A `memory/` folder + CLAUDE.md in the agent's workdir; Claude Code memory replaces the JSON |
| Conversation history (messages.json) | port once, read-only archive | Useful context; no live format needed |
| Per-user model / interval config, `...` commands | drop most | Single user now; `/model` etc. exist in Claude Code; keep `heartbeat on/off/interval` as a tiny script |
| Multi-user auto-registration | drop | Security risk (any Telegram user gets an agent); v2 is allowlist-only |
| Usage/billing tracking (api_usage.jsonl) | drop | Plan usage is visible via status line rate-limits file |
| systemd user unit, start/stop.sh | keep pattern | Same ops model, new unit |
| syncthing folder | look | Purpose unclear; decide at migration |

## 2. Architecture options

- **O1 (default): Claude Code + official Telegram Channel plugin**, in a persistent tmux/systemd session on the VPS
  (`claude --channels plugin:telegram@claude-plugins-official`, v2.1.80+, Bun; research preview since 2026-03-20).
  Pros: first-party, full Claude Code (skills, hooks, CLAUDE.md, permissions), claude.ai login (no API key), little
  code. Cons: preview (flags may change), a long-lived interactive session needs babysitting (restarts, context
  compaction), approvals arrive as prompts in the terminal unless relayed.
- **O2: thin custom bot + Agent SDK / `claude -p` headless** (v1's shape, modernised). Pros: full control of
  approval flow (inline "Approve/Deny" buttons in Telegram), per-message sessions, stable. Cons: we maintain the
  bot again (~500 lines), reimplement what Channels gives.
- **O3: no VPS agent; Remote Control on the laptop** (Feb 2026, outbound-only, phone app). Pros: zero server, real
  laptop context. Cons: dead when the laptop sleeps; not proactive.
Recommended: O1, with a fallback to O2 if approvals over Telegram turn out clumsy in a 1-day spike. O3 is a cheap
complement for the bridge (section 5).

## 3. Approvals and security

- Who: Telegram allowlist of Vals' user id only (pairing, then allowlist mode); Discord later if wanted.
- Unapproved: read files in its workdir, web search, write in its own `vigil/` workspace and memory. Needs approval
  (Telegram yes/no): any other write, network-changing or package commands, git push, messages to others. Deny
  outright: sudo, ssh keys, `~/.claude` config edits, reading other projects' `.env`.
- Run as a dedicated unprivileged user (`vigil`), not `vals`; no sudo; its own git deploy key (read-only on repos it
  doesn't own). April 2026 lesson: the box was taken via SSH password brute force, so keep key-only SSH, fail2ban/ufw
  (check these are still on), and assume a compromised agent session = a shell: no Strict data, no cross-project
  secrets, rotateable tokens (bot token, claude login) listed in one place.
- Prompt injection: web pages and incoming messages are untrusted; the allowlist plus approvals is the main guard.

## 4. Learning Vals' ways of working

Sync a curated subset to the VPS via a git repo (private): global `~/.claude/CLAUDE.md`, `claudeCodeLand/CLAUDE.md`,
`coordination/README.md` + BACKLOG.md (read-only snapshot), `security/POLICY.md`, and `claude-setup` installed via
`./setup.sh install` (minus laptop-only hooks). Not synced: other projects' data, `.env`s, Strict anything.

## 5. Bridge to the laptop land-coordinator

Feasible but not first-party: cross-session SendMessage is local-only. Options: (a) Remote Control on the laptop
coordinator, so Vals hops to it from the phone (simple, no agent-to-agent link); (b) a shared private git repo /
file drop: the coordinator writes a daily `status.md` (backlog, latest sessions) that vigil reads, and vigil leaves
notes in an inbox file the coordinator reads on wake; (c) a direct tunnel (Tailscale + local MCP): most capable,
widest attack surface (a VPS compromise reaches the laptop). Default: (b) one-way-each-way via git, plus (a) for Vals.

## 6. Migration

Build v2 alongside v1 with a new bot token; when it works, stop v1, export the one real user's messages/scratchpad
into `vigil/memory/archive/`, archive the old repo branch.

## 7. Effort

Human prior ~4-5 days (spike 1d, hardening/user/approvals 1-2d, heartbeat + sync 1d, migration 0.5d). Agent-recalibrated
~half a day to a day of agent time, plus Vals' time for BotFather, login on the VPS and approving live steps.
