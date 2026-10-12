#!/usr/bin/env bash
# VPS-side install, no sudo. Idempotent. Run from ~/daemonVigil after git pull: bash install.sh
# Does: Bun (pinned) in ~/.bun, bridge deps, ~/vigil workspace (symlinked config), systemd user units linked.
# Does NOT enable or start anything: see README "Install and go live".
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"  # repo root
VIGIL="$HOME/vigil"
BUN_VERSION="1.4.2"

if ! [ -x "$HOME/.bun/bin/bun" ]; then
  # Release zip unpacked with Python (the official installer needs unzip, which needs sudo; it also edits .bashrc)
  tmp=$(mktemp -d)
  curl -fsSL -o "$tmp/bun.zip" "https://github.com/oven-sh/bun/releases/download/bun-v$BUN_VERSION/bun-linux-x64.zip"
  python3 -m zipfile -e "$tmp/bun.zip" "$tmp"
  mkdir -p "$HOME/.bun/bin"
  install -m 755 "$tmp/bun-linux-x64/bun" "$HOME/.bun/bin/bun"
  rm -rf "$tmp"
fi
(cd "$ROOT/bridge" && "$HOME/.bun/bin/bun" install --frozen-lockfile)

mkdir -p "$VIGIL"/{memory/archive,notes,scratch,state,context,spool/{inbox,outbox,done,sent},.claude}
chmod 700 "$VIGIL" "$VIGIL/spool"
ln -sfn "$ROOT/workspace/CLAUDE.md" "$VIGIL/CLAUDE.md"
ln -sfn "$ROOT/workspace/.mcp.json" "$VIGIL/.mcp.json"
ln -sfn "$ROOT/workspace/.claude/settings.json" "$VIGIL/.claude/settings.json"
[ -f "$VIGIL/heartbeat.env" ] || cp "$ROOT/heartbeat/heartbeat.env.example" "$VIGIL/heartbeat.env"

mkdir -p "$HOME/.config/systemd/user"
for u in vigil-session.service vigil-heartbeat.service vigil-heartbeat.timer; do
  ln -sfn "$ROOT/systemd/$u" "$HOME/.config/systemd/user/$u"
done
systemctl --user daemon-reload
echo "Installed. Not started. Next: README 'Install and go live'."
