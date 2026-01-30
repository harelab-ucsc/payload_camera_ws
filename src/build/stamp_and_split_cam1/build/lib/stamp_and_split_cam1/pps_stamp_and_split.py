#!/usr/bin/env python3
"""
pps_stamp_and_split.py

PPS-aware node:
  - runs `sudo ppstest /dev/pps0` in a background thread
  - parses PPS timestamps and stores the latest one
  - subscribes to a camera Image topic
  - stamps each frame with latest PPS time (or node time as fallback)
  - republishes on 4 topics

@author     Slugaculture
@date       12 Jan 2026
@version    1.0.2
"""

import re
import subprocess
import threading

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Image
from builtin_interfaces.msg import Time


class PpsStampAndSplit(Node):
    def __init__(self):
        super().__init__('pps_stamp_and_split')

        # Parameters
        self.in_topic = self.declare_parameter(
            'in_topic', '/camera/image_raw'
        ).get_parameter_value().string_value

        depth = self.declare_parameter(
            'qos_depth', 10
        ).get_parameter_value().integer_value

        # Latest PPS timestamp
        self.latest_pps_stamp = None
        self.pps_lock = threading.Lock()
        self.warned_no_pps = False

        # Start PPS reader thread
        self.get_logger().info("Starting PPS reader thread (ppstest /dev/pps0)...")
        self.pps_thread = threading.Thread(target=self._pps_reader_thread, daemon=True)
        self.pps_thread.start()

        # Camera subscriber
        self.sub = self.create_subscription(
            Image,
            self.in_topic,
            self.cam_callback,
            depth
        )

        # Publishers (relative names so namespace works: /cam0/... when launched in namespace cam0)
        self.pub_main = self.create_publisher(Image, 'image_raw_stamped', depth)
        self.pub_1 = self.create_publisher(Image, 'image_copy_1', depth)
        self.pub_2 = self.create_publisher(Image, 'image_copy_2', depth)
        self.pub_3 = self.create_publisher(Image, 'image_copy_3', depth)

        self.get_logger().info(f"PpsStampAndSplit running. Subscribing to: {self.in_topic}")

    def _pps_reader_thread(self):
        """
        Runs `sudo ppstest /dev/pps0` and parses lines like:
          source 0 - assert 1768602692.760410425, sequence: ...
        """
        cmd = ['sudo', 'ppstest', '/dev/pps0']

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
        except Exception as e:
            self.get_logger().error(f"Failed to start ppstest: {e}")
            return

        assert_re = re.compile(r'assert\s+(\d+)\.(\d+)')

        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue

            m = assert_re.search(line)
            if not m:
                continue

            sec_str, nsec_str = m.group(1), m.group(2)
            try:
                sec = int(sec_str)
                # normalize ns to 9 digits
                nsec_str = (nsec_str + '0' * 9)[:9]
                nsec = int(nsec_str)
            except ValueError:
                continue

            t = Time()
            t.sec = sec
            t.nanosec = nsec

            with self.pps_lock:
                self.latest_pps_stamp = t

        proc.wait()
        self.get_logger().warn("ppstest exited; PPS reader thread stopped")

    def cam_callback(self, msg: Image):
        with self.pps_lock:
            pps_stamp = self.latest_pps_stamp

        if pps_stamp is None:
            if not self.warned_no_pps:
                self.get_logger().warn("No PPS timestamp yet; using node clock time instead.")
                self.warned_no_pps = True
            msg.header.stamp = self.get_clock().now().to_msg()
        else:
            msg.header.stamp = pps_stamp

        # Publish to 4 topics
        self.pub_main.publish(msg)
        self.pub_1.publish(msg)
        self.pub_2.publish(msg)
        self.pub_3.publish(msg)


def main():
    rclpy.init()
    node = PpsStampAndSplit()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()

