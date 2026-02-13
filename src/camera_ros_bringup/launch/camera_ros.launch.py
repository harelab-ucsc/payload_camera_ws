#!/usr/bin/env python3
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():

    # 1) PPS time publisher
    # This will:
    #  - run python3 rpi_pwm_interface.py
    #  - run v4l2-ctl trigger_mode=1 on subdev2 and subdev5
    #  - run ppstest /dev/pps0 and publish /pps/time
    pps = Node(
        package="pps_time_pub",
        executable="pps_time_pub",
        name="pps_time_pub",
        output="screen",
        parameters=[{
            "pps_device": "/dev/pps0",
            "pps_topic": "/pps/time",
            "use_sudo": True,

            "start_pwm": True,
            "pwm_cmd": [
                "python3",
                "/home/pi5-alpha/ros2_iron/src/birdseye/scripts/rpi_pwm_interface.py"
            ],
            "pwm_start_delay_s": 0.25,

            "set_triggers": True,
            "v4l2_subdev2": "/dev/v4l-subdev2",
            "v4l2_subdev5": "/dev/v4l-subdev5",
            "trigger_delay_s": 0.05,
        }]
    )

    # 2) Camera node (same naming you had)
    cam0 = Node(
        package="camera_ros",
        executable="camera_node",
        name="camera_node",
        namespace="cam0",
        output="screen",
        parameters=[
            {"camera": 0},
            {"role": "viewfinder"},
            {"width": 5120},
            {"height": 800},
            {"frame_id": "cam0_optical_frame"},
            {"format": "XRGB8888"},
        ],
    )

    # 3) Stamp + split (same naming you had)
    stamp_split = Node(
    package="stamp_and_split_cam1",
    executable="pps_stamp_and_split",   # your entrypoint name
    name="pps_stamp_and_split",
    namespace="cam0",
    output="screen",
    parameters=[
        {"pps_topic": "/pps/time"},
        {"in_topic": "/cam0/camera_node/image_raw"},
        {"require_pps": True},
        {"full_width": 5120},
        {"full_height": 800},
        {"num_slices": 4},
        {"out_0": "img0"},
        {"out_1": "img1"},
        {"out_2": "img2"},
        {"out_3": "img3"},
    ],
)

    # 4) AS7265x node (same naming you had)
    as7265x = Node(
        package="as7265x_at",
        executable="as7265x_at_node",
        name="as7265x_stream",
        output="screen",
        parameters=[
            {"pps_topic": "/pps/time"},
        ],
    )

    return LaunchDescription([
        pps,
        cam0,
        stamp_split,
        as7265x,
    ])
