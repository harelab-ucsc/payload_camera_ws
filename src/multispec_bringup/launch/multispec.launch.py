from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    # 1) PPS Publisher Node
    pps = Node(
        package="pps_time_pub",
        executable="pps_time_pub",
        name="pps_time_pub",
        output="screen",
    )

    # 2) Camera Node (raw image)
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
        ],
    )

    # 3) Stamping + splitting node (stamp raw images with PPS)
    stamp_split = Node(
        package="stamp_and_split_cam1",
        executable="pps_stamp_and_split",
        name="pps_stamp_and_split",
        namespace="cam0",
        output="screen",
        parameters=[
            {"in_topic": "/cam0/camera_node/image_raw/compressed"},
            {"qos_depth": 10},
        ],
        remappings=[
            ("image_raw_stamped", "img0"),
            ("image_copy_1", "img1"),
            ("image_copy_2", "img2"),
            ("image_copy_3", "img3"),
        ],
    )

    return LaunchDescription([
        pps,
        cam0,
        stamp_split,
    ])
