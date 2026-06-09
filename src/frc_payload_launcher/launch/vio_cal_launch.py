#!/usr/bin/env python3
"""
VIO calibration launch — stripped-down pipeline for collecting baggable image data.

Starts cameras, lets auto_cal converge and lock exposure immediately (force_cal=True,
no altitude gate), then publishes 8 split image topics via sync_node for ros2 bag.

Omitted vs fast_launch.py: radalt, spectrometer, inertial_sense_node, panel_scan.

Usage:
    VIO_CAL=true INDOOR_CAL=33333 ./start_services.sh
    # Wait for /cal/exposure_locked=true, then:
    ros2 bag record /sync/cam0_band_{0..3} /sync/cam1_rgb_{0..3} /pps/time
"""
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import RegisterEventHandler, TimerAction, DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch.event_handlers import OnProcessStart


def generate_launch_description():
    indoor_cal_arg = DeclareLaunchArgument(
        "indoor_cal",
        default_value="5000",
        description=(
            "Max exposure in microseconds for auto_cal convergence. "
            "Default 5000 µs is the flight-safe limit. "
            "Use INDOOR_CAL=33333 for indoor testing."
        ),
    )

    indoor_cal = LaunchConfiguration("indoor_cal")

    # ------------------------------------------------------------------
    # PPS node
    # ------------------------------------------------------------------
    pps = Node(
        package="pps_time_pub",
        executable="pps_time_pub",
        name="pps_time_pub",
        output="screen",
        parameters=[{
            "pps_device": "/dev/pps0",
            "pps_topic": "/pps/time",
            "use_sudo": True,
        }],
    )

    # ------------------------------------------------------------------
    # cam0 — mono sensor (arducam-pivariety 4-000c)
    # ------------------------------------------------------------------
    cam0 = Node(
        package="camera_ros",
        executable="camera_node",
        name="camera_node",
        namespace="cam0",
        output="screen",
        parameters=[
            {"camera": 0},
            {"role": "video"},
            {"width": 5120},
            {"height": 800},
            {"frame_id": "cam0_optical_frame"},
            {"format": "R16"},
            {"FrameDurationLimits": [28554, 199977]},
        ],
    )

    # ------------------------------------------------------------------
    # cam1 — color Bayer sensor (arducam-pivariety 6-000c)
    # ------------------------------------------------------------------
    cam1 = Node(
        package="camera_ros",
        executable="camera_node",
        name="camera_node",
        namespace="cam1",
        output="screen",
        parameters=[
            {"camera": 1},
            {"role": "still"},
            {"width": 5120},
            {"height": 800},
            {"frame_id": "cam1_optical_frame"},
            {"format": "SBGGR16"},
        ],
    )

    # ------------------------------------------------------------------
    # auto_cal — exposure lock node.
    # force_cal=True skips the altitude gate and starts AE convergence
    # immediately. Watch /cal/exposure_locked before starting the bag.
    # ------------------------------------------------------------------
    auto_cal = Node(
        package="mica_crp_cal",
        executable="auto_cal",
        name="auto_cal",
        output="screen",
        parameters=[{"force_cal": True, "max_exposure_us": indoor_cal}],
    )

    # ------------------------------------------------------------------
    # sync_node in publish_mode — splits and publishes 8 image topics
    # per PPS cycle instead of saving to disk.
    #   /sync/cam0_band_{0..3}  mono16 (450, 695, 735, 850 nm)
    #   /sync/cam1_rgb_{0..3}   bgr16 (debayered color panels)
    # ------------------------------------------------------------------
    sync_node = Node(
        package="stream_processor",
        executable="sync_node",
        name="sync_node",
        output="screen",
        parameters=[{
            "publish_mode": True,
            "require_calibration": False,
            "framerate": 3.0,
        }],
    )

    # ------------------------------------------------------------------
    # Sequencing:
    #   t=0.0s   pps starts
    #   t=2.0s   cam0 starts
    #   t=4.0s   cam1 starts (staggered to avoid I2C init collision)
    #   t=6.0s   auto_cal + sync_node start
    # ------------------------------------------------------------------
    delayed_cam0 = RegisterEventHandler(
        OnProcessStart(
            target_action=pps,
            on_start=[TimerAction(period=2.0, actions=[cam0])],
        )
    )

    delayed_cam1 = RegisterEventHandler(
        OnProcessStart(
            target_action=pps,
            on_start=[TimerAction(period=4.0, actions=[cam1])],
        )
    )

    delayed_auto_cal = RegisterEventHandler(
        OnProcessStart(
            target_action=pps,
            on_start=[TimerAction(period=6.0, actions=[auto_cal])],
        )
    )

    delayed_sync = RegisterEventHandler(
        OnProcessStart(
            target_action=pps,
            on_start=[TimerAction(period=6.0, actions=[sync_node])],
        )
    )

    return LaunchDescription([
        indoor_cal_arg,
        pps,
        delayed_cam0,
        delayed_cam1,
        delayed_auto_cal,
        delayed_sync,
    ])
