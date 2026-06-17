#!/usr/bin/env python3
import pdb
import rclpy
import cv2
import os
import json
import yaml
import copy
import time
import argparse

import numpy as np

from cv_bridge import CvBridge
from rclpy.node import Node
from rosbag2_py import SequentialReader, SequentialWriter, StorageOptions, ConverterOptions
from sensor_msgs.msg import Image
from rosidl_runtime_py.utilities import get_message
from rclpy.serialization import deserialize_message, serialize_message
from scipy.spatial.transform import Rotation as R
from pyproj import Proj, Transformer


class BagProcessor:
    def __init__(
        self,
        input_bag_path,     # Path to the input ROS2 bag file
        output_bag_path,    # Path to the output ROS2 bag file
        ds_dir,             # Path to the directory to save images/poses.json
        image_topic,        # Image topic name (e.g., /camera/image_raw)
        index,              # Image subframe index, from CamarrayHAT
        intrinsics_path,    # Path to the YAML file with camera intrinsics
        rectify,            # Whether or not to rectify in vi_time_sync.py (default: True)
        save,               # Whether or not to save imagery (default: False)
    ):
        self.input_bag_path = input_bag_path
        self.output_bag_path = output_bag_path
        self.image_topic = image_topic
        self.ds_dir = ds_dir
        self.br = CvBridge()

        self.fps = None
        self.index = index
        self.image_msgs = []

        self.save = save
        self.rectify = rectify
        if self.rectify:
            self.intrinsics = self.load_intrinsics(intrinsics_path)
            self.K = np.array([[self.intrinsics["fx"], 0, self.intrinsics["cx"]],
                          [0, self.intrinsics["fy"], self.intrinsics["cy"]],
                          [0, 0, 1]])
            self.D = np.array([self.intrinsics["k1"], self.intrinsics["k2"], self.intrinsics["r1"], self.intrinsics["r2"]])
            self.width = self.intrinsics["resx"]
            self.height = self.intrinsics["resy"]
            self.map1, self.map2 = cv2.initUndistortRectifyMap(self.K, self.D, None, self.K, (self.width, self.height), cv2.CV_32FC1)

    def process_bag(self):
        start = time.time()

        # Initialize reader and writer
        reader = SequentialReader()
        writer = SequentialWriter()
        try:
            storage_options = StorageOptions(uri=self.input_bag_path, storage_id="mcap")
            converter_options = ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr")
            reader.open(storage_options, converter_options)
        except RuntimeError:
            storage_options = StorageOptions(uri=self.input_bag_path, storage_id="sqlite3")
            converter_options = ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr")
            reader.open(storage_options, converter_options)
        writer.open(StorageOptions(uri=self.output_bag_path, storage_id="mcap"), converter_options)

        topics_and_types = reader.get_all_topics_and_types()

        topic_type_map = {t.name:t.type for t in topics_and_types}
        # Register all topics with the writer
        for topic in topics_and_types:
            writer.create_topic(topic)

        if self.save:
            os.makedirs("images", exist_ok=True)  # Ensure output directories exist

        print('[PROC]    Reading bag')
        imgs = 0
        # Read and process messages
        while reader.has_next():
            topic, data, timestamp = reader.read_next()
            message_type = get_message(topic_type_map[topic])
            msg = deserialize_message(data, message_type)

            if topic == self.image_topic:
                self.image_msgs.append(msg)
            else:
                # Copy all other topics as-is
                writer.write(topic, data, timestamp)
        print(f'[PROC]      image_msgs length: {len(self.image_msgs)}')
        print('[PROC]    Bag read done \n')

        for i, image_msg in enumerate(self.image_msgs):
            if not i % self.rate:
                stamp, ts_float, ts_int = self.get_timestamp(image_msg)
                updated_image = self.get_subframe(image_msg)

                if self.rectify:
                    updated_image = self.rectify_image(updated_image)

                if self.save:
                    timestamp_str = f"{stamp.sec}.{stamp.nanosec:09d}"
                    self.save_image(updated_image, timestamp_str)

                new_image = serialize_message(updated_image)
                writer.write(self.image_topic, new_image, ts_int)

        writer.close()
        print(f'\n  --> time elapsed: {time.time()-start}')

    def get_timestamp(self, msg):
        ts = msg.header.stamp
        ts_float = ts.sec + ts.nanosec*1e-9
        ts_int = int(ts.sec*1e9 + ts.nanosec)
        return msg.header.stamp, ts_float, ts_int

    def get_subframe(self, image_msg):
        cv_image = self.br.imgmsg_to_cv2(
            image_msg, desired_encoding='passthrough'
        )
        w = image_msg.width//4
        cropped = cv_image[:, w*(self.index-1):w*self.index]
        new_image = self.br.cv2_to_imgmsg(
            cropped,
            encoding=image_msg.encoding
        )
        new_image.header = image_msg.header
        return new_image

    def pack_image_into_msg(self, data, image_msg):
        new_image = Image()
        new_image.header = image_msg.header

        new_image.height = data.shape[0]
        new_image.width = data.shape[1]

        new_image.encoding = image_msg.encoding
        new_image.is_bigendian = image_msg.is_bigendian

        new_image.data = data.tobytes()

        bytes_per_pixel = data.dtype.itemsize
        if len(data.shape) == 3:
            bytes_per_pixel *= data.shape[2]

        new_image.step = data.shape[1] * bytes_per_pixel

        return new_image

    def save_image(self, image_msg, timestamp_str):
        """Save the image message as a PNG file."""
        img_data = np.frombuffer(image_msg.data, dtype=np.uint8).reshape(image_msg.height, image_msg.width, -1)
        savename = os.path.join(self.ds_dir, 'images')
        if not os.path.isdir(savename):
            print(f'  Making Save Directory: {savename}')
            os.makedirs(savename, exist_ok=True)

        savename = os.path.join(savename, f"{timestamp_str}.png")
        print(f"[PROC]    Saving Image To: {savename}")
        cv2.imwrite(savename, img_data)

    def rectify_image(self, raw_image):
        # Convert raw image message to OpenCV image
        cv_image = self.br.imgmsg_to_cv2(
            raw_image, desired_encoding='passthrough'
        )

        # Rectify the image using the maps
        rectified_image = cv2.remap(
            cv_image, self.map1, self.map2, interpolation=cv2.INTER_LINEAR
        )

        # Convert the rectified image back to ROS Image message
        rectified_img_msg = self.br.cv2_to_imgmsg(
            rectified_image, encoding='passthrough'
        )
        rectified_img_msg.header = raw_image.header

        return rectified_img_msg


def main():
    parser = argparse.ArgumentParser(description="Fix image timestamps in a ROS2 bag file using INS messages.")
    parser.add_argument("input_bag", help="Path to the input ROS2 bag file")
    parser.add_argument("output_bag", help="Path to the output ROS2 bag file")
    parser.add_argument("ds_dir",  help="Path to the directory to save images")
    parser.add_argument("image_topic", help="Image topic name (e.g., /camera/image_raw)")
    parser.add_argument("index", type=int, help="Image subframe index, from CamarrayHAT")
    parser.add_argument("intrinsics", help="Path to the YAML file with camera intrinsics")
    parser.add_argument("-r", "--rectify", action="store_false", help="Whether or not to rectify in vi_time_sync.py (default: True)")
    parser.add_argument("-s", "--save", action="store_true", help="Whether or not to save imagery (default: False)")

    args = parser.parse_args()

    rclpy.init()

    processor = BagProcessor(
        args.input_bag,
        args.output_bag,
        args.ds_dir,
        args.image_topic,
        args.index,
        args.intrinsics,
        args.rectify,
        args.save
    )
    processor.process_bag()

    rclpy.shutdown()


if __name__ == "__main__":
    main()
