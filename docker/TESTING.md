# Docker Integration Testing

Builds the workspace in a ROS2 Iron container and runs the pipeline test as a separate step.

## Build

```bash
docker build -f docker/Dockerfile -t payload_camera_ws:iron .
```

Tests are **not** run during the build by default.

To run tests as part of the build (e.g. for a quick local check):

```bash
docker build -f docker/Dockerfile --build-arg RUN_TESTS=true -t payload_camera_ws:iron .
```

## Run the test

```bash
# Against the already-built image
docker run --rm payload_camera_ws:iron bash -c \
  ". /opt/ros/iron/setup.sh && \
   . /payload_camera_ws/install/setup.sh && \
   python3 -m pytest /payload_camera_ws/docker/test_integration.py -v"

# Or inside a running container / with the workspace sourced locally
source install/setup.bash
python3 -m pytest docker/test_integration.py -v
```

## CI

The GitHub Actions workflow (`.github/workflows/test.yml`) runs two steps on every push and pull request:

1. **Build** — builds the Docker image
2. **Run integration tests** — runs pytest in the built container as a separate step

## What the test does

Launches `fake_image_pub.py` (synthetic 5120×800 images + PPS timestamps) and `pps_stamp_and_split` as subprocesses, then verifies the output:

- All 4 slice topics (`img0`–`img3`) receive messages
- Each slice is 1280×800 with correct encoding and step
- PPS timestamp was applied (non-zero stamp)
- Adjacent slices contain different pixel data (split actually happened)

## Notes

- `camera_ros` and `camera_ros_bringup` are skipped during build — they need `libcamera >= 0.1` which is only available on Raspberry Pi OS. Build without `--packages-skip` on the actual Pi.
- The test uses the `gradient` pattern which produces distinct colours per camera zone, letting the pixel-content check verify the split is real.
