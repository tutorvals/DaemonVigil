#!/usr/bin/env bash
# (Re)start Daemon Vigil as a systemd user service (auto-restarts, survives reboots with linger)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
UNIT=daemon-vigil.service

# One-time migration: stop a legacy nohup process tracked by the old pid file.
if [ -f ".daemon_vigil.pid" ]; then
    OLD_PID="$(cat .daemon_vigil.pid)"
    kill "$OLD_PID" 2>/dev/null && echo "Stopped legacy process (PID: $OLD_PID)" || true
    rm -f .daemon_vigil.pid
    sleep 1
fi

systemctl --user enable "$SCRIPT_DIR/systemd/$UNIT" >/dev/null 2>&1 || true
systemctl --user daemon-reload
systemctl --user restart "$UNIT"
systemctl --user --no-pager status "$UNIT" | head -3

if [ "$(loginctl show-user "$USER" -p Linger --value)" != "yes" ]; then
    echo "WARNING: linger is off, service won't start at boot. Fix: sudo loginctl enable-linger $USER"
fi
echo "Logs: tail -f $SCRIPT_DIR/daemon_vigil.log"
