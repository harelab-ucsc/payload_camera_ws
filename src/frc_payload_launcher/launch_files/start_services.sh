#!/bin/bash
# Start FRC payload systemd services and ROS2 launch.
# Used by run_tests.sh for integration tests and by the systemd service unit.

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
WS_ROOT="${WS_ROOT:-/payload_camera_ws}"

# Start systemd services if systemd is active
if pidof systemd > /dev/null 2>&1; then
    for service_file in "$SCRIPT_DIR"/*.service; do
        [ -e "$service_file" ] || continue
        echo "Starting $(basename "$service_file")..."
        sudo systemctl start "$(basename "$service_file")"
    done
fi

# Source ROS2 environment — apt install (Docker) or source build (hardware)
if [ -f /opt/ros/iron/setup.sh ]; then
    . /opt/ros/iron/setup.sh
elif [ -f "$HOME/ros2/ros2_iron/install/setup.sh" ]; then
    . "$HOME/ros2/ros2_iron/install/setup.sh"
else
    echo "ERROR: could not find ROS2 Iron setup.sh" >&2
    exit 1
fi

if [ -f "$WS_ROOT/install/setup.sh" ]; then
    . "$WS_ROOT/install/setup.sh"
fi

# Launch ROS2 nodes (replaces shell process so signals propagate cleanly).
# Override LAUNCH_FILE to use a different launch file (e.g. test_launch.py for CI).
LAUNCH_FILE="${LAUNCH_FILE:-fast_launch.py}"
exec ros2 launch frc_payload_launcher "$LAUNCH_FILE"
