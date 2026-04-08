#!/usr/bin/env python3
"""
docker/tests/test_integration.py

Full integration test: verifies that ros2 launch frc_payload_launcher fast_launch.py
publishes correctly sliced and PPS-stamped images on all 8 output topics.

Services must be started before this test runs — handled automatically by
run_tests.sh via src/frc_payload_launcher/launch_files/start_services.sh.

Run (with workspace sourced and services already running):
    pytest docker/tests/test_integration.py -v
"""

import threading
import time

import numpy as np
import pytest
import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image

# ── geometry ───────────────────────────────────────────────────────────────────
FULL_W  = 5120
FULL_H  = 800
SLICE_W = FULL_W // 4   # 1280

# ── timing ─────────────────────────────────────────────────────────────────────
# test_launch.py runs at 3 Hz (vs 10 Hz production) to keep DDS loopback
# bandwidth tractable in Docker (~37 MB/s per camera instead of ~120 MB/s).
DISCOVERY_SECS = 5.0    # wait for DDS discovery after services start
COLLECT_SECS   = 30.0   # collection window (3 Hz × 30 s >> MIN_MSGS)
MIN_MSGS       = 3      # minimum messages per slice topic to pass

# ── topics published by fast_launch.py ────────────────────────────────────────
CAM0_TOPICS = [
    "/cam0/R8_MONO_img0",
    "/cam0/R8_MONO_img1",
    "/cam0/R8_MONO_img2",
    "/cam0/R8_MONO_img3",
]
CAM1_TOPICS = [
    "/cam1/BGGR_img0",
    "/cam1/BGGR_img1",
    "/cam1/BGGR_img2",
    "/cam1/BGGR_img3",
]
ALL_TOPICS = CAM0_TOPICS + CAM1_TOPICS


def spin_for(node, duration: float):
    executor = rclpy.executors.SingleThreadedExecutor()
    executor.add_node(node)
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline and rclpy.ok():
        executor.spin_once(timeout_sec=0.05)
    executor.remove_node(node)


# ── fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def ros_init():
    rclpy.init()
    yield
    rclpy.shutdown()


# ── integration test ───────────────────────────────────────────────────────────

def test_pipeline():
    """
    Full pipeline integration test:
      ros2 launch frc_payload_launcher fast_launch.py
        → pps_time_pub + cam0 + cam1 + fast_stamp_split × 2
          → /cam0/R8_MONO_img{0..3}  /cam1/BGGR_img{0..3}

    Asserts:
      - All 8 slice topics deliver at least MIN_MSGS messages
      - Each slice is 1280×800
      - PPS timestamp is applied (stamp > 0)
      - Adjacent slices within each camera contain different pixel data
    """
    bags: dict[str, list] = {t: [] for t in ALL_TOPICS}
    lock = threading.Lock()

    node = rclpy.create_node("integration_test_collector")
    for topic in ALL_TOPICS:
        def cb(msg, t=topic):
            with lock:
                bags[t].append(msg)
        node.create_subscription(Image, topic, cb, qos_profile_sensor_data)

    time.sleep(DISCOVERY_SECS)
    spin_for(node, COLLECT_SECS)
    node.destroy_node()

    # ── 1. all 8 topics received messages ─────────────────────────────────────
    for topic in ALL_TOPICS:
        count = len(bags[topic])
        assert count >= MIN_MSGS, (
            f"{topic}: got {count} messages, need at least {MIN_MSGS}. "
            "Check that cameras are connected and fast_launch.py started cleanly."
        )

    # ── 2. correct dimensions ─────────────────────────────────────────────────
    for topic in ALL_TOPICS:
        for msg in bags[topic]:
            assert msg.width  == SLICE_W, f"{topic}: width {msg.width} != {SLICE_W}"
            assert msg.height == FULL_H,  f"{topic}: height {msg.height} != {FULL_H}"

    # ── 3. PPS timestamp was applied ──────────────────────────────────────────
    for topic in ALL_TOPICS:
        for msg in bags[topic]:
            ns = msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec
            assert ns > 0, f"{topic}: timestamp is zero — PPS stamp not applied"

    # ── 4. adjacent slices differ within each camera (split actually happened) ─
    for cam_topics in (CAM0_TOPICS, CAM1_TOPICS):
        first_frames = []
        for topic in cam_topics:
            arr = np.frombuffer(bytes(bags[topic][0].data), dtype=np.uint8)
            first_frames.append(arr)
        for i in range(len(first_frames) - 1):
            assert not np.array_equal(first_frames[i], first_frames[i + 1]), (
                f"Slices {i} and {i+1} of {cam_topics[0][:5]} are byte-identical — "
                "split may not be working"
            )
