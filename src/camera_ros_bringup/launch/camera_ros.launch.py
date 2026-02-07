#!/usr/bin/env python3

from launch import LaunchDescription
from launch.actions import ExecuteProcess, TimerAction
from launch_ros.actions import Node


def generate_launch_description():
    pwm_setup = ExecuteProcess(
        cmd=['python3', '/home/pi4/camera_ws/src/camera_ros_bringup/tmp/rpi_pwm_control.py'],
        output='screen'
    )

    camera_node = Node(
        package='camera_ros',
        executable='camera_node',
        namespace='cam0',
        name='cam0_camera',
        output='screen',
        parameters=[{
            'camera': 0,
            'role': 'viewfinder',
            'width': 5120,
            'height': 800,
            'frame_id': 'cam0_optical_frame',
        }],
    )

    pps_stamp_and_split_node = Node(
        package='stamp_and_split_cam1',
        executable='pps_stamp_and_split',
        namespace='cam0',
        name='pps_stamp_and_split',
        output='screen',
        parameters=[{
            'in_topic': '/cam0/cam0_camera/image_raw', # changed this cuz it was wrong
            'qos_depth': 10,
        }],
    )

    delayed_pps = TimerAction(
        period=5.0,
        actions=[pps_stamp_and_split_node]
    )

    return LaunchDescription([
        pwm_setup,
        camera_node,
        delayed_pps,
    ])
