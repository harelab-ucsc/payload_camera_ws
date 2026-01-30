#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class SpectralBridge(Node):
    """
    Subscribes to /as7265x/at_raw (String: "v0, v1, ... v17")
    Publishes selected band values as String topics inside this node's namespace:
      red, green, nir, red_edge
    """

    def __init__(self):
        super().__init__('spectral_bridge')

        self.declare_parameter('in_topic', '/as7265x/at_raw')
        self.declare_parameter('band_map', {
            'red': 0,
            'green': 6,
            'nir': 14,
            'red_edge': 12,
        })

        in_topic = self.get_parameter('in_topic').value
        self.band_map = self.get_parameter('band_map').value  # dict

        self.sub = self.create_subscription(String, in_topic, self.cb, 10)

        self.pubs = {name: self.create_publisher(String, name, 10) for name in self.band_map.keys()}

        self.get_logger().info(f"Listening on {in_topic}")
        self.get_logger().info(f"Publishing bands: {self.band_map}")

    def cb(self, msg: String):
        parts = [p.strip() for p in msg.data.split(',')]
        if len(parts) < 18:
            return

        try:
            vals = [float(p) for p in parts[:18]]
        except ValueError:
            return

        for name, idx in self.band_map.items():
            idx = int(idx)
            if 0 <= idx < len(vals):
                out = String()
                out.data = str(vals[idx])
                self.pubs[name].publish(out)

def main():
    rclpy.init()
    node = SpectralBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()
