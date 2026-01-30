#!/usr/bin/env python3
"""
multispec_pairer.py

Pairs 4 PPS-stamped image streams (quadrants/copies) with PPS-stamped AS7265x spectra.

Behavior:
- Buffers images keyed by exact header stamp (sec,nsec).
- Buffers recent spectra.
- When all 4 images for a stamp are present, selects the nearest spectrum within slop_ms.
- Publishes per-quadrant paired topics:
    /multispec/q0/image, /multispec/q0/spectrum
    /multispec/q1/image, /multispec/q1/spectrum
    /multispec/q2/image, /multispec/q2/spectrum
    /multispec/q3/image, /multispec/q3/spectrum

Notes:
- If your split node currently republishes copies with the same stamp, this will
  correctly attach one spectrum to all 4.
- If later you truly split into quadrants, topic names stay the same and this still works.
"""

from collections import deque, defaultdict
import time as pytime

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data

from sensor_msgs.msg import Image
from as7265x_at_msgs.msg import AS7265xCal


def stamp_to_ns(stamp) -> int:
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


def ns_to_stamp_fields(ns: int):
    sec = ns // 1_000_000_000
    nsec = ns % 1_000_000_000
    return int(sec), int(nsec)


class MultispecPairer(Node):
    def __init__(self):
        super().__init__("multispec_pairer")

        # -------- Parameters --------
        # Default for your namespaced cam0 pipeline
        self.declare_parameter("image0_topic", "/cam0/image_raw_stamped")  # q0
        self.declare_parameter("image1_topic", "/cam0/image_copy_1")       # q1
        self.declare_parameter("image2_topic", "/cam0/image_copy_2")       # q2
        self.declare_parameter("image3_topic", "/cam0/image_copy_3")       # q3
        self.declare_parameter("spec_topic", "/as7265x/calibrated_values")

        self.declare_parameter("slop_ms", 100.0)          # max allowed |dt| for pairing
        self.declare_parameter("spec_queue_size", 200)    # how many spectra to keep
        self.declare_parameter("frame_queue_size", 50)    # how many image-stamps to keep
        self.declare_parameter("out_ns", "/multispec")    # output namespace root

        self.img_topics = [
            self.get_parameter("image0_topic").value,
            self.get_parameter("image1_topic").value,
            self.get_parameter("image2_topic").value,
            self.get_parameter("image3_topic").value,
        ]
        self.spec_topic = self.get_parameter("spec_topic").value
        self.slop_ns = int(float(self.get_parameter("slop_ms").value) * 1e6)
        self.spec_qmax = int(self.get_parameter("spec_queue_size").value)
        self.frame_qmax = int(self.get_parameter("frame_queue_size").value)
        self.out_ns = self.get_parameter("out_ns").value.rstrip("/")

        # -------- Buffers --------
        # spectra: deque of (t_ns, AS7265xCal_msg)
        self.spec_buf = deque(maxlen=self.spec_qmax)

        # frames: dict stamp_ns -> dict{qidx: Image_msg}
        self.frame_buf = defaultdict(dict)
        self.frame_order = deque(maxlen=self.frame_qmax)  # keep order to GC old stamps

        # -------- Publishers --------
        # Per-quadrant outputs
        self.pub_img = []
        self.pub_spec = []
        for qi in range(4):
            img_t = f"{self.out_ns}/q{qi}/image"
            spec_t = f"{self.out_ns}/q{qi}/spectrum"
            self.pub_img.append(self.create_publisher(Image, img_t, qos_profile_sensor_data))
            self.pub_spec.append(self.create_publisher(AS7265xCal, spec_t, 10))

        # -------- Subscribers --------
        # Images
        self.sub_imgs = []
        for qi, topic in enumerate(self.img_topics):
            self.sub_imgs.append(
                self.create_subscription(
                    Image,
                    topic,
                    lambda msg, qi=qi: self.on_image(msg, qi),
                    qos_profile_sensor_data,
                )
            )

        # Spectrum
        self.sub_spec = self.create_subscription(
            AS7265xCal,
            self.spec_topic,
            self.on_spec,
            10
        )

        self.get_logger().info("MultispecPairer running with:")
        self.get_logger().info(f"  Images: {self.img_topics}")
        self.get_logger().info(f"  Spec:   {self.spec_topic}")
        self.get_logger().info(f"  slop_ms={self.slop_ns/1e6:.1f}  out_ns={self.out_ns}")

    def on_spec(self, msg: AS7265xCal):
        t_ns = stamp_to_ns(msg.header.stamp)
        self.spec_buf.append((t_ns, msg))

        # Optional cleanup of old frames if spec advances a lot
        self.gc_old_frames()

    def on_image(self, msg: Image, qi: int):
        t_ns = stamp_to_ns(msg.header.stamp)

        # Track stamp order for GC
        if t_ns not in self.frame_buf:
            self.frame_order.append(t_ns)

        # Store this quadrant image for this stamp
        self.frame_buf[t_ns][qi] = msg

        # If we have all 4 images for this stamp, try pairing
        if len(self.frame_buf[t_ns]) == 4:
            self.try_pair_and_publish(t_ns)

    def find_nearest_spec(self, t_ns: int):
        if not self.spec_buf:
            return None, None

        # linear scan is fine for small buffers
        best = None
        best_dt = None
        for s_ns, s_msg in self.spec_buf:
            dt = abs(s_ns - t_ns)
            if best_dt is None or dt < best_dt:
                best_dt = dt
                best = (s_ns, s_msg)

        if best_dt is not None and best_dt <= self.slop_ns:
            return best[1], best_dt
        return None, None

    def try_pair_and_publish(self, t_ns: int):
        spec_msg, dt_ns = self.find_nearest_spec(t_ns)
        if spec_msg is None:
            # No spectrum close enough yet; keep frame buffered briefly
            return

        # Publish per-quadrant: image + spectrum (spectrum header forced to image stamp)
        for qi in range(4):
            img = self.frame_buf[t_ns][qi]
            self.pub_img[qi].publish(img)

            # Clone-ish spectrum: reuse msg object but adjust header fields
            out_spec = AS7265xCal()
            out_spec.header = spec_msg.header  # copy header object
            out_spec.values = list(spec_msg.values)

            sec, nsec = ns_to_stamp_fields(t_ns)
            out_spec.header.stamp.sec = sec
            out_spec.header.stamp.nanosec = nsec
            out_spec.header.frame_id = f"as7265x_q{qi}"

            self.pub_spec[qi].publish(out_spec)

        self.get_logger().info(
            f"paired stamp={t_ns} dt_ms={dt_ns/1e6:.2f} len(values)={len(spec_msg.values)}"
        )

        # Done with this stamp
        if t_ns in self.frame_buf:
            del self.frame_buf[t_ns]

        self.gc_old_frames()

    def gc_old_frames(self):
        # Remove stamps that fell out of our frame_order deque
        # (deque maxlen will drop old entries automatically; we mirror that cleanup)
        if len(self.frame_order) < self.frame_qmax:
            return

        # best-effort: if deque is full, delete anything not in it anymore
        keep = set(self.frame_order)
        dead = [k for k in self.frame_buf.keys() if k not in keep]
        for k in dead:
            del self.frame_buf[k]


def main():
    rclpy.init()
    node = MultispecPairer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

