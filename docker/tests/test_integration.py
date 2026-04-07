#!/usr/bin/env python3
"""
docker/test_integration.py

Integration test: fake_image_pub → pps_stamp_and_split → verify 4 slices

Launches both nodes as subprocesses, spins a verifier in-process, and asserts
that all 4 output slices arrive with the correct dimensions and timestamps.

Run (with workspace sourced):
    pytest docker/test_integration.py -v
"""

import os
import pty
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import List

import pytest
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data, QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image
from builtin_interfaces.msg import Time

# ── paths ──────────────────────────────────────────────────────────────────────
REPO_ROOT       = Path(__file__).resolve().parent.parent.parent
FAKE_PUB        = str(REPO_ROOT / "fake_image_pub.py")
PPS_STAMP_SPLIT = str(
    REPO_ROOT / "src/stamp_and_split_cam1/stamp_and_split_cam1/pps_stamp_and_split.py"
)

# ── geometry ───────────────────────────────────────────────────────────────────
FULL_W   = 5120
FULL_H   = 800
SLICE_W  = FULL_W // 4   # 1280
ENCODING = "rgb8"
BPP      = 3

# ── timing ─────────────────────────────────────────────────────────────────────
DISCOVERY_SECS = 3.0   # wait for DDS discovery before collecting
COLLECT_SECS   = 8.0   # collection window
MIN_MSGS       = 3     # minimum messages per slice topic to pass


# ── subprocess helpers ─────────────────────────────────────────────────────────

def _stream_fd(master_fd: int, label: str):
    """Background thread: read from a PTY master fd and print with a label prefix."""
    try:
        with os.fdopen(master_fd, "rb") as f:
            for line in f:
                sys.stdout.write(f"[{label}] {line.decode(errors='replace').rstrip()}\n")
                sys.stdout.flush()
    except OSError:
        pass  # PTY closed when subprocess exits


def start_proc(cmd: List[str], label: str) -> subprocess.Popen:
    """Launch cmd in a PTY so the subprocess sees a real TTY and keeps color output."""
    print(f"\n[test] start {label}: {' '.join(cmd)}")
    master_fd, slave_fd = pty.openpty()
    proc = subprocess.Popen(
        cmd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
        preexec_fn=os.setsid,
    )
    os.close(slave_fd)
    threading.Thread(target=_stream_fd, args=(master_fd, label), daemon=True).start()
    return proc


def stop_proc(proc: subprocess.Popen, label: str):
    if proc.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        proc.wait(timeout=3)
    except Exception:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            pass


def spin_for(node: Node, duration: float):
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


@pytest.fixture()
def pipeline():
    """Start fake_image_pub (with PPS) and pps_stamp_and_split together."""
    pub = start_proc([
        sys.executable, FAKE_PUB,
        "--rate",     "10",
        "--pps-rate", "2",
        "--pattern",  "gradient",
        "--width",    str(FULL_W),
        "--height",   str(FULL_H),
    ], "fake_image_pub")

    dut = start_proc([
        sys.executable, PPS_STAMP_SPLIT,
    ], "pps_stamp_and_split")

    yield pub, dut

    stop_proc(pub, "fake_image_pub")
    stop_proc(dut, "pps_stamp_and_split")


# ── integration test ───────────────────────────────────────────────────────────

SLICE_TOPICS = ["img0", "img1", "img2", "img3"]


def test_pipeline(pipeline):
    """
    Full pipeline test:
      fake_image_pub (5120×800 gradient + PPS)
        → pps_stamp_and_split
          → img0 / img1 / img2 / img3

    Asserts:
      - All 4 slice topics deliver at least MIN_MSGS messages
      - Each slice is 1280×800 with correct step and data length
      - Encoding passes through unchanged (rgb8)
      - PPS timestamp is applied (stamp.sec > 0)
      - Adjacent slices contain different pixel data (split actually happened)
    """
    import numpy as np

    # Collect messages from all 4 slice topics
    bags: dict[str, list] = {t: [] for t in SLICE_TOPICS}
    lock = threading.Lock()

    node = rclpy.create_node("integration_test_collector")
    for topic in SLICE_TOPICS:
        def cb(msg, t=topic):
            with lock:
                bags[t].append(msg)
        node.create_subscription(Image, topic, cb, qos_profile_sensor_data)

    time.sleep(DISCOVERY_SECS)
    spin_for(node, COLLECT_SECS)
    node.destroy_node()

    # ── 1. all 4 topics received messages ─────────────────────────────────────
    for topic in SLICE_TOPICS:
        count = len(bags[topic])
        assert count >= MIN_MSGS, (
            f"{topic}: got {count} messages, need at least {MIN_MSGS}. "
            "PPS may not have arrived in time or the split node didn't start."
        )

    # ── 2. correct dimensions and data length ─────────────────────────────────
    for topic in SLICE_TOPICS:
        for msg in bags[topic]:
            assert msg.width  == SLICE_W,           f"{topic}: width {msg.width} != {SLICE_W}"
            assert msg.height == FULL_H,            f"{topic}: height {msg.height} != {FULL_H}"
            assert msg.step   == SLICE_W * BPP,     f"{topic}: step {msg.step} != {SLICE_W * BPP}"
            assert len(msg.data) == SLICE_W * FULL_H * BPP, f"{topic}: wrong data length"

    # ── 3. encoding preserved ─────────────────────────────────────────────────
    for topic in SLICE_TOPICS:
        for msg in bags[topic]:
            assert msg.encoding == ENCODING, f"{topic}: encoding {msg.encoding!r} != {ENCODING!r}"

    # ── 4. PPS timestamp was applied ──────────────────────────────────────────
    for topic in SLICE_TOPICS:
        for msg in bags[topic]:
            ns = msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec
            assert ns > 0, f"{topic}: timestamp is zero — PPS stamp not applied"

    # ── 5. adjacent slices have different content (split really happened) ──────
    first_frames = []
    for topic in SLICE_TOPICS:
        msg = bags[topic][0]
        arr = np.frombuffer(bytes(msg.data), dtype=np.uint8).reshape(FULL_H, SLICE_W, BPP)
        first_frames.append(arr)

    for i in range(len(first_frames) - 1):
        assert not np.array_equal(first_frames[i], first_frames[i + 1]), (
            f"Slices {i} and {i+1} are byte-identical — split may not be working"
        )
