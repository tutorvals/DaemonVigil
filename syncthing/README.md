# Syncthing Setup for DaemonVigil

Two-way sync of the `data/` directory between VPS and local PC.

## What gets synced

Only `data/` directory:
- `api_usage.jsonl` — usage log
- `billing_thresholds.json` — threshold state
- `users.json` — user registry
- `users/<user_id>/` — per-user messages, scratchpad, config

**Not synced:** `.env` (secrets, stays manual per machine), `config.yaml` (git-tracked).

## Setup

### On each machine (VPS and local PC)

```bash
cd /path/to/daemonVigil
bash syncthing/setup.sh
```

The script will:
- Install Syncthing from the official apt repo (if not already installed)
- Enable it as a systemd service (survives reboots)
- Configure it to share `data/` with folder ID `daemonvigil-data`
- Print the local device ID

### Pair the devices

1. Copy the device ID printed by the script on each machine.
2. Open the Syncthing GUI on each machine: http://localhost:8384
3. **Add Remote Device** → paste the other machine's device ID.
4. Accept the shared folder (`DaemonVigil Data`) when prompted.

Sync will start automatically once both sides are paired.

## Useful commands

```bash
# Check service status
systemctl status syncthing@$USER

# View logs
journalctl -u syncthing@$USER -f

# Restart
sudo systemctl restart syncthing@$USER
```
