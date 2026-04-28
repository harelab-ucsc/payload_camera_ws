#!/usr/bin/env python3
"""
fake_image_pub.py

Publishes synthetic sensor_msgs/Image frames on /cam0/camera_node/image_raw
and fake PPS timestamps on /pps/time so the stamp-and-split pipeline can be
tested without real hardware.

Usage (after sourcing ROS2):
  python3 fake_image_pub.py [OPTIONS]

Options:
  --topic      IMAGE topic to publish on   (default: /cam0/camera_node/image_raw)
  --pps        PPS topic to publish on     (default: /pps/time)
  --rate       Publish rate in Hz          (default: 10.0)
  --width      Full panorama width px      (default: 5120)
  --height     Image height px             (default: 800)
  --encoding   Image encoding              (default: rgb8)
  --pattern    Image pattern:
                 solid      — flat colour (use --color R,G,B)
                 gradient   — left-to-right hue sweep across 4 camera zones
                 noise      — random grayscale noise each frame
                 checker    — checkerboard (use --block N)
                 file       — repeat a single image file (use --file PATH)
               (default: gradient)
  --color      R,G,B for solid pattern     (default: 128,128,128)
  --block      Checker block size px       (default: 64)
  --file       Path to image file for file pattern
  --no-pps     Skip publishing PPS entirely (frames will be dropped by nodes
               that have require_pps=True)
  --pps-rate   PPS rate in Hz              (default: 1.0)
  --frame-id   header frame_id             (default: camera)

Examples:
  # Default gradient at 10 Hz + 1 Hz PPS
  python3 fake_image_pub.py

  # Noise at 30 Hz, no PPS (test drop behaviour)
  python3 fake_image_pub.py --pattern noise --rate 30 --no-pps

  # Publish a real image file at 5 Hz
  python3 fake_image_pub.py --pattern file --file /tmp/test.png --rate 5

  # Solid red
  python3 fake_image_pub.py --pattern solid --color 255,0,0
"""

import argparse
import sys
import threading
import time

import numpy as np

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data, QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image
from builtin_interfaces.msg import Time


# ─── Image generators ─────────────────────────────────────────────────────────

