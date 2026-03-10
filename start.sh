#!/usr/bin/env bash
# Start Daemon Vigil in the background
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Stop an existing tracked process if present.
if [ -f ".daemon_vigil.pid" ]; then
    OLD_PID="$(cat .daemon_vigil.pid)"
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "Stopping existing Daemon Vigil process (PID: $OLD_PID)..."
        kill "$OLD_PID" || true
        sleep 1
    fi
    rm -f .daemon_vigil.pid
fi

# Best-effort cleanup for stray Daemon Vigil processes not tracked by the pid file.
pkill -f "/home/.*/daemonVigil/venv/bin/python main.py --silent" 2>/dev/null || true
pkill -f "python main.py --silent" 2>/dev/null || true
sleep 1

# Activate venv if it exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

PYTHON_BIN="python"
if [ -x "venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/venv/bin/python"
fi

echo "Starting Daemon Vigil..."
nohup "$PYTHON_BIN" main.py --silent > daemon_vigil.log 2>&1 &
PID=$!
echo "$PID" > .daemon_vigil.pid
echo "Daemon Vigil started (PID: $PID)"
echo "Logs: tail -f $SCRIPT_DIR/daemon_vigil.log"
echo "Stop:  kill $PID"
