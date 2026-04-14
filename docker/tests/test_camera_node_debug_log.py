#!/usr/bin/env python3
"""
docker/tests/test_camera_node_debug_log.py

Integration test: verifies that FakeImagePublisher (which mirrors CameraNode's
publish loop) actually emits per-frame DEBUG log messages containing frame
number, received timestamp, and publish timestamp.

CameraNode.cpp is not built in Docker (requires Pi-native libcamera), so
FakeImagePublisher carries the same debug log and is tested here instead.

No external services required — creates nodes in-process.

Run (with workspace sourced):
    pytest docker/tests/test_camera_node_debug_log.py -v
"""

import argparse
import re
import sys
import time
from pathlib import Path

import pytest
import rclpy
import rclpy.logging
from rcl_interfaces.msg import Log

WS_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(WS_ROOT))
from fake_image_pub import FakeImagePublisher  # noqa: E402

# ── test parameters ────────────────────────────────────────────────────────────
# Small frames + fast rate → minimal overhead, quick collection.
TEST_ARGS = argparse.Namespace(
    topic="/test_pub_log/image_raw",
    pps="/test_pub_log/pps",
    rate=10.0,
    pps_rate=1.0,
    width=64,
    height=64,
    encoding="rgb8",
    pattern="solid",
    color="128,128,128",
    block=64,
    file=None,
    no_pps=True,
    frame_id="camera",
)

# Matches: "frame 3  recv 1713000000000000000 ns  pub 1713000000001000000 ns"
LOG_PATTERN = re.compile(r"frame \d+\s+recv \d+ ns\s+pub \d+ ns")

COLLECT_SECS = 5.0
MIN_MATCHING = 3


@pytest.fixture(scope="module", autouse=True)
def ros_init():
    rclpy.init()
    yield
    rclpy.shutdown()


def test_debug_log_emitted():
    """
    Publisher must emit per-frame DEBUG logs with frame number,
    received timestamp, and publish timestamp.
    """
    captured: list[str] = []

    pub_node = FakeImagePublisher(TEST_ARGS)
    rclpy.logging.set_logger_level(
        pub_node.get_name(), rclpy.logging.LoggingSeverity.DEBUG
    )

    collector = rclpy.create_node("debug_log_collector")

    def rosout_cb(msg: Log):
        if msg.name == pub_node.get_name():
            captured.append(msg.msg)

    collector.create_subscription(Log, "/rosout", rosout_cb, 100)

    executor = rclpy.executors.MultiThreadedExecutor()
    executor.add_node(pub_node)
    executor.add_node(collector)

    deadline = time.monotonic() + COLLECT_SECS
    while time.monotonic() < deadline and rclpy.ok() and len(captured) < MIN_MATCHING:
        executor.spin_once(timeout_sec=0.05)

    pub_node.destroy_node()
    collector.destroy_node()

    matching = [m for m in captured if LOG_PATTERN.search(m)]
    assert len(matching) >= MIN_MATCHING, (
        f"Expected >= {MIN_MATCHING} debug log messages matching {LOG_PATTERN.pattern!r}, "
        f"got {len(matching)}. All captured from this node: {captured[:10]}"
    )

    first = matching[0]
    assert re.search(r"frame \d+", first), f"Missing frame number in: {first!r}"
    assert re.search(r"recv \d+ ns", first), f"Missing recv timestamp in: {first!r}"
    assert re.search(r"pub \d+ ns", first), f"Missing pub timestamp in: {first!r}"
