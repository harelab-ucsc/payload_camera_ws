#!/usr/bin/env python3
"""
benchmark_stamp_split.py

Launches both nodes, publishes synthetic 4-colour images to each, and
measures round-trip latency (publish → img0 received).

Usage:
    python3 benchmark_stamp_split.py [--frames N] [--width W] [--height H]

Requirements:
    - workspace sourced  (both packages built)
    - no other nodes publishing on /bench/py/* or /bench/cpp/*
"""

import argparse
import subprocess
import sys
import time
import threading
import numpy as np

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, qos_profile_sensor_data
from sensor_msgs.msg import Image
from builtin_interfaces.msg import Time

# ── colours for the 4 strips (BGR) ──────────────────────────────────────────
COLOURS_BGR = [
    (0,   0,   255),   # RED
    (0,   255,   0),   # GREEN
    (255,  0,    0),   # BLUE
    (0,  255,  255),   # YELLOW
]

def make_test_image(width=5120, height=800) -> np.ndarray:
    img = np.zeros((height, width, 3), dtype=np.uint8)
    sw = width // 4
    for i, bgr in enumerate(COLOURS_BGR):
        img[:, i*sw:(i+1)*sw] = bgr
    return img

def numpy_to_ros_image(arr: np.ndarray) -> Image:
    h, w = arr.shape[:2]
    msg = Image()
    msg.height = h
    msg.width  = w
    msg.encoding    = "bgr8"
    msg.is_bigendian = False
    msg.step   = w * 3
    msg.data   = arr.tobytes()
    return msg

# ── benchmark node ───────────────────────────────────────────────────────────

class BenchNode(Node):
    def __init__(self, img_msg: Image, n_frames: int):
        super().__init__("bench_stamp_split")
        self.img_msg  = img_msg
        self.n_frames = n_frames

        img_qos = qos_profile_sensor_data

        # publishers → each node's input topic
        self.py_pub  = self.create_publisher(Image, "/bench/py/image_raw",  img_qos)
        self.cpp_pub = self.create_publisher(Image, "/bench/cpp/image_raw", img_qos)

        # subscribers ← each node's first output slice
        self.create_subscription(Image, "/bench/py/img0",  self._py_cb,  img_qos)
        self.create_subscription(Image, "/bench/cpp/img0", self._cpp_cb, img_qos)

        self._py_times:  list[float] = []
        self._cpp_times: list[float] = []
        self._py_send:  float | None = None
        self._cpp_send: float | None = None
        self._lock = threading.Lock()

        self._py_done  = threading.Event()
        self._cpp_done = threading.Event()

    # ── callbacks ─────────────────────────────────────────────────────────

    def _py_cb(self, _msg):
        with self._lock:
            if self._py_send is not None:
                self._py_times.append(time.perf_counter() - self._py_send)
                self._py_send = None
            if len(self._py_times) >= self.n_frames:
                self._py_done.set()

    def _cpp_cb(self, _msg):
        with self._lock:
            if self._cpp_send is not None:
                self._cpp_times.append(time.perf_counter() - self._cpp_send)
                self._cpp_send = None
            if len(self._cpp_times) >= self.n_frames:
                self._cpp_done.set()

    # ── run ───────────────────────────────────────────────────────────────

    def run_bench(self, timeout_per_frame=5.0):
        # Give nodes a moment to start up before the first publish
        time.sleep(0.5)

        def send_frames(pub, send_attr, done_event, label):
            sent = 0
            while sent < self.n_frames:
                with self._lock:
                    if getattr(self, send_attr) is not None:
                        # still waiting for last reply — spin a bit
                        pass
                    else:
                        setattr(self, send_attr, time.perf_counter())
                        pub.publish(self.img_msg)
                        sent += 1
                time.sleep(0.01)   # ~100 Hz max send rate

        py_thread  = threading.Thread(target=send_frames,
                                      args=(self.py_pub,  "_py_send",  self._py_done,  "py"))
        cpp_thread = threading.Thread(target=send_frames,
                                      args=(self.cpp_pub, "_cpp_send", self._cpp_done, "cpp"))

        py_thread.start()
        cpp_thread.start()
        py_thread.join()
        cpp_thread.join()

        # Wait for all replies (with timeout)
        deadline = self.n_frames * timeout_per_frame
        self._py_done.wait(timeout=deadline)
        self._cpp_done.wait(timeout=deadline)

    def results(self):
        return self._py_times, self._cpp_times


