#!/bin/bash
set -e

# Source ROS2 Iron base
source /opt/ros/iron/setup.bash

# Source the built workspace if it exists
if [ -f /payload_camera_ws/install/setup.bash ]; then
    source /payload_camera_ws/install/setup.bash
fi

# Load environment.d files (systemd does this automatically on hardware;
# we replicate it here so the container behaves the same without systemd)
if [ -d /etc/environment.d ]; then
    for f in /etc/environment.d/*.conf; do
        [ -f "$f" ] && set -a && . "$f" && set +a
    done
fi

exec "$@"
