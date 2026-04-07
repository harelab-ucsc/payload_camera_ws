#!/usr/bin/env bash
# docker/run_tests.sh
#
# Discovers and runs all tests inside docker/tests/.
# Intended to be called from within the Docker container.
#
# Usage (inside container):
#   bash /payload_camera_ws/docker/run_tests.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTS_DIR="$SCRIPT_DIR/tests"

# Source ROS2 and workspace environments
. /opt/ros/iron/setup.sh
if [ -f /payload_camera_ws/install/setup.sh ]; then
    . /payload_camera_ws/install/setup.sh
fi

echo "[run_tests.sh] Discovering tests in $TESTS_DIR"

# Collect test files matching pytest naming conventions
mapfile -t test_files < <(find "$TESTS_DIR" -name "test_*.py" -o -name "*_test.py" | sort)

if [ "${#test_files[@]}" -eq 0 ]; then
    echo "[run_tests.sh] No test files found in $TESTS_DIR"
    exit 0
fi

echo "[run_tests.sh] Found ${#test_files[@]} test file(s):"
printf '  %s\n' "${test_files[@]}"
echo ""

python3 -m pytest "${test_files[@]}" -v -s
