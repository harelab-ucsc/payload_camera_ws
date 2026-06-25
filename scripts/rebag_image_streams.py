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
import utm

import numpy as np

from cv_bridge import CvBridge
from rclpy.node import Node
from rosbag2_py import SequentialReader, SequentialWriter, StorageOptions, ConverterOptions, TopicMetadata
from sensor_msgs.msg import Image, CameraInfo
from rosidl_runtime_py.utilities import get_message
from rclpy.serialization import deserialize_message, serialize_message
from scipy.spatial.transform import Rotation as R
from pyproj import Proj, Transformer


BITMASK_STROBE_IN = 0x00000020


class RigCalibration:

    def __init__(self, yaml_path):
        with open(yaml_path, "r") as f:
            self.data = yaml.safe_load(f)

    def get_camera_info(self, cam_name):
        cam = self.data["cameras"][cam_name]

        intr = cam["intrinsics"]
        dist = cam["distortion"]
        res  = cam["resolution"]
        T_cam_ins = cam["T_cam_ins"]

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
            "T_cam_ins": T_cam_ins,
            "width": res["width"],
            "height": res["height"]
        }


class BagProcessor:
    def __init__(
        self,
        input_bag_path,     # Path to the input ROS2 bag file
        output_bag_path,    # Path to the output ROS2 bag file
        ds_dir,             # Path to the directory to save images/transforms.json
        image_topic,        # Image topic name (e.g., /camera/image_raw)
        ins_topic,          # INS topic name (e.g. /ins_quat_uvw_lla)
        rate,
        ind,                # Image subframe index/indices, from CamarrayHAT
        calibration_path,   # Path to a YAML file with camera calibration data
        rectify,            # Whether or not to rectify in vi_time_sync.py (default: True)
        save,               # Whether or not to save imagery (default: True)
        rebag,              # Whether or not ro rebag the ROS2 data (default: True)
    ):
        self.input_bag_path = input_bag_path
        self.output_bag_path = output_bag_path
        self.image_topic = image_topic
        self.ins_topic = ins_topic
        self.ds_dir = ds_dir
        self.br = CvBridge()

        self.rate = rate
        self.ind = ind
        self.image_msgs = []
        self.ins_msgs = []
        self.ins_times = None
        self.frames = []
        self.frames_by_timestamp = {}
        self.camera_ids = {}
        self.image_filenames = {}
        self.image_id = 0

        self.save = save
        self.rebag = rebag
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

        # Initialize reader and optional writer
        reader = SequentialReader()
        try:
            storage_options = StorageOptions(uri=self.input_bag_path, storage_id="mcap")
            converter_options = ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr")
            reader.open(storage_options, converter_options)
        except RuntimeError:
            storage_options = StorageOptions(uri=self.input_bag_path, storage_id="sqlite3")
            converter_options = ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr")
            reader.open(storage_options, converter_options)
        writer = None
        if self.rebag:
            writer = SequentialWriter()
            writer.open(StorageOptions(uri=self.output_bag_path, storage_id="mcap"), converter_options)

        topics_and_types = reader.get_all_topics_and_types()

        topic_type_map = {t.name:t.type for t in topics_and_types}
        if self.rebag:
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
        j = 0
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
                print(f"[PROC]        {i} images, {j} INS poses", end="\r")
            elif topic == self.ins_topic:
                if msg.hdw_status & BITMASK_STROBE_IN == BITMASK_STROBE_IN:
                    if not j % self.rate:
                        self.ins_msgs.append(msg)
                    else:
                        pass
                    j += 1
                    print(f"[PROC]        {i} images, {j} INS poses", end="\r")
            else:
                # Copy all other topics as-is
                if self.rebag:
                    writer.write(topic, data, timestamp)
        print()
        self.ins_times = np.array([
            msg.header.stamp.sec +
            msg.header.stamp.nanosec * 1e-9
            for msg in self.ins_msgs
        ])

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
                ins_msg = self.find_closest_ins(stamp, max_age=0.1)

                if ins_msg is None:
                    print(
                        f"[PROC] [WARN]    No INS solution within 0.1s of image\n"
                        f"[PROC] [WARN]        {cam_name}_{stamp.sec}.{stamp.nanosec}"
                    )
                    continue

                if self.rectify:
                    updated_image = self.rectify_image(updated_image)

                if self.save:
                    timestamp_str = f"{stamp.sec}.{stamp.nanosec:09d}"
                    self.save_image(updated_image, cam_name, timestamp_str)
                    self.append_pose_to_json(ins_msg, image_msg, cam_name, timestamp_str)

                if self.rebag:
                    updated_image = serialize_message(updated_image)
                    writer.write(
                        f"/cam{ind}/camera/image_raw",
                        updated_image,
                        ts_int
                    )
                    # the following cam_info is wrong if `rectify` is `True`
                    cam_info = serialize_message(cam_info)
                    writer.write(
                        f"/cam{ind}/camera/camera_info",
                        cam_info,
                        ts_int
                    )
                    ins_msgs = serialize_message(ins_msg)
                    writer.write(
                        f"/ins_quat_uvw_lla",
                        ins_msg,
                        ts_int
                    )
        if self.rebag:
            writer.close()
        self.save_json()
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

    def find_closest_ins(self, stamp, max_age=0.05):
        """
        Find nearest INS message.

        Parameters
        ----------
        stamp : builtin_interfaces.msg.Time
            Image timestamp

        max_age : float
            Maximum allowable separation in seconds

        Returns
        -------
        DIDINS2 | None
        """
        if len(self.ins_msgs) == 0:
            return None

        t = stamp.sec + stamp.nanosec * 1e-9
        idx = np.argmin(np.abs(self.ins_times - t))
        dt = abs(self.ins_times[idx] - t)
        if dt > max_age:
            return None

        # prune old messages
        prune_idx = max(0, idx - 1)
        if prune_idx > 0:
            self.ins_msgs = self.ins_msgs[prune_idx:]
            self.ins_times = self.ins_times[prune_idx:]
        return self.ins_msgs[idx - prune_idx]

    def save_image(self, image_msg, prefix, timestamp_str):
        """Save the image message as a PNG file."""
        img_data = self.br.imgmsg_to_cv2(
            image_msg,
            desired_encoding='passthrough'
        )
        savename = os.path.join(self.ds_dir, 'images', prefix)
        if not os.path.isdir(savename):
            print(f'[PROC]    Making Save Directory: {savename}')
            os.makedirs(savename, exist_ok=True)

        savename = os.path.join(savename, self.get_image_filename(timestamp_str))
        print(f"[PROC]    Saving Image To: {savename}")
        cv2.imwrite(savename, img_data)

    def get_image_filename(self, timestamp_str):
        """Return a stable image filename for one grouped rig capture."""
        if timestamp_str not in self.image_filenames:
            image_number = len(self.image_filenames) + 1
            self.image_filenames[timestamp_str] = f"image{image_number:04d}.png"
        return self.image_filenames[timestamp_str]

    def get_camera_id(self, cam_name):
        """Return a stable COLMAP sensor ID for the camera."""
        if cam_name not in self.camera_ids:
            self.camera_ids[cam_name] = len(self.camera_ids) + 1
        return self.camera_ids[cam_name]

    def rotation_to_quat_wxyz(self, rot):
        """Convert a rotation matrix to a COLMAP-order quaternion."""
        quat_xyzw = R.from_matrix(rot).as_quat()
        return [
            quat_xyzw[3],
            quat_xyzw[0],
            quat_xyzw[1],
            quat_xyzw[2],
        ]

    def colmap_camera_config(self, cam_name):
        """Build one COLMAP rig_config camera entry."""
        cam_id = self.get_camera_id(cam_name)
        cam = self.camera_models[cam_name]["cam"]
        config = {
            "image_prefix": f"{cam_name}/",
            "camera_model_name": "PINHOLE",
            "camera_params": [
                cam["K"][0,0],
                cam["K"][1,1],
                cam["K"][0,2],
                cam["K"][1,2],
            ],
        }

        ref_cam_name = next(iter(self.camera_ids))
        if cam_name == ref_cam_name:
            config["ref_sensor"] = True
            return config

        T_cam_ins = np.array(cam["T_cam_ins"])
        ref_cam = self.camera_models[ref_cam_name]["cam"]
        T_ref_ins = np.array(ref_cam["T_cam_ins"])
        T_cam_ref = np.linalg.inv(T_ref_ins) @ T_cam_ins

        config["cam_from_rig_rotation"] = self.rotation_to_quat_wxyz(
            T_cam_ref[:3,:3]
        )
        config["cam_from_rig_translation"] = T_cam_ref[:3,3].tolist()
        return config

    def append_pose_to_json(self, ins_msg, image_msg, cam_name, timestamp_str):
        """Append the pose data from INS message to the JSON."""
        # Convert quaternion to R matrix
        quat = ins_msg.qn2b

        # quat is [w, x, y, z], wrt NED frame -> make [x, y, z, w]
        reordered_quat = [quat[1], quat[2], quat[3], quat[0]]
        rot = R.from_quat(reordered_quat).as_matrix()
        R_ned_enu = np.array([
            [0, 1, 0],
            [1, 0, 0],
            [0, 0,-1]
        ])

        # (longitude, latitude) -> (easting, northing, zone number, zone letter)
        east, north, num, let = utm.from_latlon(ins_msg.lla[0], ins_msg.lla[1])
        altitude = ins_msg.lla[2]

        # make T vector in NED
        trans = [north, east, -altitude]

        # compose world pose of IMX-5
        T_ins_ned = np.eye(4)
        T_ins_ned[:3,:3] = rot
        T_ins_ned[:3,3] = trans

        T_ned_enu = np.eye(4)
        T_ned_enu[:3,:3] = R_ned_enu

        timestamp = ins_msg.header.stamp.sec + ins_msg.header.stamp.nanosec * 1e-9
        camera_id = self.get_camera_id(cam_name)
        ref_cam_name = next(iter(self.camera_ids))
        ref_cam = self.camera_models[ref_cam_name]["cam"]
        T_rig_enu = T_ned_enu @ T_ins_ned @ np.array(ref_cam["T_cam_ins"])
        T_enu_rig = np.linalg.inv(T_rig_enu)

        frame = self.frames_by_timestamp.get(timestamp_str)
        if frame is None:
            frame = {
                "frame_id": len(self.frames) + 1,
                "rig_id": 1,
                "timestamp": timestamp,
                "rig_from_world_rotation": self.rotation_to_quat_wxyz(
                    T_enu_rig[:3,:3]
                ),
                "rig_from_world_translation": T_enu_rig[:3,3].tolist(),
                "data_ids": [],
            }
            self.frames_by_timestamp[timestamp_str] = frame
            self.frames.append(frame)

        self.image_id += 1
        data_id = {
            "sensor_type": "CAMERA",
            "sensor_id": camera_id,
            "data_id": self.image_id,
            "timestamp": timestamp,
            "file_path": f"{cam_name}/{self.get_image_filename(timestamp_str)}",
        }
        frame["data_ids"].append(data_id)

    def save_json(self):
        """Save all frames to a JSON file."""
        savename = os.path.join(self.ds_dir, "transforms.json")
        camera_map = [
            {
                "sensor_type": "CAMERA",
                "sensor_id": camera_id,
                "camera_name": cam_name,
                "image_prefix": f"{cam_name}/",
            }
            for cam_name, camera_id in self.camera_ids.items()
        ]
        rig_config = [{
            "cameras": [
                self.colmap_camera_config(cam_name)
                for cam_name in self.camera_ids
            ],
        }]
        with open(savename, "w") as json_file:
            print(f'[PROC]    Saving JSON To: {savename}')
            json.dump(
                {
                    "rig_config": rig_config,
                    "cameras": camera_map,
                    "frames": self.frames,
                },
                json_file,
                indent=4
            )

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
    parser.add_argument("ins_topic", help="INS topic name (e.g., /ins_quat_uvw_lla)")
    parser.add_argument("--rate", type=int, default=1, help="Optional integer rate for frame subsampling.")
    parser.add_argument("--ind", type=int, nargs='+', help="Image subframe index or indices, from CamarrayHAT")
    parser.add_argument("--calibration", default=None, help="Path to the YAML file with camera calibration data")
    parser.add_argument("--no-rectify", action="store_false", dest="rectify", help="Whether or not to rectify in vi_time_sync.py (default: True)")
    parser.add_argument("--no-save", action="store_false", dest="save", help="Whether or not to save imagery (default: True)")
    parser.add_argument("--no-rebag", action="store_false", dest="rebag", help="Whether or not to save imagery (default: True)")

    args = parser.parse_args()

    rclpy.init()

    processor = BagProcessor(
        args.input_bag,
        args.output_bag,
        args.ds_dir,
        args.image_topic,
        args.ins_topic,
        args.rate,
        args.ind,
        args.calibration,
        args.rectify,
        args.save,
        args.rebag,
    )
    processor.process_bag()

    rclpy.shutdown()


if __name__ == "__main__":
    main()
