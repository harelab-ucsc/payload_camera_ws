from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():

    # 1) PPS time publisher (/pps/time)
    pps = Node(
        package="pps_time_pub",
        executable="pps_time_pub",
        name="pps_time_pub",
        output="screen",
    )

    # 2) Camera node (/cam0/camera_node/image_raw)
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
            # optional: stop the "auto-selecting format" warning
            {"format": "XRGB8888"},
        ],
    )

    # 3) PPS stamp + split (your existing node)
    # This node currently publishes: image_raw_stamped, image_copy_1, image_copy_2, image_copy_3
    # We'll remap those to: /cam0/img0..img3 to match your whiteboard.
    stamp_split = Node(
        package="stamp_and_split_cam1",     # <-- change if your package name differs
        executable="pps_stamp_and_split",   # <-- change if your console_script differs
        name="pps_stamp_and_split",
        namespace="cam0",
        output="screen",
        parameters=[
            {"in_topic": "/cam0/camera_node/image_raw"},
            {"qos_depth": 10},
        ],
        remappings=[
            ("image_raw_stamped", "img0"),
            ("image_copy_1", "img1"),
            ("image_copy_2", "img2"),
            ("image_copy_3", "img3"),
        ],
    )

    # 4) AS7265x stream node (already PPS-stamped internally)
    as7265x = Node(
        package="as7265x_at",
        executable="as7265x_at_node",  # <-- confirm exact executable name in your setup.py
        name="as7265x_stream",
        output="screen",
        parameters=[
            {"pps_topic": "/pps/time"},
            # also set your serial params here if you want:
            # {"serial_port": "/dev/serial/by-id/usb-FTDI_..."},
            # {"calibrated": True},
            # {"integration_time": 20},
            # {"gain": 1},
            # {"interval": 1},
        ],
    )

    return LaunchDescription([
        pps,
        cam0,
        stamp_split,
        as7265x,
    ])
