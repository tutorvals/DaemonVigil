#!/usr/bin/env bash
# Root install of vigil-ops (run by Vals: sudo bash ~/daemonVigil/ops/install-root.sh). Idempotent.
# Copies (not links) so the root-run code can't be changed by the vals user; re-run after reviewing a git pull.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
here="$(cd "$(dirname "$0")" && pwd)"
install -o root -g root -m 0755 "$here/vigil-ops" /usr/local/sbin/vigil-ops
install -o root -g root -m 0755 "$here/vigil-request" /usr/local/bin/vigil-request
install -o root -g root -m 0644 "$here"/vigil-sense.{service,timer} "$here"/vigil-act.{path,service} /etc/systemd/system/
install -d -o root -g root -m 0755 /etc/vigil
[ -f /etc/vigil/vigil.toml ] || install -o root -g root -m 0644 "$here/vigil.toml.example" /etc/vigil/vigil.toml
install -d -o root -g root -m 0700 /var/lib/vigil
install -d -o root -g vals -m 0730 /var/lib/vigil/requests   # vals may drop files, not list or read them
chmod 0711 /var/lib/vigil                                    # vals needs to traverse to requests/
[ -f /etc/vigil/alarm.env ] || echo "note: no /etc/vigil/alarm.env yet: high alarms go to vigil only, and 'confirm' actions are refused"
systemctl daemon-reload
systemctl enable --now vigil-sense.timer vigil-act.path
echo "installed; check: sudo vigil-ops status; journalctl -u vigil-sense -n 20"
