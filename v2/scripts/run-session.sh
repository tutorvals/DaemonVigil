#!/usr/bin/env bash
# The vigil session itself. Custom channels need the development flag during the research preview, which shows a
# confirmation dialog at each start: attach (tmux attach -t vigil) and confirm, or see README "Restarts".
cd "$HOME/vigil"
continue=()
[ -d "$HOME/.claude/projects/-home-vals-vigil" ] && continue=(--continue)  # resume the last conversation if any
exec claude "${continue[@]}" \
  --channels plugin:telegram@claude-plugins-official \
  --dangerously-load-development-channels server:vigil-bridge
