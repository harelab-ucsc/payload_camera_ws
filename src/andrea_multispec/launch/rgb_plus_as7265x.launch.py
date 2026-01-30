
    
from launch import LaunchDescription
from launch.actions import GroupAction
from launch_ros.actions import Node, PushRosNamespace

def generate_launch_description():
    # TODO: replace with stable by-id paths
    cam0_device = '/dev/v4l/by-id/usb-Arducam_Technology_co._Ltd._Arducam_MS_Camera...' 
    as_port = '/dev/serial/by-id/usb-FTDI_FT231X_USB_UART_...'

    cam0 = GroupAction([
        PushRosNamespace('cam0'),
        
        # 1. The Main Camera Driver
        Node(
            package='camera_ros',
            executable='camera_node',
            name='camera_node',
            output='screen',
            parameters=[{
                'device': cam0_device,
                'role': 'video', # Video role often enables MJPEG/Compressed
                'format': 'MJPEG',
                'width': 1280,
                'height': 720,
            }],
        ),

        # 2. Your New PPS Stamp & Split Node
        Node(
            package='multispec_bringup',
            executable='pps_stamp_and_split',
            name='pps_stamp_and_split',
            output='screen',
            parameters=[{
                # We are inside 'cam0' namespace, so in_topic is relative
                'in_topic': 'camera_node/image_raw/compressed',
                'pps_topic': '/pps/time', # Global topic
                'require_pps': True,
                'out_main': 'image_compressed_stamped',
                'out_1': 'img0',
                'out_2': 'img1',
                'out_3': 'img2',
            }],
        ),
    ])

    as7265x = Node(
        package='as7265x_at',
        executable='as7265x_at_node',
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

    