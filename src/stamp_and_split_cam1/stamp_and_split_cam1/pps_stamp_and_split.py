#!/usr/bin/env python3
"""
pps_stamp_and_split_raw.py

- Subscribes to:
    /pps/time (builtin_interfaces/Time)
    in_topic (sensor_msgs/Image) default: /cam0/camera_node/image_raw
- For each frame:
    - stamps header.stamp with latest PPS time (or drops until PPS)
    - splits a 5120x800 side-by-side panorama into 4 slices (1280x800 each)
    - publishes 4 Image topics (img0..img3 by default)
"""

import threading
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data, QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image
from builtin_interfaces.msg import Time


class PpsStampAndSplitRaw(Node):
    def __init__(self):
        super().__init__("pps_stamp_and_split")

        # ---------------- Parameters ----------------
        self.declare_parameter("pps_topic", "/pps/time")
        self.declare_parameter("in_topic", "/cam0/camera_node/image_raw")

        # Output topics (publish 4 slices)
        self.declare_parameter("out_0", "img0")
        self.declare_parameter("out_1", "img1")
        self.declare_parameter("out_2", "img2")
        self.declare_parameter("out_3", "img3")

        # If True: drop frames until PPS has been received at least once
        self.declare_parameter("require_pps", True)

        # Expected geometry
        self.declare_parameter("full_width", 5120)
        self.declare_parameter("full_height", 800)
        self.declare_parameter("num_slices", 4)

        self.declare_parameter("pps_depth", 10)
      

        self.pps_topic = self.get_parameter("pps_topic").value
        self.in_topic = self.get_parameter("in_topic").value

        self.out_0 = self.get_parameter("out_0").value
        self.out_1 = self.get_parameter("out_1").value
        self.out_2 = self.get_parameter("out_2").value
        self.out_3 = self.get_parameter("out_3").value

        self.require_pps = bool(self.get_parameter("require_pps").value)

        self.full_width = int(self.get_parameter("full_width").value)
        self.full_height = int(self.get_parameter("full_height").value)
        self.num_slices = int(self.get_parameter("num_slices").value)
        assert self.num_slices == 4, "This node currently assumes 4 slices (num_slices=4)."

        self.slice_w = self.full_width // self.num_slices

        self.latest_pps_stamp = None
        self.pps_lock = threading.Lock()
        self.warned_no_pps = False

        img_qos = qos_profile_sensor_data  # best effort
        pps_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=int(self.get_parameter("pps_depth").value),
        )

        # Subscribers
        self.create_subscription(Time, self.pps_topic, self._pps_cb, pps_qos)
        self.create_subscription(Image, self.in_topic, self._img_cb, img_qos)

        # Publishers (raw Image)
        self.pub0 = self.create_publisher(Image, self.out_0, img_qos)
        self.pub1 = self.create_publisher(Image, self.out_1, img_qos)
        self.pub2 = self.create_publisher(Image, self.out_2, img_qos)
        self.pub3 = self.create_publisher(Image, self.out_3, img_qos)

        self.get_logger().info(
            "PpsStampAndSplitRaw running:\n"
            f"  pps_topic: {self.pps_topic}\n"
            f"  in_topic:  {self.in_topic}\n"
            f"  expect:    {self.full_width}x{self.full_height} -> 4 slices of {self.slice_w}x{self.full_height}\n"
            f"  outs:      {self.out_0}, {self.out_1}, {self.out_2}, {self.out_3}\n"
            f"  require_pps: {self.require_pps}"
        )

    def _pps_cb(self, msg: Time):
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
            return self.get_clock().now().to_msg()

        return pps_stamp

    def _slice_and_publish(self, msg: Image, stamp: Time):
        # Validate dimensions
        w = msg.width
        h = msg.height

        if (w, h) != (self.full_width, self.full_height):
            self.get_logger().warn(
                f"Unexpected image size {w}x{h} (expected {self.full_width}x{self.full_height}). "
                "Will still attempt to split evenly."
            )


        full_step = msg.step
        if full_step == 0:
            self.get_logger().warn("Image step is 0; cannot split.")
            return

      
        if w > 0:
            bpp = full_step // w
        else:
            self.get_logger().warn("Image width is 0; cannot split.")
            return

        slice_w = w // self.num_slices if w else self.slice_w
        slice_step = slice_w * bpp

        data = msg.data  # bytes-like

        def make_slice(i: int) -> Image:
            x0 = i * slice_w
            x1 = (i + 1) * slice_w
            # Build new data row-by-row to preserve correct step
            out_bytes = bytearray()
            for row in range(h):
                row_start = row * full_step
                out_bytes += data[row_start + x0 * bpp : row_start + x1 * bpp]

            out = Image()
            out.header = msg.header
            out.header.stamp = stamp

            out.height = h
            out.width = slice_w
            out.encoding = msg.encoding
            out.is_bigendian = msg.is_bigendian
            out.step = slice_step
            out.data = bytes(out_bytes)
            return out

        s0 = make_slice(0)
        s1 = make_slice(1)
        s2 = make_slice(2)
        s3 = make_slice(3)

        self.pub0.publish(s0)
        self.pub1.publish(s1)
        self.pub2.publish(s2)
        self.pub3.publish(s3)

    def _img_cb(self, msg: Image):
        stamp = self._get_stamp()
        if stamp is None:
            return
        self._slice_and_publish(msg, stamp)


def main():
    rclpy.init()
    node = PpsStampAndSplitRaw()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
