#!/usr/bin/env bash
# Start Daemon Vigil in the background
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

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
