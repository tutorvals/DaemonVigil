#!/usr/bin/env bash
# Drops one heartbeat event into the vigil spool; the bridge channel pushes it into the session.
# Run by vigil-heartbeat.timer. Settings: ~/vigil/heartbeat.env (KEY=value lines, parsed not sourced).
# Off switch: touch ~/vigil/state/heartbeat-off (the agent may do this when Vals asks).
set -euo pipefail
VIGIL="${VIGIL_HOME:-$HOME/vigil}"
VIGIL_TZ=Europe/Paris QUIET_START=23 QUIET_END=8
# Parsed, never sourced: only these three keys, only safe values (the file must not become code execution).
if [ -f "$VIGIL/heartbeat.env" ]; then
  while IFS='=' read -r key value; do
    case "$key" in
      VIGIL_TZ) [[ "$value" =~ ^[A-Za-z0-9_+/-]{1,40}$ ]] && VIGIL_TZ="$value" ;;
      QUIET_START) [[ "$value" =~ ^([01]?[0-9]|2[0-3])$ ]] && QUIET_START="$value" ;;
      QUIET_END) [[ "$value" =~ ^([01]?[0-9]|2[0-3])$ ]] && QUIET_END="$value" ;;
    esac
  done < "$VIGIL/heartbeat.env"
fi

[ -e "$VIGIL/state/heartbeat-off" ] && exit 0
hour=$(TZ="$VIGIL_TZ" date +%-H)
if [ "$QUIET_START" -gt "$QUIET_END" ]; then
  { [ "$hour" -ge "$QUIET_START" ] || [ "$hour" -lt "$QUIET_END" ]; } && exit 0
else
  { [ "$hour" -ge "$QUIET_START" ] && [ "$hour" -lt "$QUIET_END" ]; } && exit 0
fi

inbox="$VIGIL/spool/inbox"
mkdir -p "$inbox"
# Skip if the previous heartbeat hasn't been picked up (session down): no pile-up after an outage.
ls "$inbox"/*-heartbeat.json >/dev/null 2>&1 && exit 0
now=$(TZ="$VIGIL_TZ" date '+%Y-%m-%d %H:%M %Z (%A)')
name="$(date -u +%Y-%m-%dT%H-%M-%SZ)-heartbeat.json"
printf '{"from":"heartbeat","text":"Heartbeat at %s. Follow the Heartbeat section of CLAUDE.md."}\n' "$now" > "$inbox/.$name"
mv "$inbox/.$name" "$inbox/$name"
