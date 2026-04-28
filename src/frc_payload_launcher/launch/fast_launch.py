#!/usr/bin/env python3
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import RegisterEventHandler, TimerAction
from launch.event_handlers import OnProcessStart


def generate_launch_description():

    # ------------------------------------------------------------------
    # PPS node — shared by both cameras
    # ------------------------------------------------------------------
    pps = Node(
        package="pps_time_pub",
        executable="pps_time_pub",
        name="pps_time_pub",
        output="screen",
        parameters=[{
            "pps_device":        "/dev/pps0",
            "pps_topic":         "/pps/time",
            "use_sudo":          True,
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
            {"camera":   0},
            {"role":     "still"},
            {"width":    5120},
            {"height":   800},
            {"frame_id": "cam0_optical_frame"},
            {"format":   "R16"},
            # FrameDurationLimits is a [min, max] span in microseconds; 333333 µs = 3 fps
            {"FrameDurationLimits": [333333, 333333]},
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
            {"camera":   1},
            {"role":     "still"},
            {"width":    5120},
            {"height":   800},
            {"frame_id": "cam1_optical_frame"},
            {"format":   "SBGGR16"},
            {"FrameDurationLimits": [333333, 333333]},
        ],
    )

    # ------------------------------------------------------------------
    # stream_processor — PPS-synced save node (does split + spectral
    # correction + debayer in-process via the C++ extension; no
    # intermediate image topics on DDS)
    # ------------------------------------------------------------------
    sync_node = Node(
        package="stream_processor",
        executable="sync_node",
        name="sync_node",
        output="screen",
        parameters=[{
            "db_name":      "flight_data",
            "img_format":   ".tiff",
            "dir_name":     "parsed_flight",
            "sensors_yaml": "sensor_params/birdsEyeSensorParams.yaml",
            "clicks_csv":   "catch/data.csv",
        }],
    )

    # ------------------------------------------------------------------
    # Sequencing:
    #   t=0.0s   pps starts
    #   t=2.0s   cam0 starts
    #   t=4.0s   cam1 starts (staggered to avoid I2C init collision)
    #   t=6.0s   sync_node (stream_processor) starts
    # ------------------------------------------------------------------
    delayed_cam0 = RegisterEventHandler(
        OnProcessStart(
            target_action=pps,
            on_start=[
                TimerAction(
                    period=2.0,
                    actions=[cam0],
                )
            ],
        )
    )

    delayed_cam1 = RegisterEventHandler(
        OnProcessStart(
            target_action=pps,
            on_start=[
                TimerAction(
                    period=4.0,
                    actions=[cam1],
                )
            ],
        )
    )

    delayed_sync = RegisterEventHandler(
        OnProcessStart(
            target_action=pps,
            on_start=[
                TimerAction(
                    period=6.0,
                    actions=[sync_node],
                )
            ],
        )
    )

    return LaunchDescription([
        pps,
        delayed_cam0,
        delayed_cam1,
        delayed_sync,
    ])
