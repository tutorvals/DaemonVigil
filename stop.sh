#!/usr/bin/env bash
# Stop Daemon Vigil (it stays enabled, so it will start again at boot)
set -e

systemctl --user stop daemon-vigil.service 2>/dev/null || true
echo "Daemon Vigil stopped"
