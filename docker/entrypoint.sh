#!/bin/bash
set -e

# Source ROS2 Iron base
source /opt/ros/iron/setup.bash

# Source the built workspace if it exists
if [ -f /payload_camera_ws/install/setup.bash ]; then
    source /payload_camera_ws/install/setup.bash
fi

exec "$@"
