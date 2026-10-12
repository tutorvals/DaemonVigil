#!/usr/bin/env bash
# Drops one heartbeat event into the vigil spool; the bridge channel pushes it into the session.
# Run by vigil-heartbeat.timer. Settings: ~/vigil/heartbeat.env (copied from heartbeat.env.example by install.sh).
# Off switch: touch ~/vigil/state/heartbeat-off (the agent may do this when Vals asks).
set -euo pipefail
VIGIL="${VIGIL_HOME:-$HOME/vigil}"
# shellcheck disable=SC1091
[ -f "$VIGIL/heartbeat.env" ] && . "$VIGIL/heartbeat.env"
: "${VIGIL_TZ:=Europe/Paris}" "${QUIET_START:=23}" "${QUIET_END:=8}"

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
