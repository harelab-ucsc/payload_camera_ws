#!/usr/bin/env bash
# docker/run_tests.sh
#
# Discovers and runs all tests inside docker/tests/ and src/*/test/.
# Intended to be called from within the Docker container.
#
# Usage (inside container):
#   bash /payload_camera_ws/docker/run_tests.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TESTS_DIR="$SCRIPT_DIR/tests"
LAUNCH_FILES="$WS_ROOT/src/frc_payload_launcher/launch_files"

# Source ROS2 and workspace environments
. /opt/ros/iron/setup.sh
if [ -f /payload_camera_ws/install/setup.sh ]; then
    . /payload_camera_ws/install/setup.sh
fi

# Ensure no leftover services from a previous run
echo "[run_tests.sh] Stopping any running services (clean state)"
bash "$LAUNCH_FILES/stop_services.sh"

echo "[run_tests.sh] Discovering tests"

# Collect unit/integration test files from docker/tests/ and src/*/test/.
# Ament lint tests (test_flake8, test_pep257, test_copyright) are excluded here
# because they use the CWD to discover source files — running them from the
# workspace root would incorrectly scan vendored third-party packages.
# They are run separately per-package below.
mapfile -t test_files < <(find \
    "$TESTS_DIR" \
    "$WS_ROOT/src" \
    \( -name "test_*.py" -o -name "*_test.py" \) \
    ! -name "test_flake8.py" \
    ! -name "test_copyright.py" \
    ! -name "test_pep257.py" \
    | sort -u 2>/dev/null || true)

if [ "${#test_files[@]}" -eq 0 ]; then
    echo "[run_tests.sh] No test files found in $TESTS_DIR"
    exit 0
fi

# Separate integration tests (need services running) from unit tests (services stopped)
mapfile -t integration_files < <(printf '%s\n' "${test_files[@]}" | grep "test_integration" || true)
mapfile -t unit_files        < <(printf '%s\n' "${test_files[@]}" | grep -v "test_integration" || true)

echo "[run_tests.sh] Found ${#test_files[@]} test file(s) (${#unit_files[@]} unit, ${#integration_files[@]} integration):"
printf '  %s\n' "${test_files[@]}"
echo ""

# ── Unit tests (services stopped) ─────────────────────────────────────────────
if [ "${#unit_files[@]}" -gt 0 ]; then
    echo "[run_tests.sh] Running unit tests (services stopped)"
    python3 -m pytest --import-mode=importlib "${unit_files[@]}" -v -s
    echo ""
fi

# ── Integration tests (services started via start_services.sh + fast_launch.py)
if [ "${#integration_files[@]}" -gt 0 ]; then
    echo "[run_tests.sh] Starting services for integration tests (mock launch)"
    LAUNCH_FILE=test_launch.py bash "$LAUNCH_FILES/start_services.sh" &
    LAUNCH_PID=$!

    # Wait for fake publishers + stamp_split to initialise and DDS to settle.
    # Extra time needed: 5120×800 frames take longer to route through DDS than small ones.
    sleep 15

    INTEGRATION_RC=0
    python3 -m pytest --import-mode=importlib "${integration_files[@]}" -v -s || INTEGRATION_RC=$?

    echo "[run_tests.sh] Stopping services after integration tests"
    bash "$LAUNCH_FILES/stop_services.sh"
    wait "$LAUNCH_PID" 2>/dev/null || true
    echo ""

    [ $INTEGRATION_RC -ne 0 ] && exit $INTEGRATION_RC
fi

# ── Per-package lint tests ─────────────────────────────────────────────────────
# Run ament lint tests (flake8, pep257, copyright) from within each package
# directory so they only check files belonging to that package.
echo "[run_tests.sh] Running per-package lint tests"

mapfile -t lint_files < <(find \
    "$WS_ROOT/src" \
    \( -name "test_flake8.py" -o -name "test_copyright.py" -o -name "test_pep257.py" \) \
    | sort -u 2>/dev/null || true)

for f in "${lint_files[@]}"; do
    pkg_dir="$(dirname "$f")"
    while [[ "$pkg_dir" != "/" && "$pkg_dir" != "$WS_ROOT" && ! -f "$pkg_dir/package.xml" ]]; do
        pkg_dir="$(dirname "$pkg_dir")"
    done
    if [[ ! -f "$pkg_dir/package.xml" ]]; then
        echo "[run_tests.sh] WARNING: no package.xml found for $f, skipping"
        continue
    fi
    echo "[run_tests.sh] Linting $(basename "$pkg_dir") (from $pkg_dir):"
    pushd "$pkg_dir" > /dev/null
    python3 -m pytest --import-mode=importlib "$f" -v -s
    popd > /dev/null
done
