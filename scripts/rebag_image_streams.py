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
from rosbag2_py import SequentialReader, SequentialWriter, StorageOptions, ConverterOptions, TopicMetadata
from sensor_msgs.msg import Image, CameraInfo
from rosidl_runtime_py.utilities import get_message
from rclpy.serialization import deserialize_message, serialize_message
from scipy.spatial.transform import Rotation as R
from pyproj import Proj, Transformer


class RigCalibration:

    def __init__(self, yaml_path):
        with open(yaml_path, "r") as f:
            self.data = yaml.safe_load(f)

    def get_camera_info(self, cam_name):
        cam = self.data["cameras"][cam_name]

        intr = cam["intrinsics"]
        dist = cam["distortion"]
        res  = cam["resolution"]

        K = np.array([
            [intr["fx"], 0.0, intr["cx"]],
            [0.0, intr["fy"], intr["cy"]],
            [0.0, 0.0, 1.0]
        ], dtype=np.float64)

        D = np.array([
            dist["k1"],
            dist["k2"],
            dist["p1"],
            dist["p2"],
            dist.get("k3", 0.0)
        ], dtype=np.float64)

        return {
            "K": K,
            "D": D,
            "width": res["width"],
            "height": res["height"]
        }


class BagProcessor:
    def __init__(
        self,
        input_bag_path,     # Path to the input ROS2 bag file
        output_bag_path,    # Path to the output ROS2 bag file
        ds_dir,             # Path to the directory to save images/poses.json
        image_topic,        # Image topic name (e.g., /camera/image_raw)
        rate,
        ind,                # Image subframe index/indices, from CamarrayHAT
        calibration_path,    # Path to the YAML file with camera intrinsics
        rectify,            # Whether or not to rectify in vi_time_sync.py (default: True)
        save,               # Whether or not to save imagery (default: False)
    ):
        self.input_bag_path = input_bag_path
        self.output_bag_path = output_bag_path
        self.image_topic = image_topic
        self.ds_dir = ds_dir
        self.br = CvBridge()

        self.rate = rate
        self.ind = ind
        self.image_msgs = []

        self.save = save

        self.rectify = rectify

        self.calib = RigCalibration(calibration_path)
        self.camera_models = {}
        for sensor in ["rgb", "multispec"]:
            for ind in [1,2,3,4]:

                cam_name = f"{sensor}_{ind}"

                cam = self.calib.get_camera_info(cam_name)

                map1, map2 = cv2.initUndistortRectifyMap(
                    cam["K"],
                    cam["D"],
                    None,
                    cam["K"],
                    (cam["width"], cam["height"]),
                    cv2.CV_32FC1
                )

                self.camera_models[cam_name] = {
                    "cam": cam,
                    "map1": map1,
                    "map2": map2,
                }

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
            if topic.name != self.image_topic:
                writer.create_topic(topic)

        for ind in self.ind:
            # create subframe image topics
            writer.create_topic(
                TopicMetadata(
                    name=f"/cam{ind}/camera/image_raw",
                    type="sensor_msgs/msg/Image",
                    serialization_format="cdr"
                )
            )
            # create subframe camera_info topics
            writer.create_topic(
                TopicMetadata(
                    name=f"/cam{ind}/camera/camera_info",
                    type="sensor_msgs/msg/CameraInfo",
                    serialization_format="cdr"
                )
            )

        print('[PROC]    Reading bag')
        # Read and process messages
        i = 0
        while reader.has_next():
            topic, data, timestamp = reader.read_next()
            message_type = get_message(topic_type_map[topic])
            msg = deserialize_message(data, message_type)

            if topic == self.image_topic:
                if not i % self.rate:
                    self.image_msgs.append(msg)
                else:
                    pass
                i += 1
            else:
                # Copy all other topics as-is
                writer.write(topic, data, timestamp)
        print(f'[PROC]      image_msgs length: {len(self.image_msgs)}')
        print('[PROC]    Bag read done \n')

        for image_msg in self.image_msgs:
            stamp, ts_float, ts_int = self.get_timestamp(image_msg)
            for ind in self.ind:
                if "mono" in image_msg.encoding:
                    cam_name = f"multispec_{ind}"
                else:
                    cam_name = f"rgb_{ind}"

                # load camera parameters from memory
                model = self.camera_models[cam_name]
                cam = model["cam"]
                self.map1 = model["map1"]
                self.map2 = model["map2"]

                updated_image = self.get_subframe(ind, image_msg)
                cam_info = self.make_camera_info(cam, cam_name, image_msg)

                if self.rectify:
                    updated_image = self.rectify_image(updated_image)

                if self.save:
                    timestamp_str = f"{stamp.sec}.{stamp.nanosec:09d}"
                    self.save_image(updated_image, cam_name, timestamp_str)

                updated_image = serialize_message(updated_image)
                writer.write(
                    f"/cam{ind}/camera/image_raw",
                    updated_image,
                    ts_int
                )
                cam_info = serialize_message(cam_info)
                writer.write(
                    f"/cam{ind}/camera/camera_info",
                    cam_info,
                    ts_int
                )

        writer.close()
        print(f'\n  --> time elapsed: {time.time()-start}')

    def get_timestamp(self, msg):
        ts = msg.header.stamp
        ts_float = ts.sec + ts.nanosec*1e-9
        ts_int = int(ts.sec*1e9 + ts.nanosec)
        return msg.header.stamp, ts_float, ts_int

    def get_subframe(self, ind, image_msg):
        cv_image = self.br.imgmsg_to_cv2(
            image_msg, desired_encoding='passthrough'
        )
        w = image_msg.width//4
        cropped = cv_image[:, w*(ind-1):w*ind]
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

    def make_camera_info(self, cam, cam_name, image_msg):
        msg = CameraInfo()

        msg.width = cam["width"]
        msg.height = cam["height"]
        msg.k = cam["K"].flatten().tolist()
        msg.d = cam["D"].tolist()
        msg.distortion_model = "plumb_bob"
        msg.r = [1.0, 0.0, 0.0,
                 0.0, 1.0, 0.0,
                 0.0, 0.0, 1.0]
        msg.p = [cam["K"][0,0], 0, cam["K"][0,2], 0,
                 0, cam["K"][1,1], cam["K"][1,2], 0,
                 0, 0, 1, 0]
        msg.header.frame_id = f"{cam_name}_optical"
        msg.header.stamp = image_msg.header.stamp
        return msg

    def save_image(self, image_msg, prefix, timestamp_str):
        """Save the image message as a PNG file."""
        img_data = self.br.imgmsg_to_cv2(
            image_msg,
            desired_encoding='passthrough'
        )
        savename = os.path.join(self.ds_dir, 'images')
        if not os.path.isdir(savename):
            print(f'  Making Save Directory: {savename}')
            os.makedirs(savename, exist_ok=True)

        savename = os.path.join(savename, f'{prefix}_{timestamp_str}.png')
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
    parser.add_argument("--calibration", default=None, help="Path to the YAML file with camera calibration data")
    parser.add_argument("--rate", type=int, default=1, help="Optional integer rate for frame subsampling.")
    parser.add_argument("--ind", type=int, nargs='+', help="Image subframe index or indices, from CamarrayHAT")
    parser.add_argument("--no-rectify", action="store_false", dest="rectify", help="Whether or not to rectify in vi_time_sync.py (default: True)")
    parser.add_argument("--save", action="store_true", help="Whether or not to save imagery (default: False)")

    args = parser.parse_args()

    rclpy.init()

    processor = BagProcessor(
        args.input_bag,
        args.output_bag,
        args.ds_dir,
        args.image_topic,
        args.rate,
        args.ind,
        args.calibration,
        args.rectify,
        args.save
    )
    processor.process_bag()

    rclpy.shutdown()


if __name__ == "__main__":
    main()
