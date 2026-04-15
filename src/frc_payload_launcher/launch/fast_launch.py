#!/usr/bin/env python3
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import RegisterEventHandler, TimerAction, DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch.event_handlers import OnProcessStart


def generate_launch_description():
    # Declare arguments
    yaml_param_file_arg = DeclareLaunchArgument(
        'yaml_param_file',
        default_value='/home/pi5-alpha/ros2/ros2_iron/src/inertial-sense-sdk/ros2/launch/example_params.yaml',
        description='Path to the YAML parameter file for the inertial_sense_ros2 node'
    )

    antenna_offset_gps1_arg = DeclareLaunchArgument(
        'antenna_offset_gps1',
        default_value='[-0.02, 0.48, -0.36]',  # Default value; update as needed
        description='Offset for GPS1 antenna'
    )

    gps2_enable_arg = DeclareLaunchArgument(
        'gps2_enable',
        default_value='True',
        description='Boolean, whether or not to enable the second GPS antenna for compassing. Default: True'
    )

    antenna_offset_gps2_arg = DeclareLaunchArgument(
        'antenna_offset_gps2',
        default_value='[-0.02, -0.48, -0.36]',  # Default value; update as needed
        description='Offset for GPS2 antenna'
    )

    mag_declination_arg = DeclareLaunchArgument(
        'mag_declination',
        default_value='0.222',  # Default value; update as needed
        description='Magnetic declination value'
    )

    # Get the argument values
    yaml_param_file = LaunchConfiguration('yaml_param_file')
    antenna_offset_gps1 = LaunchConfiguration('antenna_offset_gps1')
    antenna_offset_gps2 = LaunchConfiguration('antenna_offset_gps2')
    gps2_enable = LaunchConfiguration('gps2_enable')
    mag_declination = LaunchConfiguration('mag_declination')

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

    #-------------------------------------------------------------------
    # Radar altimeter, spectrometer, and INS nodes
    #-------------------------------------------------------------------
    radalt = Node(
        package="ros2_radalt",
        executable="radalt",
        name="radalt",
        output="screen"
    )

    spectrometer = Node(
        package="as7265x_at",
        executable="as7265x_at_node",
        name="as7265x_at_node",
        output="screen"
    )

    # Inertial Sense node with parameters
    inertial_sense_node = Node(
        package='inertial_sense_ros2',
        executable='new_target',
        name='inertial_sense_node',
        output='screen',
        arguments=[yaml_param_file],
        parameters=[
            {'antenna_offset_gps1': antenna_offset_gps1},
            {'antenna_offset_gps2': antenna_offset_gps2},
            {'msg/gps2/enable': gps2_enable},
            {'mag_declination': mag_declination}
        ]
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
            "full_width":  5120,
            "full_height": 800,
            "num_slices":  4,
            "out_0":       "R8_MONO_img0",
            "out_1":       "R8_MONO_img1",
            "out_2":       "R8_MONO_img2",
            "out_3":       "R8_MONO_img3",
        }],
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
            "full_width":  5120,
            "full_height": 800,
            "num_slices":  4,
            "out_0":       "BGGR_img0",
            "out_1":       "BGGR_img1",
            "out_2":       "BGGR_img2",
            "out_3":       "BGGR_img3",
        }],
    )

    # ------------------------------------------------------------------
    # Sequencing:
    #   t=0.0s   pps starts
    #   t=2.0s   cam0 starts
    #   t=4.0s   cam1 starts (staggered to avoid I2C init collision)
    #   t=6.0s   both stamp_split nodes start
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

    delayed_stamp_splits = RegisterEventHandler(
        OnProcessStart(
            target_action=pps,
            on_start=[
                TimerAction(
                    period=6.0,
                    actions=[stamp_split_cam0, stamp_split_cam1],
                )
            ],
        )
    )

    return LaunchDescription([
        yaml_param_file_arg,
        antenna_offset_gps1_arg,
        antenna_offset_gps2_arg,
        gps2_enable_arg,
        mag_declination_arg,

        pps,
        radalt,
        spectrometer,
        inertial_sense_node,
        delayed_cam0,
        delayed_cam1,
        delayed_stamp_splits,
    ])
