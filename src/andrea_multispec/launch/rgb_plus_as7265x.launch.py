from launch import LaunchDescription
from launch.actions import GroupAction
from launch_ros.actions import Node, PushRosNamespace

def generate_launch_description():
    # TODO: replace with stable by-id paths
    cam0_device = '/dev/v4l/by-id/REPLACE_WITH_RGB_CAMERA'
    as_port = '/dev/serial/by-id/REPLACE_WITH_FTDI'

    cam0 = GroupAction([
        PushRosNamespace('cam0'),
        Node(
            package='camera_ros',
            executable='camera_node',
            name='camera_ros',
            output='screen',
            parameters=[{'device': cam0_device}],
        ),
    ])

    as7265x = Node(
        package='as7265x_at',
        executable='as7265x_at_node',  # change if your exec name differs
        name='as7265x_stream',
        output='screen',
        parameters=[{
            'serial_port': as_port,
            'baudrate': 115200,
            'calibrated': True,
        }],
    )

    cam1 = GroupAction([
        PushRosNamespace('cam1'),
        Node(
            package='multispec',
            executable='spectral_bridge',
            name='spectral_bridge',
            output='screen',
            parameters=[{
                'in_topic': '/as7265x/at_raw',
                'band_map': {
                    'red': 0,
                    'green': 6,
                    'nir': 14,
                    'red_edge': 12,
                }
            }],
        ),
    ])

    return LaunchDescription([cam0, as7265x, cam1])
    