def _make_gradient(width: int, height: int) -> np.ndarray:
    """Left-to-right hue sweep; camera zone boundaries are visually distinct."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    # 4 zones, each a different hue band
    zone_w = width // 4
    hues = [0, 60, 120, 200]   # red, yellow, green, blue (degrees)
    for i, h in enumerate(hues):
        x0 = i * zone_w
        x1 = x0 + zone_w
        # Convert HSV(h, 255, 200) -> RGB manually (avoid cv2 dependency at top-level)
        h_norm = h / 360.0
        r, g, b = _hsv_to_rgb(h_norm, 1.0, 0.78)
        img[:, x0:x1, 0] = int(r * 255)
        img[:, x0:x1, 1] = int(g * 255)
        img[:, x0:x1, 2] = int(b * 255)
        # Draw a thin white divider at the boundary
        if i > 0:
            img[:, x0:x0 + 2, :] = 255
    # Add frame counter stripe at the top (updated each call via caller)
    return img


def _hsv_to_rgb(h, s, v):
    if s == 0:
        return v, v, v
    i = int(h * 6)
    f = h * 6 - i
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    i %= 6
    return [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i]


def _make_checker(width: int, height: int, block: int) -> np.ndarray:
    img = np.zeros((height, width, 3), dtype=np.uint8)
    for r in range(0, height, block):
        for c in range(0, width, block):
            if ((r // block) + (c // block)) % 2 == 0:
                img[r:r + block, c:c + block] = 255
    return img


def _load_file(path: str, width: int, height: int) -> np.ndarray:
    try:
        import cv2
        raw = cv2.imread(path)
        if raw is None:
            raise FileNotFoundError(f"cv2.imread could not open: {path}")
        resized = cv2.resize(raw, (width, height))
        return cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    except ImportError:
        # Fall back to PIL if available
        try:
            from PIL import Image as PILImage
            pil = PILImage.open(path).convert("RGB").resize((width, height))
            return np.array(pil, dtype=np.uint8)
        except ImportError:
            print("[fake_image_pub] ERROR: neither cv2 nor PIL found; cannot load image file.")
            sys.exit(1)


# ─── ROS2 node ────────────────────────────────────────────────────────────────

class FakeImagePublisher(Node):
    def __init__(self, args):
        super().__init__("fake_image_pub")

        self.img_topic  = args.topic
        self.pps_topic  = args.pps
        self.rate_hz    = args.rate
        self.pps_rate   = args.pps_rate
        self.width      = args.width
        self.height     = args.height
        self.encoding   = args.encoding
        self.pattern    = args.pattern
        self.frame_id   = args.frame_id
        self.publish_pps = not args.no_pps
        self.block      = args.block

        self._frame_idx = 0

        # QoS mirroring stamp_and_split expectations
        img_qos = qos_profile_sensor_data
        pps_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

        self._img_pub = self.create_publisher(Image, self.img_topic, img_qos)
        if self.publish_pps:
            self._pps_pub = self.create_publisher(Time, self.pps_topic, pps_qos)

        # Pre-generate static frames
        self._static_frame = self._build_static_frame(args)
        self._base_gradient = _make_gradient(self.width, self.height)

        # Timers
        self.create_timer(1.0 / self.rate_hz, self._publish_image)
        if self.publish_pps:
            self.create_timer(1.0 / self.pps_rate, self._publish_pps)

        self.get_logger().info(
            f"fake_image_pub started\n"
            f"  image topic : {self.img_topic}\n"
            f"  image rate  : {self.rate_hz} Hz\n"
            f"  resolution  : {self.width}x{self.height}  encoding={self.encoding}\n"
            f"  pattern     : {self.pattern}\n"
            f"  pps topic   : {self.pps_topic if self.publish_pps else '(disabled)'}\n"
            f"  pps rate    : {self.pps_rate} Hz"
        )

    # ── frame builders ──────────────────────────────────────────────────────

    def _build_static_frame(self, args) -> np.ndarray | None:
        """Return a pre-built numpy array for static patterns (None for dynamic)."""
        if self.pattern == "solid":
            r, g, b = [int(x) for x in args.color.split(",")]
            frame = np.full((self.height, self.width, 3), [r, g, b], dtype=np.uint8)
            return frame
        elif self.pattern == "checker":
            return _make_checker(self.width, self.height, self.block)
        elif self.pattern == "file":
            if not args.file:
                self.get_logger().error("--pattern file requires --file PATH")
                sys.exit(1)
            return _load_file(args.file, self.width, self.height)
        return None  # gradient and noise are dynamic

    def _make_frame(self) -> np.ndarray:
        if self._static_frame is not None:
            return self._static_frame

        if self.pattern == "noise":
            return np.random.randint(0, 256, (self.height, self.width, 3), dtype=np.uint8)

        # gradient — overlay frame counter as a bright stripe
        frame = self._base_gradient.copy()
        bar_w = (self._frame_idx % self.width) + 1
        frame[self.height - 8 : self.height, :bar_w] = [255, 255, 255]
        return frame

    # ── publishers ──────────────────────────────────────────────────────────

    def _publish_image(self):
        frame = self._make_frame()
        self._frame_idx += 1

        msg = Image()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.frame_id
        msg.height = self.height
        msg.width = self.width
        msg.encoding = self.encoding
        msg.is_bigendian = False

        if self.encoding in ("rgb8", "bgr8"):
            msg.step = self.width * 3
            msg.data = frame.tobytes()
        elif self.encoding == "mono8":
            gray = frame[:, :, 0]  # cheap single-channel
            msg.step = self.width
            msg.data = gray.tobytes()
        elif self.encoding == "mono16":
            # Production cam0 publishes R16 (mono16). Promote to uint16.
            gray = frame[:, :, 0].astype(np.uint16) << 8
            msg.step = self.width * 2
            msg.data = gray.tobytes()
        elif self.encoding == "bayer_bggr16":
            # Production cam1 publishes SBGGR16. Build a synthetic Bayer mosaic
            # from the RGB frame so that debayer roundtrips to a recognizable
            # gradient. Pattern (BG/GR rows):
            #   row 0,2,...:  B  G  B  G ...
            #   row 1,3,...:  G  R  G  R ...
            bayer = np.empty((self.height, self.width), dtype=np.uint16)
            r16 = frame[:, :, 0].astype(np.uint16) << 8
            g16 = frame[:, :, 1].astype(np.uint16) << 8
            b16 = frame[:, :, 2].astype(np.uint16) << 8
            bayer[0::2, 0::2] = b16[0::2, 0::2]
            bayer[0::2, 1::2] = g16[0::2, 1::2]
            bayer[1::2, 0::2] = g16[1::2, 0::2]
            bayer[1::2, 1::2] = r16[1::2, 1::2]
            msg.step = self.width * 2
            msg.data = bayer.tobytes()
        else:
            # Fallback: raw bytes as-is
            msg.step = self.width * 3
            msg.data = frame.tobytes()

        self._img_pub.publish(msg)

    def _publish_pps(self):
        msg = self.get_clock().now().to_msg()
        self._pps_pub.publish(msg)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Publish fake images into the payload camera ROS2 pipeline."
    )
    parser.add_argument("--topic",    default="/cam0/camera_node/image_raw")
    parser.add_argument("--pps",      default="/pps/time")
    parser.add_argument("--rate",     type=float, default=10.0)
    parser.add_argument("--pps-rate", type=float, default=1.0, dest="pps_rate")
    parser.add_argument("--width",    type=int,   default=5120)
    parser.add_argument("--height",   type=int,   default=800)
    parser.add_argument("--encoding", default="rgb8",
                        choices=["rgb8", "bgr8", "mono8", "mono16", "bayer_bggr16"])
    parser.add_argument("--pattern",  default="gradient",
                        choices=["solid", "gradient", "noise", "checker", "file"])
    parser.add_argument("--color",    default="128,128,128",
                        help="R,G,B for solid pattern (default: 128,128,128)")
    parser.add_argument("--block",    type=int, default=64,
                        help="Checker block size in pixels (default: 64)")
    parser.add_argument("--file",     default=None,
                        help="Path to image file for --pattern file")
    parser.add_argument("--no-pps",   action="store_true",
                        help="Disable PPS publishing (frames will be dropped by require_pps nodes)")
    parser.add_argument("--frame-id", default="camera", dest="frame_id")

    # Parse only the args we own; let rclpy take the rest
    args, ros_args = parser.parse_known_args()

    rclpy.init(args=ros_args if ros_args else None)
    node = FakeImagePublisher(args)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except rclpy.executors.ExternalShutdownException:
        import logging
        logging.getLogger(__name__).warning(
            "rclpy context shut down externally (e.g. SIGTERM) — exiting cleanly"
        )
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except rclpy._rclpy_pybind11.RCLError as e:
            if "rcl_shutdown already called" in str(e):
                import logging
                logging.getLogger(__name__).warning(
                    "rclpy context was already shut down before explicit shutdown call"
                )
            else:
                raise


if __name__ == "__main__":
    main()
