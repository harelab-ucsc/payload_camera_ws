# Slugriculture Camera Payload - ROS2 Interface

ROS2 interface that integrates multispectral and orthomosaic, RGB camera systems.

## Installation

## Testing

Tests live in `docker/tests/`. Add any new test file there using pytest naming conventions (`test_*.py` or `*_test.py`) and it will be picked up automatically.

**Run all tests inside Docker:**
```bash
docker build -f docker/Dockerfile -t payload_camera_ws:iron .
docker run --rm payload_camera_ws:iron bash /payload_camera_ws/docker/run_tests.sh
```

The `docker/run_tests.sh` script sources the ROS2 Iron and workspace environments, discovers all test files in `docker/tests/`, and runs them with pytest.

CI (GitHub Actions) builds the image and calls the same script on every push and pull request.

## Metadata

### Authors

Team Slugriculture
HARE Lab
jLab

### Date

20 Jan 2026

### Version

0.0.1
