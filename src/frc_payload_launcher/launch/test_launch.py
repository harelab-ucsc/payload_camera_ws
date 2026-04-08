#!/usr/bin/env python3
"""Mock launch for integration testing using fake cameras instead of hardware."""
import os
import sys
from pathlib import Path

from launch import LaunchDescription
from launch.actions import ExecuteProcess, RegisterEventHandler, TimerAction
from launch.event_handlers import OnProcessStart
from launch_ros.actions import Node

# Locate fake_image_pub.py at the workspace root.
# COLCON_PREFIX_PATH is set to <ws>/install when the workspace is sourced.
_prefix = os.environ.get("COLCON_PREFIX_PATH", "").split(":")[0]
_ws_root = str(Path(_prefix).parent) if _prefix else "/payload_camera_ws"
FAKE_PUB = str(Path(_ws_root) / "fake_image_pub.py")


# Production resolution used at reduced frame rate for Docker CI testing.
# 5120×800 rgb8 @ 10 Hz = ~120 MB/s per camera — too much for DDS loopback.
# 5120×800 rgb8 @ 3 Hz  =  ~37 MB/s per camera — within Docker loopback capacity.
TEST_WIDTH = 5120
TEST_HEIGHT = 800
NUM_SLICES = 4
TEST_RATE = 3
TEST_PPS_RATE = 2


def generate_launch_description():

    # ------------------------------------------------------------------
    # Fake cam0 — gradient pattern, also publishes /pps/time
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
            "--encoding", "rgb8",
        ],
        output="screen",
        name="fake_cam0",
    )

    # ------------------------------------------------------------------
    # Fake cam1 — gradient pattern (distinct zones → distinct slices),
    #             shares /pps/time from fake_cam0
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
            "--encoding", "rgb8",
        ],
        output="screen",
        name="fake_cam1",
    )

    # ------------------------------------------------------------------
    # cam0 stamp + split
    # ------------------------------------------------------------------
    stamp_split_cam0 = Node(
        package="fast_stamp_split",
        executable="fast_stamp_split_node",
        name="pps_stamp_and_split",
        namespace="cam0",
        output="screen",
        parameters=[{
            "pps_topic":   "/pps/time",
            "in_topic":    "/cam0/camera_node/image_raw",
            "require_pps": True,
            "full_width":  TEST_WIDTH,
            "full_height": TEST_HEIGHT,
            "num_slices":  NUM_SLICES,
            "out_0":       "R8_MONO_img0",
            "out_1":       "R8_MONO_img1",
            "out_2":       "R8_MONO_img2",
            "out_3":       "R8_MONO_img3",
        }],
    )

    # ------------------------------------------------------------------
    # cam1 stamp + split
    # ------------------------------------------------------------------
    stamp_split_cam1 = Node(
        package="fast_stamp_split",
        executable="fast_stamp_split_node",
        name="pps_stamp_and_split",
        namespace="cam1",
        output="screen",
        parameters=[{
            "pps_topic":   "/pps/time",
            "in_topic":    "/cam1/camera_node/image_raw",
            "require_pps": True,
            "full_width":  TEST_WIDTH,
            "full_height": TEST_HEIGHT,
            "num_slices":  NUM_SLICES,
            "out_0":       "BGGR_img0",
            "out_1":       "BGGR_img1",
            "out_2":       "BGGR_img2",
            "out_3":       "BGGR_img3",
        }],
    )

    # Give fake publishers 2 s to start before launching processing nodes
    delayed_splits = RegisterEventHandler(
        OnProcessStart(
            target_action=fake_cam0,
            on_start=[
                TimerAction(
                    period=2.0,
                    actions=[stamp_split_cam0, stamp_split_cam1],
                )
            ],
        )
    )

    return LaunchDescription([
        fake_cam0,
        fake_cam1,
        delayed_splits,
    ])
