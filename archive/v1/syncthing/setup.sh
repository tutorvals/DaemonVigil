#!/usr/bin/env bash
set -euo pipefail

# Idempotent Syncthing setup for DaemonVigil data/ sync.
# Run on both the VPS and local PC.

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="$REPO_ROOT/data"
FOLDER_ID="daemonvigil-data"
FOLDER_LABEL="DaemonVigil Data"
SYNCTHING_USER="${SUDO_USER:-$USER}"

# --- Install Syncthing if not present ---
if ! command -v syncthing &>/dev/null; then
    echo "==> Installing Syncthing..."
    sudo mkdir -p /etc/apt/keyrings
    sudo curl -fsSL -o /etc/apt/keyrings/syncthing-archive-keyring.gpg \
        https://syncthing.net/release-key.gpg
    echo "deb [signed-by=/etc/apt/keyrings/syncthing-archive-keyring.gpg] https://apt.syncthing.net/ syncthing stable" \
        | sudo tee /etc/apt/sources.list.d/syncthing.list >/dev/null
    sudo apt-get update -qq
    sudo apt-get install -y syncthing
else
    echo "==> Syncthing already installed: $(syncthing --version | head -1)"
fi

# --- Enable and start the systemd service ---
echo "==> Enabling syncthing service for user '$SYNCTHING_USER'..."
sudo systemctl enable "syncthing@${SYNCTHING_USER}"
sudo systemctl start "syncthing@${SYNCTHING_USER}"

# Wait for Syncthing to generate its config on first run
echo "==> Waiting for Syncthing to initialize..."
for i in $(seq 1 15); do
    if syncthing cli config version get &>/dev/null 2>&1; then
        break
    fi
    sleep 1
done

# --- Add the data/ folder if not already shared ---
EXISTING=$(syncthing cli config folders list 2>/dev/null || true)
if echo "$EXISTING" | grep -q "^${FOLDER_ID}$"; then
    echo "==> Folder '$FOLDER_ID' already configured in Syncthing."
else
    echo "==> Adding folder '$FOLDER_ID' -> $DATA_DIR"
    syncthing cli config folders add --id "$FOLDER_ID" --path "$DATA_DIR" --label "$FOLDER_LABEL"
    # Set folder type to "sendreceive" (two-way sync, the default)
    syncthing cli config folders "$FOLDER_ID" type set sendreceive
fi

# --- Print device ID ---
echo ""
echo "============================================"
echo "  Syncthing is running!"
echo "============================================"
echo ""
DEVICE_ID=$(syncthing cli config devices list 2>/dev/null | head -1)
if [ -z "$DEVICE_ID" ]; then
    DEVICE_ID=$(syncthing -device-id 2>/dev/null || echo "(could not determine)")
fi
echo "This device's ID:"
echo "  $DEVICE_ID"
echo ""
echo "Next steps:"
echo "  1. Run this script on the other machine too."
echo "  2. Open Syncthing GUI: http://localhost:8384"
echo "  3. Add each machine's device ID to the other."
echo "  4. Share the '$FOLDER_LABEL' folder with the remote device."
echo ""
