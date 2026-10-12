#!/usr/bin/env bash
# Laptop side: copy a curated, read-only snapshot of how Vals works to the VPS (~/vigil/context/).
# Direction laptop -> VPS only. Nothing Professional or Strict, no secrets (security/POLICY.md: these are Low).
set -euo pipefail
LAND="$HOME/claudeCodeLand"
TARGET="${VIGIL_SSH_TARGET:-vals@167.233.85.125}"
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
cp "$HOME/.claude/CLAUDE.md"            "$stage/global-CLAUDE.md"
cp "$LAND/CLAUDE.md"                    "$stage/claudeCodeLand-CLAUDE.md"
cp "$LAND/coordination/README.md"       "$stage/coordination-README.md"
cp "$LAND/coordination/BACKLOG.md"      "$stage/BACKLOG.md"
cp "$LAND/security/POLICY.md"           "$stage/security-POLICY.md"
date -Iseconds > "$stage/SYNCED_AT"
rsync -a --delete "$stage/" "$TARGET:vigil/context/"
echo "synced to $TARGET:~/vigil/context/"
