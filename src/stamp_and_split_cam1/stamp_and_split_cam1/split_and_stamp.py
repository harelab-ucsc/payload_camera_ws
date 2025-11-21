#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image


class SplitAndStampNode(Node):
    def __init__(self):
        super().__init__('split_and_stamp_node')

        # Parameters
        self.declare_parameter('input_topic', '/cam0/camera/image_raw')
        self.declare_parameter(
            'output_topics',
            ['/cam0/camera/image_raw_0',
             '/cam0/camera/image_raw_1',
             '/cam0/camera/image_raw_2',
             '/cam0/camera/image_raw_3']
        )
        self.declare_parameter('num_slices', 4)

        input_topic = self.get_parameter('input_topic').get_parameter_value().string_value
        output_topics_param = self.get_parameter('output_topics').get_parameter_value().string_array_value
        self.num_slices = self.get_parameter('num_slices').get_parameter_value().integer_value

        if len(output_topics_param) < self.num_slices:
            self.get_logger().warn(
                f"output_topics length ({len(output_topics_param)}) "
                f"< num_slices ({self.num_slices}), trimming num_slices"
            )
            self.num_slices = len(output_topics_param)

        self.output_topics = list(output_topics_param)[:self.num_slices]

        # Subscriber and publishers
        self.subscription = self.create_subscription(
            Image,
            input_topic,
            self.image_callback,
            10
        )

        self.slice_publishers = [
            self.create_publisher(Image, topic, 10)
            for topic in self.output_topics
        ]

        self.get_logger().info(
            f"Splitting '{input_topic}' into {self.num_slices} slices -> {self.output_topics}"
        )

    def image_callback(self, msg: Image):
        width = msg.width
        height = msg.height
        step = msg.step   # bytes per row
        data = msg.data   # bytes

        if width == 0 or height == 0 or step == 0:
            self.get_logger().warn("Received empty image")
            return

        # assume tightly-packed image: step = width * bytes_per_pixel
        if step % width != 0:
            self.get_logger().error(
                f"step ({step}) is not divisible by width ({width}); "
                "cannot safely split without cv_bridge"
            )
            return

        bytes_per_pixel = step // width
        slice_width = width // self.num_slices

        if slice_width == 0:
            self.get_logger().error("slice_width computed as 0")
            return

        new_step = slice_width * bytes_per_pixel
        total_rows = height

        # Convert to bytes once
        if isinstance(data, bytearray):
            src = data
        else:
            src = bytes(data)

        for i in range(self.num_slices):
            # Create a buffer for the slice: height * new_step bytes
            slice_buf = bytearray(total_rows * new_step)

            for row in range(total_rows):
                src_row_start = row * step
                # offset for this slice in the row
                src_slice_start = src_row_start + i * slice_width * bytes_per_pixel
                src_slice_end = src_slice_start + new_step

                dst_row_start = row * new_step
                slice_buf[dst_row_start:dst_row_start + new_step] = src[src_slice_start:src_slice_end]

            # Build new Image message
            out_msg = Image()
            out_msg.header.stamp = msg.header.stamp  # keep original capture time
            out_msg.header.frame_id = f"{msg.header.frame_id}_slice_{i}"

            out_msg.height = height
            out_msg.width = slice_width
            out_msg.encoding = msg.encoding
            out_msg.is_bigendian = msg.is_bigendian
            out_msg.step = new_step
            out_msg.data = bytes(slice_buf)

            self.slice_publishers[i].publish(out_msg)


def main(args=None):
    rclpy.init(args=args)
    node = SplitAndStampNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()


