# #!/usr/bin/env python3
# """
# pps_stamp_and_split.py

# PPS-aware node:
#   - subscribes to /pps/time
#   - subscribes to camera Image topic
#   - stamps each frame with latest PPS time (or node time as fallback)
#   - republishes on 4 topics
# """

# import threading
# import rclpy
# from rclpy.node import Node
# from sensor_msgs.msg import Image
# from builtin_interfaces.msg import Time


# class PpsStampAndSplit(Node):
#     def __init__(self):
#         super().__init__('pps_stamp_and_split')

#         # Parameters
#         self.in_topic = self.declare_parameter(
#             'in_topic', '/camera/image_raw'
#         ).get_parameter_value().string_value

#         depth = self.declare_parameter(
#             'qos_depth', 10
#         ).get_parameter_value().integer_value

#         # PPS state
#         self.latest_pps_stamp = None
#         self.pps_lock = threading.Lock()
#         self.warned_no_pps = False

#         # Subscribe to PPS time
#         self.create_subscription(
#             Time,
#             "/pps/time",
#             self.pps_cb,
#             10
#         )

#         # Camera subscriber
#         self.sub = self.create_subscription(
#             Image,
#             self.in_topic,
#             self.cam_callback,
#             depth
#         )

#         # Publishers
#         self.pub_main = self.create_publisher(Image, 'image_raw_stamped', depth)
#         self.pub_1 = self.create_publisher(Image, 'image_copy_1', depth)
#         self.pub_2 = self.create_publisher(Image, 'image_copy_2', depth)
#         self.pub_3 = self.create_publisher(Image, 'image_copy_3', depth)

#         self.get_logger().info(
#             f"PpsStampAndSplit running. Subscribing to {self.in_topic} and /pps/time"
#         )

#     def pps_cb(self, msg: Time):
#         with self.pps_lock:
#             self.latest_pps_stamp = msg

#     def cam_callback(self, msg: Image):
#         with self.pps_lock:
#             pps_stamp = self.latest_pps_stamp

#         if pps_stamp is None:
#             if not self.warned_no_pps:
#                 self.get_logger().warn(
#                     "No PPS timestamp yet; using node clock time instead."
#                 )
#                 self.warned_no_pps = True
#             msg.header.stamp = self.get_clock().now().to_msg()
#         else:
#             msg.header.stamp = pps_stamp

#         self.pub_main.publish(msg)
#         self.pub_1.publish(msg)
#         self.pub_2.publish(msg)
#         self.pub_3.publish(msg)


# def main():
#     rclpy.init()
#     node = PpsStampAndSplit()
#     rclpy.spin(node)
#     node.destroy_node()
#     rclpy.shutdown()


# if __name__ == '__main__':
#     main()



#!/usr/bin/env python3
"""
pps_stamp_and_split.py

PPS-aware node:
  - subscribes to /pps/time
  - subscribes to camera Image topic
  - stamps each frame with latest PPS time (or node time as fallback)
  - republishes on 4 topics
"""

import threading
import copy

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data, QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image
from builtin_interfaces.msg import Time


class PpsStampAndSplit(Node):
    def __init__(self):
        super().__init__('pps_stamp_and_split')

        # Parameters
        self.declare_parameter('pps_topic', '/pps/time')

        # Default to your camera_ros topic
        self.declare_parameter('in_topic', '/cam0/camera_node/image_raw')

        # Output topics (relative names OK, but I prefer explicit params)
        self.declare_parameter('out_main', 'image_raw_stamped')
        self.declare_parameter('out_1', 'image_copy_1')
        self.declare_parameter('out_2', 'image_copy_2')
        self.declare_parameter('out_3', 'image_copy_3')

        # If True: drop frames until PPS has been received at least once
        self.declare_parameter('require_pps', True)

        # QoS depth (only used for PPS reliable QoS)
        self.declare_parameter('pps_depth', 10)

        self.pps_topic = self.get_parameter('pps_topic').value
        self.in_topic = self.get_parameter('in_topic').value

        self.out_main = self.get_parameter('out_main').value
        self.out_1 = self.get_parameter('out_1').value
        self.out_2 = self.get_parameter('out_2').value
        self.out_3 = self.get_parameter('out_3').value

        self.require_pps = bool(self.get_parameter('require_pps').value)
        pps_depth = int(self.get_parameter('pps_depth').value)

        # PPS state
        self.latest_pps_stamp = None
        self.pps_lock = threading.Lock()
        self.warned_no_pps = False

        # QoS:
        # - Images: sensor data QoS (best effort, keep last small)
        img_qos = qos_profile_sensor_data

        # - PPS: reliable small queue
        pps_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=pps_depth,
        )

        # Subscribe to PPS time
        self.create_subscription(Time, self.pps_topic, self.pps_cb, pps_qos)

        # Camera subscriber
        self.sub = self.create_subscription(Image, self.in_topic, self.cam_callback, img_qos)

        # Publishers (same QoS as images)
        self.pub_main = self.create_publisher(Image, self.out_main, img_qos)
        self.pub_1 = self.create_publisher(Image, self.out_1, img_qos)
        self.pub_2 = self.create_publisher(Image, self.out_2, img_qos)
        self.pub_3 = self.create_publisher(Image, self.out_3, img_qos)

        self.get_logger().info(
            "PpsStampAndSplit running:\n"
            f"  pps_topic: {self.pps_topic}\n"
            f"  in_topic:  {self.in_topic}\n"
            f"  outs:      {self.out_main}, {self.out_1}, {self.out_2}, {self.out_3}\n"
            f"  require_pps: {self.require_pps}"
        )

    def pps_cb(self, msg: Time):
        with self.pps_lock:
            self.latest_pps_stamp = msg

    def _get_stamp(self):
        with self.pps_lock:
            pps_stamp = self.latest_pps_stamp

        if pps_stamp is None:
            if self.require_pps:
                if not self.warned_no_pps:
                    self.get_logger().warn(
                        f"No PPS timestamp yet on {self.pps_topic}; dropping frames until PPS arrives."
                    )
                    self.warned_no_pps = True
                return None

            if not self.warned_no_pps:
                self.get_logger().warn(
                    f"No PPS timestamp yet on {self.pps_topic}; using node clock time."
                )
                self.warned_no_pps = True
            return self.get_clock().now().to_msg()

        return pps_stamp

    def _clone_image_shallow(self, src: Image) -> Image:
        """
        Create a new Image message object that references the same data buffer.
        This avoids accidental shared-mutation weirdness while not copying 16MB.
        """
        dst = Image()
        dst.header = copy.copy(src.header)
        dst.height = src.height
        dst.width = src.width
        dst.encoding = src.encoding
        dst.is_bigendian = src.is_bigendian
        dst.step = src.step
        dst.data = src.data  # shared buffer reference (no big copy)
        return dst

    def cam_callback(self, msg: Image):
        stamp = self._get_stamp()
        if stamp is None:
            return

        # Stamp original
        msg.header.stamp = stamp

        # Publish stamped + copies
        self.pub_main.publish(msg)

        # Use shallow clones for safety (still no huge data copy)
        self.pub_1.publish(self._clone_image_shallow(msg))
        self.pub_2.publish(self._clone_image_shallow(msg))
        self.pub_3.publish(self._clone_image_shallow(msg))


def main():
    rclpy.init()
    node = PpsStampAndSplit()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()


