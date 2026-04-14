#!/bin/bash
# Copy, enable and prepare .service files located in the same directory as this script.
# Safe to run inside Docker (no active systemd): installs files but skips daemon-reload/enable.

# Determine the directory where this script resides
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SERVICE_DIR="$SCRIPT_DIR"
DEST_DIR="/etc/systemd/system"

echo "Copying service files from $SERVICE_DIR to $DEST_DIR..."

# Make sure the source directory exists
if [ ! -d "$SERVICE_DIR" ]; then
    echo "Error: $SERVICE_DIR does not exist."
    exit 1
fi

mkdir -p "$DEST_DIR"

# Copy all .service files
sudo cp "$SERVICE_DIR"/*.service "$DEST_DIR"/

# Install the FastDDS SHM profile to a fixed system path so fastdds-shm.service
# can reference it at /etc/ros/fastdds_shm.xml regardless of workspace location.
FASTDDS_XML="$SCRIPT_DIR/../../../docker/fastdds_shm.xml"
FASTDDS_XML="$(cd "$(dirname "$FASTDDS_XML")" && pwd)/$(basename "$FASTDDS_XML")"
if [ -f "$FASTDDS_XML" ]; then
    sudo mkdir -p /etc/ros /etc/environment.d
    sudo cp "$FASTDDS_XML" /etc/ros/fastdds_shm.xml
    echo "FASTRTPS_DEFAULT_PROFILES_FILE=/etc/ros/fastdds_shm.xml" \
        | sudo tee /etc/environment.d/fastdds-shm.conf > /dev/null
    echo "Installed FastDDS SHM profile to /etc/ros/fastdds_shm.xml"
    echo "Wrote /etc/environment.d/fastdds-shm.conf"
else
    echo "WARNING: $FASTDDS_XML not found — skipping FastDDS profile install"
fi

# Only reload/enable when systemd is actually running (not inside Docker build)
if pidof systemd > /dev/null 2>&1; then
    echo "Reloading systemd daemon..."
    sudo systemctl daemon-reexec
    sudo systemctl daemon-reload

    echo "Enabling all copied services to start on boot..."
    for file in "$SERVICE_DIR"/*.service; do
        # Skip if no .service files were found (glob expands to literal pattern)
        [ -e "$file" ] || continue
        service_name=$(basename "$file")
        sudo systemctl enable "$service_name"
        echo "Enabled $service_name"
    done
else
    echo "systemd not active — service files installed, skipping daemon-reload/enable"
fi

echo "Done. You can now start services with: systemctl start <service-name>, or start_services.sh"
