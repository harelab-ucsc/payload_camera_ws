#!/usr/bin/env python3
"""
pps_stamp_and_split_compressed.py

PPS-aware node for COMPRESSED images:
  - subscribes to /pps/time (builtin_interfaces/Time)
  - subscribes to camera CompressedImage topic
  - stamps each frame with latest PPS time (or node time as fallback)
  - republishes on 4 topics
"""

import threading
import copy

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data, QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import CompressedImage
from builtin_interfaces.msg import Time


class PpsStampAndSplit(Node):
    def __init__(self):
        super().__init__('pps_stamp_and_split')

        # Parameters
        self.declare_parameter('pps_topic', '/pps/time')

        # Default to compressed camera_ros topic
        self.declare_parameter('in_topic', '/cam0/camera_node/image_raw/compressed')

        # Output topics
        self.declare_parameter('out_main', 'image_compressed_stamped')
        self.declare_parameter('out_1', 'image_comp_1')
        self.declare_parameter('out_2', 'image_comp_2')
        self.declare_parameter('out_3', 'image_comp_3')

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
        img_qos = qos_profile_sensor_data  # best effort, low latency
        pps_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=pps_depth,
        )

        # Subscribe to PPS time
        self.create_subscription(Time, self.pps_topic, self.pps_cb, pps_qos)

        # Camera subscriber (COMPRESSED)
        self.sub = self.create_subscription(
            CompressedImage, self.in_topic, self.cam_callback, img_qos
        )

        # Publishers (COMPRESSED)
        self.pub_main = self.create_publisher(CompressedImage, self.out_main, img_qos)
        self.pub_1 = self.create_publisher(CompressedImage, self.out_1, img_qos)
        self.pub_2 = self.create_publisher(CompressedImage, self.out_2, img_qos)
        self.pub_3 = self.create_publisher(CompressedImage, self.out_3, img_qos)

        self.get_logger().info(
            "PpsStampAndSplit (CompressedImage) running:\n"
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

    def _clone_compressed_shallow(self, src: CompressedImage) -> CompressedImage:
        """
        Create a new CompressedImage message object.
        NOTE: src.data is a Python 'bytes' (immutable) in many cases, so sharing is fine.
        """
        dst = CompressedImage()
        dst.header = copy.copy(src.header)
        dst.format = src.format
        dst.data = src.data
        return dst

    def cam_callback(self, msg: CompressedImage):
        stamp = self._get_stamp()
        if stamp is None:
            return

        msg.header.stamp = stamp

        self.pub_main.publish(msg)
        self.pub_1.publish(self._clone_compressed_shallow(msg))
        self.pub_2.publish(self._clone_compressed_shallow(msg))
        self.pub_3.publish(self._clone_compressed_shallow(msg))


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
