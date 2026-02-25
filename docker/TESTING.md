# Docker Integration Testing

Builds the workspace in a ROS2 Iron container and runs the pipeline test automatically.

## Build & test

```bash
docker build -f docker/Dockerfile -t payload_camera_ws:iron .
```

The build runs `test_integration.py` as the final step — if it fails, the build fails.

## What the test does

Launches `fake_image_pub.py` (synthetic 5120×800 images + PPS timestamps) and `pps_stamp_and_split` as subprocesses, then verifies the output:

- All 4 slice topics (`img0`–`img3`) receive messages
- Each slice is 1280×800 with correct encoding and step
- PPS timestamp was applied (non-zero stamp)
- Adjacent slices contain different pixel data (split actually happened)

## Run the test manually

```bash
# inside the container, or with the workspace sourced
source install/setup.bash
python3 -m pytest docker/test_integration.py -v
```

## Notes

- `camera_ros` and `camera_ros_bringup` are skipped during build — they need `libcamera >= 0.1` which is only available on Raspberry Pi OS. Build without `--packages-skip` on the actual Pi.
- The test uses the `gradient` pattern which produces distinct colours per camera zone, letting the pixel-content check verify the split is real.
