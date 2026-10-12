#!/usr/bin/env bash
# VPS-side install, no sudo. Idempotent. Run from ~/daemonVigil after git pull: bash v2/install.sh
# Does: Bun (pinned) in ~/.bun, bridge deps, ~/vigil workspace (symlinked config), systemd user units linked.
# Does NOT enable or start anything: see README "Go live".
set -euo pipefail
V2="$(cd "$(dirname "$0")" && pwd)"
VIGIL="$HOME/vigil"
BUN_VERSION="1.4.2"

if ! [ -x "$HOME/.bun/bin/bun" ]; then
  curl -fsSL https://bun.sh/install | bash -s "bun-v$BUN_VERSION"
fi
(cd "$V2/bridge" && "$HOME/.bun/bin/bun" install --frozen-lockfile)

mkdir -p "$VIGIL"/{memory/archive,notes,scratch,state,context,spool/{inbox,outbox,done,sent},.claude}
chmod 700 "$VIGIL" "$VIGIL/spool"
ln -sfn "$V2/workspace/CLAUDE.md" "$VIGIL/CLAUDE.md"
ln -sfn "$V2/workspace/.mcp.json" "$VIGIL/.mcp.json"
ln -sfn "$V2/workspace/.claude/settings.json" "$VIGIL/.claude/settings.json"
[ -f "$VIGIL/heartbeat.env" ] || cp "$V2/heartbeat/heartbeat.env.example" "$VIGIL/heartbeat.env"

mkdir -p "$HOME/.config/systemd/user"
for u in vigil-session.service vigil-heartbeat.service vigil-heartbeat.timer; do
  ln -sfn "$V2/systemd/$u" "$HOME/.config/systemd/user/$u"
done
systemctl --user daemon-reload
echo "Installed. Not started. Next: README 'Go live'."
