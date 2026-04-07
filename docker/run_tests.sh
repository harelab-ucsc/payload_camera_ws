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
WS_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TESTS_DIR="$SCRIPT_DIR/tests"

# Source ROS2 and workspace environments
. /opt/ros/iron/setup.sh
if [ -f /payload_camera_ws/install/setup.sh ]; then
    . /payload_camera_ws/install/setup.sh
fi

echo "[run_tests.sh] Discovering tests"

# Collect test files from docker/tests/ and all src/*/test/ directories
mapfile -t test_files < <(find \
    "$TESTS_DIR" \
    "$WS_ROOT/src" \
    \( -name "test_*.py" -o -name "*_test.py" \) \
    | sort -u 2>/dev/null || true)

if [ "${#test_files[@]}" -eq 0 ]; then
    echo "[run_tests.sh] No test files found in $TESTS_DIR"
    exit 0
fi

echo "[run_tests.sh] Found ${#test_files[@]} test file(s) across docker/tests/ and src/*/test/:"
printf '  %s\n' "${test_files[@]}"
echo ""

python3 -m pytest --import-mode=importlib "${test_files[@]}" -v -s
