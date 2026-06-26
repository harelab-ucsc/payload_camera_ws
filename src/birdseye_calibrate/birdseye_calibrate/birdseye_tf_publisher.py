#!/usr/bin/env python3

import yaml
import numpy as np

import rclpy
from rclpy.node import Node

from tf2_ros.static_transform_broadcaster import StaticTransformBroadcaster
from geometry_msgs.msg import TransformStamped
from tf2_ros import TransformBroadcaster
from nav_msgs.msg import Odometry

from scipy.spatial.transform import Rotation


class BirdsEyeTfPublisher(Node):

    def __init__(self):
        super().__init__("birdseye_tf_pub")

        self.declare_parameter("calibration_file", "")

        calib_file = (
            self.get_parameter("calibration_file")
            .get_parameter_value()
            .string_value
        )

        if not calib_file:
            raise RuntimeError("No calibration_file parameter supplied")

        with open(calib_file, "r") as f:
            self.calib = yaml.safe_load(f)

        self.static_broadcaster = StaticTransformBroadcaster(self)
        self.dynamic_broadcaster = TransformBroadcaster(self)

        self.create_subscription(
            Odometry,
            "/ins/odom",
            self.odom_callback,
            10
        )

        self.world_frame = self.calib["world_frame"]
        self.body_frame = self.calib["body_frame"]

        transforms = []

        # Publish INS -> camera transforms
        for cam_name, cam_cfg in self.calib["cameras"].items():

            T = np.array(cam_cfg["T_cam_ins"], dtype=float)

            R = T[:3, :3]
            t = T[:3, 3]

            q = Rotation.from_matrix(R).as_quat()

            msg = TransformStamped()

            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = self.body_frame
            msg.child_frame_id = cam_name

            msg.transform.translation.x = float(t[0])
            msg.transform.translation.y = float(t[1])
            msg.transform.translation.z = float(t[2])

            msg.transform.rotation.x = float(q[0])
            msg.transform.rotation.y = float(q[1])
            msg.transform.rotation.z = float(q[2])
            msg.transform.rotation.w = float(q[3])

            transforms.append(msg)

            # camera -> optical frame
            optical = TransformStamped()

            optical.header.stamp = msg.header.stamp
            optical.header.frame_id = cam_name
            optical.child_frame_id = f"{cam_name}_optical"

            optical.transform.translation.x = 0.0
            optical.transform.translation.y = 0.0
            optical.transform.translation.z = 0.0

            # ROS camera_link -> optical frame
            R_optical = np.array(
                [
                    [0.0, -1.0, 0.0],
                    [0.0, 0.0, -1.0],
                    [1.0, 0.0, 0.0],
                ]
            )

            q_opt = Rotation.from_matrix(R_optical).as_quat()

            optical.transform.rotation.x = float(q_opt[0])
            optical.transform.rotation.y = float(q_opt[1])
            optical.transform.rotation.z = float(q_opt[2])
            optical.transform.rotation.w = float(q_opt[3])

            transforms.append(optical)

        self.static_broadcaster.sendTransform(transforms)

        self.get_logger().info(
            f"Published {len(transforms)} static transforms"
        )

    def odom_callback(self, msg: Odometry):
        tf = TransformStamped()
        tf.header.stamp = msg.header.stamp
        tf.header.frame_id = self.world_frame
        tf.child_frame_id = self.body_frame
        tf.transform.translation.x = msg.pose.pose.position.y
        tf.transform.translation.y = msg.pose.pose.position.x
        tf.transform.translation.z = -msg.pose.pose.position.z
        tf.transform.rotation = msg.pose.pose.orientation
        self.dynamic_broadcaster.sendTransform(tf)


def main():
    rclpy.init()

    node = BirdsEyeTfPublisher()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