# ── helpers ──────────────────────────────────────────────────────────────────

def launch_node(cmd: list[str]) -> subprocess.Popen:
    return subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

def stats(times: list[float], label: str):
    if not times:
        print(f"  {label}: NO DATA received")
        return
    a = np.array(times) * 1000  # → ms
    print(f"  {label}")
    print(f"    frames    : {len(a)}")
    print(f"    mean      : {np.mean(a):.2f} ms")
    print(f"    median    : {np.median(a):.2f} ms")
    print(f"    min       : {np.min(a):.2f} ms")
    print(f"    max       : {np.max(a):.2f} ms")
    print(f"    std       : {np.std(a):.2f} ms")
    print(f"    throughput: {1000/np.mean(a):.1f} fps")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--frames", "-n", type=int, default=100)
    parser.add_argument("--width",        type=int, default=5120)
    parser.add_argument("--height",       type=int, default=800)
    args = parser.parse_args()

    W, H, N = args.width, args.height, args.frames

    print("=" * 70)
    print("  Benchmark: fast_stamp_split (C++)  vs  stamp_and_split_cam1 (Python)")
    print("=" * 70)
    print(f"  image : {W}×{H} bgr8  ({W*H*3/1024:.0f} KB)")
    print(f"  frames: {N}")
    print()

    # Build the synthetic image
    img_arr = make_test_image(W, H)
    img_msg = numpy_to_ros_image(img_arr)
    print("  4-colour test image strips:")
    sw = W // 4
    names = ["RED", "GREEN", "BLUE", "YELLOW"]
    for i, name in enumerate(names):
        cy, cx = H//2, i*sw + sw//2
        print(f"    slice {i}: x=[{i*sw}–{(i+1)*sw-1}]  {name}  BGR={tuple(int(v) for v in img_arr[cy, cx])}")
    print()

    # Common ros-args for both nodes
    common = [
        "-p", "require_pps:=false",
        "-p", "full_width:=" + str(W),
        "-p", "full_height:=" + str(H),
    ]

    py_cmd = [
        "ros2", "run", "stamp_and_split_cam1", "pps_stamp_and_split",
        "--ros-args",
        "-p", "in_topic:=/bench/py/image_raw",
        "-p", "out_0:=/bench/py/img0",
        "-p", "out_1:=/bench/py/img1",
        "-p", "out_2:=/bench/py/img2",
        "-p", "out_3:=/bench/py/img3",
        *common,
    ]

    cpp_cmd = [
        "ros2", "run", "fast_stamp_split", "fast_stamp_split_node",
        "--ros-args",
        "-p", "in_topic:=/bench/cpp/image_raw",
        "-p", "out_0:=/bench/cpp/img0",
        "-p", "out_1:=/bench/cpp/img1",
        "-p", "out_2:=/bench/cpp/img2",
        "-p", "out_3:=/bench/cpp/img3",
        *common,
    ]

    print("  Launching nodes...")
    py_proc  = launch_node(py_cmd)
    cpp_proc = launch_node(cpp_cmd)

    # Give them time to initialise
    time.sleep(3.0)
    print("  Nodes ready. Running benchmark...\n")

    rclpy.init()
    node = BenchNode(img_msg, N)

    # Spin the node in a background thread so callbacks fire
    executor = rclpy.executors.MultiThreadedExecutor()
    executor.add_node(node)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()

    try:
        node.run_bench()
    finally:
        executor.shutdown()
        rclpy.shutdown()

    py_times, cpp_times = node.results()

    print("--- Results (round-trip: publish → img0 received) ---\n")
    stats(py_times,  "stamp_and_split_cam1  (Python)")
    print()
    stats(cpp_times, "fast_stamp_split      (C++)")

    if py_times and cpp_times:
        speedup = np.mean(py_times) / np.mean(cpp_times)
        print()
        if speedup >= 1.0:
            print(f"  → C++ is {speedup:.1f}× faster than Python")
        else:
            print(f"  → Python is {1/speedup:.1f}× faster than C++ (unexpected)")

    print()

    py_proc.terminate()
    cpp_proc.terminate()
    py_proc.wait()
    cpp_proc.wait()


if __name__ == "__main__":
    main()
