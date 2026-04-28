#!/usr/bin/env python3
"""
docker/tests/test_integration.py

End-to-end pipeline test: verifies that ros2 launch frc_payload_launcher
test_launch.py wires up fake cameras + fake AS7265x + sync_node, and that
sync_node writes the expected per-PPS-cycle output files to disk.

The standalone fast_stamp_split node is gone; split + spectral correction +
debayer all happen in-process inside sync_node via the C++ pybind extension.
There are no longer intermediate /cam{0,1}/{R8_MONO,BGGR}_img{0..3} topics.

Services must be started before this test runs — handled automatically by
run_tests.sh via src/frc_payload_launcher/launch_files/start_services.sh.

Run (with workspace sourced and services already running):
    pytest docker/tests/test_integration.py -v
"""

import glob
import os
import re
import time

import numpy as np
import pytest
import rclpy

# ── geometry ───────────────────────────────────────────────────────────────────
FULL_W = 5120
FULL_H = 800
SLICE_W = FULL_W // 4   # 1280

# ── timing ─────────────────────────────────────────────────────────────────────
DISCOVERY_SECS = 5.0
COLLECT_SECS   = 30.0
MIN_CYCLES     = 2
FILES_PER_CYCLE = 8     # 4 cam0 + 4 cam1 per PPS cycle

# ── output ─────────────────────────────────────────────────────────────────────
OUTPUT_DIR = "/tmp/test_sync_output"
CAM_RE = re.compile(r"^cam(?P<cam>[01])_(?P<idx>[0-3])_(?P<stamp>\d+\.\d+)\.(?P<ext>tiff?|png|jpg)$")


# ── fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def ros_init():
    rclpy.init()
    yield
    rclpy.shutdown()


def _spin_for(node, duration: float):
    executor = rclpy.executors.SingleThreadedExecutor()
    executor.add_node(node)
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline and rclpy.ok():
        executor.spin_once(timeout_sec=0.05)
    executor.remove_node(node)


def _list_outputs():
    """Group output files by PPS timestamp."""
    if not os.path.isdir(OUTPUT_DIR):
        return {}
    cycles: dict = {}
    for path in glob.glob(os.path.join(OUTPUT_DIR, "cam*")):
        m = CAM_RE.match(os.path.basename(path))
        if not m:
            continue
        cycles.setdefault(m["stamp"], []).append(path)
    return cycles


def _wait_for_cycles(min_cycles: int, files_per_cycle: int, timeout: float):
    """Poll OUTPUT_DIR until min_cycles complete (have files_per_cycle each)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        cycles = _list_outputs()
        complete = [s for s, paths in cycles.items() if len(paths) >= files_per_cycle]
        if len(complete) >= min_cycles:
            return cycles, complete
        time.sleep(0.5)
    return _list_outputs(), [s for s, paths in _list_outputs().items()
                              if len(paths) >= files_per_cycle]


# ── tests ──────────────────────────────────────────────────────────────────────

def test_pipeline_writes_per_cycle_files():
    """
    sync_node should produce 8 image files (cam{0,1}_{0..3}_<stamp>.<ext>)
    per PPS cycle once the fakes have been pumping for a few seconds.
    """
    cycles, complete = _wait_for_cycles(
        MIN_CYCLES, FILES_PER_CYCLE, DISCOVERY_SECS + COLLECT_SECS
    )
    assert len(complete) >= MIN_CYCLES, (
        f"Got {len(complete)} complete cycles (need {MIN_CYCLES}). "
        f"All cycles seen: { {k: len(v) for k, v in cycles.items()} }. "
        f"Check that fake_cam0/cam1 + fake_sync_inputs + sync_node all started "
        f"and that sync_node imported stream_processor.spectral_correct."
    )

    # First completed cycle gets a deeper inspection.
    sample_paths = sorted(cycles[complete[0]])
    cam0_files = [p for p in sample_paths if os.path.basename(p).startswith("cam0_")]
    cam1_files = [p for p in sample_paths if os.path.basename(p).startswith("cam1_")]
    assert len(cam0_files) == 4, f"expected 4 cam0 files, got {cam0_files}"
    assert len(cam1_files) == 4, f"expected 4 cam1 files, got {cam1_files}"

    # All files non-trivially sized — rules out 0-byte / failed-write artifacts.
    for p in sample_paths:
        size = os.path.getsize(p)
        assert size > 1024, f"{p}: only {size} bytes — write likely failed"


def test_pipeline_image_dimensions():
    """
    Verify the saved images have the expected per-slice geometry.
    cam0: (H, W/4) reflectance (float32 in TIFF, uint16 in PNG).
    cam1: (H, W/4, 3) RGB.
    """
    import cv2

    cycles = _list_outputs()
    complete = [s for s, paths in cycles.items() if len(paths) >= FILES_PER_CYCLE]
    if not complete:
        pytest.skip("no complete cycles produced yet — see test_pipeline_writes_per_cycle_files")

    sample = sorted(cycles[complete[0]])
    cam0_path = next(p for p in sample if os.path.basename(p).startswith("cam0_0_"))
    cam1_path = next(p for p in sample if os.path.basename(p).startswith("cam1_0_"))

    cam0_img = cv2.imread(cam0_path, cv2.IMREAD_UNCHANGED)
    assert cam0_img is not None, f"cv2 could not read {cam0_path}"
    assert cam0_img.shape == (FULL_H, SLICE_W), (
        f"cam0 shape {cam0_img.shape} != {(FULL_H, SLICE_W)}"
    )
    # TIFF preserves float32 reflectance; PNG path scales to uint16.
    assert cam0_img.dtype in (np.float32, np.uint16), f"cam0 dtype {cam0_img.dtype}"

    cam1_img = cv2.imread(cam1_path, cv2.IMREAD_UNCHANGED)
    assert cam1_img is not None, f"cv2 could not read {cam1_path}"
    assert cam1_img.shape == (FULL_H, SLICE_W, 3), (
        f"cam1 shape {cam1_img.shape} != {(FULL_H, SLICE_W, 3)}"
    )


def test_sync_node_running():
    """sync_node should be in the ROS 2 graph after services started."""
    node = rclpy.create_node("sync_check_collector")
    try:
        _spin_for(node, DISCOVERY_SECS)
        node_pairs = node.get_node_names_and_namespaces()
        names = [n for n, _ in node_pairs]
    finally:
        node.destroy_node()

    assert "sync_node" in names, (
        f"sync_node not found in ROS2 node list: {names}. "
        "Check that stream_processor built correctly and test_launch.py started it."
    )
