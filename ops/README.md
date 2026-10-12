# ops/: the root side of vigil's security loop

Asked for (Vals, 2026-10-12, VPS security thread): alerts from programs that ping the always-on vigil, which triages
and can react (block, kill, stop); vigil's 3 automatic actions "for now", easy to change; and guards that make risky
actions hard, which vigil can lift once Vals confirms by typing back a program-generated 4-letter word, verified by a
program, not by the model. Plan: `~/claudeCodeLand/security/vps/plan.md` S5 (local, git-ignored).
Design and code: Claude, 2026-10-12, TENTATIVE until Vals reviews it. Not installed yet (needs sudo: `install-root.sh`).

## How the pieces fit

```
vigil-sense.timer (root, 1 min) ─> vigil-ops sense ─> events.jsonl ─┬─> ~/vigil/spool/inbox (from "sensor") ─> vigil
                                         │                           └─> high only: alarm bot ─> Vals (Telegram)
                                         └─> re-applies guards (sudo window closed, files immutable) when no lift is active
vigil ─> vigil-request <action> ─> /var/lib/vigil/requests/*.json ─> vigil-act.path ─> vigil-ops act
          policy in /etc/vigil/vigil.toml:  auto ─> runs, alarm bot tells Vals
                                            confirm ─> alarm bot sends Vals the request + a code; Vals sends the
                                                       code to vigil; `vigil-request confirm CODE` ─> runs
                                            off ─> refused
          result ─> ~/vigil/spool/inbox (from "actions") ─> vigil
```

| File | Installed as | What |
|---|---|---|
| `vigil-ops` | `/usr/local/sbin/vigil-ops` (root) | sensor, action runner, guards; Python stdlib |
| `vigil-request` | `/usr/local/bin/vigil-request` | vals side: queues a request (validates nothing that matters; root does) |
| `vigil.toml.example` | `/etc/vigil/vigil.toml` | the one config: action policies, allowlists, watched files |
| `vigil-sense.{service,timer}`, `vigil-act.{path,service}` | `/etc/systemd/system/` | system units |
| `install-root.sh` | | `sudo bash install-root.sh`: copies, enables; idempotent |
| `VIGIL.md` | | vigil's instructions for events and actions (linked from `workspace/CLAUDE.md`) |

The alarm bot: a second Telegram bot (BotFather), token and Vals' chat id in `/etc/vigil/alarm.env` (root, 0600:
`TELEGRAM_ALARM_TOKEN=...`, `TELEGRAM_ALARM_CHAT=...`). Root-only so a compromised `vals` can't silence alarms or read
codes. Without it, high alarms reach only vigil and every "confirm" action is refused.

## Choices (Claude, 2026-10-12, TENTATIVE)

- **A request spool instead of sudo wrappers** (the plan had `vigil-block` and `vigil-upgrade-thirdparty` behind a
  sudoers rule). vigil's settings deny `sudo` (and should keep doing so); the spool needs no sudoers rule, and one
  root program owns validation, logging and the policy. Same trust result: `vals` can queue requests either way.
- **Why the code proves Vals agreed:** the code exists only in root's memory and in the alarm bot's message to Vals
  (stored hashed). vigil sees it only after Vals types it. The request text Vals reads is written by the program,
  not paraphrased by the model. Codes: 4 letters (consonant-vowel x2, 5625 words), 10 min, single use; 3 wrong
  codes cancel all pending requests and alarm Vals.
- **Guards built now:** `sudo-window` (vals gets passwordless sudo for up to 60 min). Inert while vigil's settings
  deny `sudo`; useful if Vals moves `sudo` from deny to ask there (each command would still need his "yes <id>") and `unlock-files` (`authorized_keys`, `.bashrc`,
  `.profile` stay `chattr +i`; Vals himself: `sudo vigil-ops lift unlock-files 15`). Guards re-apply within a
  minute after the lift ends.
- **Sensor scope** (plan S5): SSH logins from new IPs/keys, root logins, sudo/su, new listeners, binaries in temp
  dirs / memfd / deleted, new outbound networks (learned silently for 14 days, then low events), hash changes on
  watched paths, dpkg installs. First run learns a baseline (30 days of logins) without events.
- Not chosen: AIDE (files only, heavier), auditd (precise but noisy), Falco/osquery (too heavy for 4 GB).

## Limits

A root-level attacker can switch all of this off. Blocks live in an nftables table (`inet vigil`) and vanish at
reboot (they expire after 24 h anyway). `kill-process` saves evidence (binary, maps, environ, connections) under
`/var/lib/vigil/evidence/` (root only; environ can hold secrets).
