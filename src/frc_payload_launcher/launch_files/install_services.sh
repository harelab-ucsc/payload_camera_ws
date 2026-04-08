#!/bin/bash
# Copy, enable and prepare .service files located in the same directory as this script

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

# Copy all .service files (requires sudo for the destination)
sudo cp "$SERVICE_DIR"/*.service "$DEST_DIR"/

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

echo "Done. You can now start services with: systemctl start <service-name>, or start_services.sh"
