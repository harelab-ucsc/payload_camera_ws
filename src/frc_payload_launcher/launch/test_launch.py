#!/usr/bin/env python3
"""Mock launch for integration testing using fake cameras instead of hardware."""
import os
import sys
from pathlib import Path

from launch import LaunchDescription
from launch.actions import ExecuteProcess, RegisterEventHandler, TimerAction
from launch.event_handlers import OnProcessStart
from launch_ros.actions import Node

# Locate fake_image_pub.py / fake_sync_inputs.py at the workspace root.
# COLCON_PREFIX_PATH is set to <ws>/install when the workspace is sourced.
_prefix = os.environ.get("COLCON_PREFIX_PATH", "").split(":")[0]
_ws_root = str(Path(_prefix).parent) if _prefix else "/payload_camera_ws"
FAKE_PUB = str(Path(_ws_root) / "fake_image_pub.py")
FAKE_SYNC_INPUTS = str(Path(_ws_root) / "fake_sync_inputs.py")

# Test fixtures for sync_node startup (absolute paths bypass the ~/... join in SyncNode)
_fixtures = str(Path(_ws_root) / "docker" / "tests" / "fixtures")
TEST_SENSORS_YAML = str(Path(_fixtures) / "test_sensors.yaml")
TEST_CLICKS_CSV = str(Path(_fixtures) / "test_clicks.csv")
TEST_OUTPUT_DIR = "/tmp/test_sync_output"


# Production resolution and frame rate used for Docker CI testing.
# Hardware runs at 3 Hz (PWM-triggered); test_launch.py matches that rate.
# 5120×800 mono16/bayer16 @ 3 Hz = ~24 MB/s per camera (one publisher hop only).
TEST_WIDTH = 5120
TEST_HEIGHT = 800
TEST_RATE = 3
TEST_PPS_RATE = 2


def generate_launch_description():

    # ------------------------------------------------------------------
    # Fake cam0 — mono16 to match production R16, also publishes /pps/time
    # ------------------------------------------------------------------
    fake_cam0 = ExecuteProcess(
        cmd=[
            sys.executable, FAKE_PUB,
            "--topic",    "/cam0/camera_node/image_raw",
            "--pps",      "/pps/time",
            "--rate",     str(TEST_RATE),
            "--pps-rate", str(TEST_PPS_RATE),
            "--pattern",  "gradient",
            "--width",    str(TEST_WIDTH),
            "--height",   str(TEST_HEIGHT),
            "--encoding", "mono16",
        ],
        output="screen",
        name="fake_cam0",
    )

    # ------------------------------------------------------------------
    # Fake cam1 — bayer_bggr16 to match production SBGGR16
    # ------------------------------------------------------------------
    fake_cam1 = ExecuteProcess(
        cmd=[
            sys.executable, FAKE_PUB,
            "--topic",    "/cam1/camera_node/image_raw",
            "--no-pps",
            "--rate",     str(TEST_RATE),
            "--pattern",  "gradient",
            "--width",    str(TEST_WIDTH),
            "--height",   str(TEST_HEIGHT),
            "--encoding", "bayer_bggr16",
        ],
        output="screen",
        name="fake_cam1",
    )

    # ------------------------------------------------------------------
    # Fake INS / radalt / AS7265x — required for SyncNode.all_caught()
    # ------------------------------------------------------------------
    fake_sync_inputs = ExecuteProcess(
        cmd=[sys.executable, FAKE_SYNC_INPUTS, "--rate", "10"],
        output="screen",
        name="fake_sync_inputs",
    )

    # ------------------------------------------------------------------
    # sync_node — stream_processor PPS-synced save node
    # Subscribes directly to raw camera topics and does split + spectral
    # correction + debayer in-process via the C++ extension; no
    # intermediate image topics on DDS.
    # ------------------------------------------------------------------
    sync_node = Node(
        package="stream_processor",
        executable="sync_node",
        name="sync_node",
        output="screen",
        parameters=[{
            "db_name":      "test_flight_data",
            "img_format":   ".tiff",
            "dir_name":     TEST_OUTPUT_DIR,
            "sensors_yaml": TEST_SENSORS_YAML,
            "clicks_csv":   TEST_CLICKS_CSV,
        }],
    )

    # sync_node starts 4 s after fake_cam0 to give DDS discovery time
    delayed_sync = RegisterEventHandler(
        OnProcessStart(
            target_action=fake_cam0,
            on_start=[
                TimerAction(
                    period=4.0,
                    actions=[sync_node],
                )
            ],
        )
    )

    return LaunchDescription([
        fake_cam0,
        fake_cam1,
        fake_sync_inputs,
        delayed_sync,
    ])
