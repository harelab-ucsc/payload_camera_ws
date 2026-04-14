#!/bin/bash
# Start FRC payload systemd services and ROS2 launch.
# Used by run_tests.sh for integration tests and by the systemd service unit.

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
WS_ROOT="${WS_ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"

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

# Load FastDDS SHM profile — installed by install_services.sh.
# Systemd propagates /etc/environment.d/ automatically for services;
# source it here so manual runs also get the SHM transport.
if [ -f /etc/environment.d/fastdds-shm.conf ]; then
    set -a; . /etc/environment.d/fastdds-shm.conf; set +a
fi

# Launch ROS2 nodes (replaces shell process so signals propagate cleanly).
# Override LAUNCH_FILE to use a different launch file (e.g. test_launch.py for CI).
LAUNCH_FILE="${LAUNCH_FILE:-fast_launch.py}"
exec ros2 launch frc_payload_launcher "$LAUNCH_FILE"
