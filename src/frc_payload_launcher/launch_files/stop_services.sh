#!/bin/bash
# Stop FRC payload ROS2 launch and systemd services.
# Used by run_tests.sh for integration test teardown and general cleanup.

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Kill any running ros2 launch process (fast_launch.py or test_launch.py)
pkill -TERM -f "ros2 launch frc_payload_launcher" 2>/dev/null || true
sleep 1
pkill -KILL -f "ros2 launch frc_payload_launcher" 2>/dev/null || true

# Stop systemd services if systemd is active
if pidof systemd > /dev/null 2>&1; then
    for service_file in "$SCRIPT_DIR"/*.service; do
        [ -e "$service_file" ] || continue
        echo "Stopping $(basename "$service_file")..."
        sudo systemctl stop "$(basename "$service_file")"
    done
fi
