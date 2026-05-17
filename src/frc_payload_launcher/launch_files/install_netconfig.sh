#!/bin/bash
# Install netplan configuration for the payload Pi.
# Copies netplan/pi.yaml to /etc/netplan/ and applies it when networkd is running.

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
NETPLAN_SRC="$SCRIPT_DIR/netplan/pi.yaml"
NETPLAN_DEST="/etc/netplan/50-oasis-payload.yaml"

if [ ! -f "$NETPLAN_SRC" ]; then
    echo "Error: netplan config not found at $NETPLAN_SRC"
    exit 1
fi

echo "Installing netplan config to $NETPLAN_DEST..."
sudo mkdir -p /etc/netplan
sudo cp "$NETPLAN_SRC" "$NETPLAN_DEST"
sudo chmod 600 "$NETPLAN_DEST"
echo "Installed $NETPLAN_DEST"

if pidof systemd > /dev/null 2>&1; then
    echo "Applying netplan config..."
    sudo netplan apply
    echo "Netplan applied."
else
    echo "systemd not active — netplan config installed, skipping netplan apply"
fi

echo "Done."
