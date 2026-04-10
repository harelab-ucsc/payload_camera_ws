# Docker Testing

Builds the workspace in a ROS2 Iron container and runs all tests as a separate step.

## Build

```bash
docker build -f docker/Dockerfile -t payload_camera_ws:iron .
```

The build step installs the systemd service files from `frc_payload_launcher/launch_files/`
to `/etc/systemd/system/` via `install_services.sh`. When no systemd daemon is running
(e.g. inside Docker), the file copy still happens but `daemon-reload`/`enable` are skipped.

Tests are **not** run during the build by default. To include them:

```bash
docker build -f docker/Dockerfile --build-arg RUN_TESTS=true -t payload_camera_ws:iron .
```

## Run tests

```bash
docker run --rm --shm-size 512m payload_camera_ws:iron bash /payload_camera_ws/docker/run_tests.sh
```

`--shm-size 512m` is required because the integration test uses FastDDS shared-memory
transport to route ~12 MB frames between same-container processes without UDP fragmentation.
FastDDS allocates one 16 MB SHM segment per DataWriter; with ~11 DataWriters the peak
usage is ~176 MB — 512 MB gives comfortable headroom.

## Test structure

`run_tests.sh` runs three groups in order:

### 1. Unit tests (services stopped)

All `test_*.py` / `*_test.py` files found under `docker/tests/` and `src/*/test/`,
excluding ament lint files. Services are stopped first to ensure a clean state.

Currently includes:
- `src/pps_time_pub/test/test_pps_time_pub.py` — unit tests for the PPS publisher node

### 2. Integration test (services started via `start_services.sh`)

`docker/tests/test_integration.py` exercises the full pipeline using mock hardware:

```
ros2 launch frc_payload_launcher test_launch.py
  fake_image_pub (cam0, 5120×800, gradient + PPS, 3 fps)
  fake_image_pub (cam1, 5120×800, gradient, no PPS, 3 fps)
  fast_stamp_split × 2
    → /cam0/R8_MONO_img{0..3}   (1280×800 slices)
    → /cam1/BGGR_img{0..3}      (1280×800 slices)
```

**Note on frame rate:** `test_launch.py` runs at 3 fps, matching the hardware PWM trigger
rate. 5120×800 mono16/bayer16 @ 3 Hz = ~24 MB/s per camera — within Docker loopback
capacity with SHM transport.

Services are managed by the scripts in `src/frc_payload_launcher/launch_files/`:
- `start_services.sh` — starts systemd services (if systemd is active) then launches
  `ros2 launch frc_payload_launcher $LAUNCH_FILE` (`fast_launch.py` by default;
  `test_launch.py` when `LAUNCH_FILE=test_launch.py` is set by `run_tests.sh`)
- `stop_services.sh` — kills the ROS2 launch process and stops systemd services

The test asserts:
- All 8 slice topics receive ≥ 3 messages
- Each slice is 1280×800 (5120/4)
- PPS timestamp applied (stamp > 0)
- Adjacent slices within each camera contain different pixel data

### 3. Per-package lint tests

`ament_flake8`, `ament_pep257`, and `ament_copyright` are run from inside each package
directory so they only scan that package's source files.

## On real hardware (Raspberry Pi)

```bash
# Build without skipping camera_ros (requires libcamera >= 0.1)
colcon build --symlink-install

# Install service files
bash src/frc_payload_launcher/launch_files/install_services.sh

# Start the full pipeline (5120×800, real cameras)
bash src/frc_payload_launcher/launch_files/start_services.sh

# Or for hardware integration testing
LAUNCH_FILE=fast_launch.py bash src/frc_payload_launcher/launch_files/start_services.sh
```

## CI

`.github/workflows/test.yml` runs on every push and pull request:

1. **Build** — `docker build -f docker/Dockerfile -t payload_camera_ws:iron .`
2. **Run tests** — `docker run --rm payload_camera_ws:iron bash /payload_camera_ws/docker/run_tests.sh`

## Notes

- `camera_ros` and `camera_ros_bringup` are skipped in Docker — they need
  `libcamera >= 0.1` which is only available on Raspberry Pi OS.
- The `gradient` pattern produces distinct hues per 128-px zone so the pixel-content
  check can verify that slicing actually happened.
