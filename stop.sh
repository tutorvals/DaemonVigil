#!/usr/bin/env bash
# Stop Daemon Vigil
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/.daemon_vigil.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "Daemon Vigil is not running (no pid file)"
    exit 0
fi

PID=$(cat "$PID_FILE")

if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    rm -f "$PID_FILE"
    echo "Daemon Vigil stopped (PID: $PID)"
else
    rm -f "$PID_FILE"
    echo "Daemon Vigil was not running (stale pid file cleaned up)"
fi
