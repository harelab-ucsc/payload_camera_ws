#!/usr/bin/env python3
"""
fake_sync_inputs.py

Publishes the non-image sensor inputs that SyncNode requires so its
all_caught() state machine fires in test environments without real hardware.

In Docker the inertial_sense_ros2 (DIDINS2) and custom_msgs (AltSNR) packages
are not installed; SyncNode skips those subscriptions and only requires
AS7265xCal (plus cam0/cam1/PPS). This script publishes that one topic.

If DIDINS2 / AltSNR ever become available in the environment, the matching
publishers in this script light up automatically.

Usage:
  python3 fake_sync_inputs.py [--rate HZ]
"""

import argparse

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

reliable_qos = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    history=HistoryPolicy.KEEP_LAST,
    depth=10,
)

try:
    from as7265x_at_msgs.msg import AS7265xCal
except ImportError:
    AS7265xCal = None

try:
    from inertial_sense_ros2.msg import DIDINS2
except ImportError:
    DIDINS2 = None

try:
    from custom_msgs.msg import AltSNR
except ImportError:
    AltSNR = None


class FakeSyncInputs(Node):
    def __init__(self, rate_hz: float):
        super().__init__("fake_sync_inputs")

        period = 1.0 / rate_hz
        published = []

        if AS7265xCal is not None:
            self._spec_pub = self.create_publisher(
                AS7265xCal, "as7265x/calibrated_values", reliable_qos
            )
            self.create_timer(period, self._publish_spec)
            published.append("as7265x/calibrated_values")
        else:
            self.get_logger().warn("as7265x_at_msgs not available — spec publisher disabled")

        if DIDINS2 is not None:
            self._ins_pub = self.create_publisher(DIDINS2, "/ins_quat_uvw_lla", reliable_qos)
            self.create_timer(period, self._publish_ins)
            published.append("/ins_quat_uvw_lla")
        if AltSNR is not None:
            self._alt_pub = self.create_publisher(AltSNR, "/rad_altitude", reliable_qos)
            self.create_timer(period, self._publish_radalt)
            published.append("/rad_altitude")

        self.get_logger().info(
            f"fake_sync_inputs publishing at {rate_hz} Hz on: {', '.join(published) or '(nothing)'}"
        )

    def _publish_spec(self):
        msg = AS7265xCal()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "spec"
        # Non-zero at the four CAM0_ALIGNMENT indices (0, 2, 9, 14) so cam0
        # spectral correction divides by a real number rather than identity.
        vals = [0.0] * 18
        vals[0]  = 100.0  # 410 nm — slice 0 (BP340_UV)
        vals[2]  = 110.0  # 460 nm — slice 1 (BP450_Blue)
        vals[9]  = 120.0  # 705 nm — slice 2 (BP695_Red)
        vals[14] = 130.0  # 730 nm — slice 3 (BP735_Edge)
        msg.values = vals
        self._spec_pub.publish(msg)

    def _publish_ins(self):
        msg = DIDINS2()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "ins"
        # SyncNode.ins_cb requires hdw_status & 0x20 (HDW_STROBE) to latch.
        msg.hdw_status = 0x00000020
        msg.ins_status = 0x00040000  # nominal solution bits
        msg.lla = [36.9741, -122.0308, 100.0]
        msg.qn2b = [1.0, 0.0, 0.0, 0.0]  # identity quat (scalar-first NED)
        self._ins_pub.publish(msg)

    def _publish_radalt(self):
        msg = AltSNR()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "radalt"
        msg.altitude = 50.0
        msg.snr = 30  # > 13 so radalt_cb latches
        self._alt_pub.publish(msg)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rate", type=float, default=10.0)
    args, ros_args = parser.parse_known_args()

    rclpy.init(args=ros_args if ros_args else None)
    node = FakeSyncInputs(args.rate)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    main()
