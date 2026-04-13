#!/usr/bin/env python3
"""
File: sync_node.py
Description: 
    ROS 2 Sync Node based on State Machine Specs.
    Flow: Wait for PPS -> Clear State -> Catch All (Cam, Pose, Spec, Radalt) 
    -> Stamp/Correct -> Save (Multithreaded).
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Header, Float32MultiArray
from builtin_interfaces.msg import Time as BuiltinTime
from inertial_sense_ros2.msg import DIDINS2
from custom_msgs.msg import AltSNR
from as7265x_at_msgs.msg import AS7265xCal

import cv2
import os
import threading
import numpy as np
from cv_bridge import CvBridge
from .dbConnector import dbConnector # Assuming it's in the same package

class SyncNode(Node):
    def __init__(self):
        super().__init__('sync_node')
        self.br = CvBridge()
        
        # --- Parameters ---
        self.declare_parameter('db_name', 'flight_sync_data')
        self.declare_parameter('output_dir', 'parsed_flight')
        self.sensor_id = "multispectral_sync"
        
        db_path = os.path.join(os.path.expanduser('~'), self.get_parameter('output_dir').value)
        os.makedirs(db_path, exist_ok=True)
        self.dbc = dbConnector(os.path.join(db_path, self.get_parameter('db_name').value))
        self.dbc.boot(self.get_parameter('db_name').value, self.sensor_id)

        # --- INS bitmasks ---
        self.HDW_STROBE = 0x00000020
        self.INS_STATUS_SOLUTION_MASK = 0x000F0000
        self.INS_STATUS_SOLUTION_OFFSET = 16
        self.INS_STATUS_GPS_NAV_FIX_MASK = 0x03000000
        self.INS_STATUS_GPS_NAV_FIX_OFFSET = 24
        self.RTK_STATUS = None
        self.INS_STATUS = None

        # --- State Machine Variables ---
        self.state_lock = threading.Lock()
        self.current_pps_stamp = None
        self.caught_data = {
            'cam0': None,
            'cam1': None,
            'pose': None,
            'spec': None,
            'radalt': None,
            'RTK_STATUS': None,
            'INS_STATUS': None
        }

        # --- Subscriptions ---
        # 1. PPS Trigger (The heartbeat of the state machine)
        self.create_subscription(BuiltinTime, '/pps/time', self.pps_cb, 10)
        
        # 2. Camera Streams
        self.create_subscription(Image, '/cam0/image_raw', self.cam0_cb, 10)
        self.create_subscription(Image, '/cam1/image_raw', self.cam1_cb, 10)
        
        # 3. Navigation & Environment
        self.create_subscription(DIDINS2, '/ins', self.ins_cb, 10)
        self.create_subscription(AltSNR, '/rad_altitude', self.radalt_cb, 10)
        
        # 4. AS7265x Spectrometer (For Reflectance)
        self.create_subscription(AS7265xCal, 'as7265x/calibrated_values', self.spec_cb, 10)

        self.get_logger().info("Sync Node Initialized. Waiting for PPS Trigger...")

    # --- 1. PPS Trigger (State Machine Start) ---
    def pps_cb(self, msg: BuiltinTime):
        with self.state_lock:
            # Check for "Big Error" logic from diagram: 
            # If we get a NEW PPS but haven't "Caught All" from the last one
            if any(v is not None for v in self.caught_data.values()) and not self.all_caught():
                self.get_logger().error("BIG ERROR: New PPS received before previous cycle completed!")
            
            # Clear State
            self.current_pps_stamp = msg
            for key in self.caught_data:
                self.caught_data[key] = None
            # self.get_logger().info(f"State Cleared. New Sync Cycle: {msg.sec}.{msg.nanosec}")

    # --- 2. Data "Catch" Callbacks ---
    def cam0_cb(self, msg):
        self.catch('cam0', msg)

    def cam1_cb(self, msg):
        self.catch('cam1', msg)

    def ins_cb(self, msg):
        # Using logic from your provided subscriberNode
        # Check if Strobed

#        u = utm.from_latlon(msg.lla[0], msg.lla[1])  # returns easting, northing, zone number, zone letter
#        self.utm_NUM = u[2]
#        self.utm_LET = u[3]
#        self.pos = [u[0], u[1], msg.lla[2]]  # save x:easting, y:northing, z:WGS84 altitude
#
#        # the quaternion comes in scalar-first format - convert it to scalar-last
#        self.quat = [msg.qn2b[1], msg.qn2b[2], msg.qn2b[3], msg.qn2b[0]]
#        # the quaternion comes in in a NED reference - convert it to ENU
#        self.quat = [self.quat[1], self.quat[0], -self.quat[2], self.quat[3]

        if msg.hdw_status & self.HDW_STROBE == self.HDW_STROBE:
            self.catch('pose', msg)

    def radalt_cb(self, msg):
        if msg.snr > 13:
            self.catch('radalt', msg.altitude)

    def spec_cb(self, msg):
        self.catch('spec', msg.values)

    def catch(self, key, data):
        with self.state_lock:
            if self.current_pps_stamp is None:
                return # Ignore data until first PPS arrives
            
            if self.caught_data[key] is None:
                self.caught_data[key] = data
                
            if self.all_caught():
                # Logic: Stamp -> Split/Process -> Save
                self.process_sync_cycle()

    def all_caught(self):
        return all(v is not None for v in self.caught_data.values())

    # --- 3. Processing & Radiometric Correction ---
    def process_sync_cycle(self):
        # Capture a snapshot of data to free the lock quickly
        data = self.caught_data.copy()
        stamp = self.current_pps_stamp
        
        # Reset state for next cycle immediately
        for key in self.caught_data:
            self.caught_data[key] = None
        self.current_pps_stamp = None

        # Start a thread for saving (Multithreaded as per specs)
        threading.Thread(target=self.post_process_and_save, args=(data, stamp)).start()

    def post_process_and_save(self, data, stamp):
        """
        Implements MicaSense-style correction using AS7265x data
        before saving to disk and SQL.
        """
        try:
            # 1. Split & Reflectance Post-Processing
            # Indices: Red=13 (680nm), NIR=16 (810nm)
            spec_vals = data['spec']
            cam0_raw = self.br.imgmsg_to_cv2(data['cam0'], desired_encoding='passthrough')
            
            # Apply Spectrometer Correction (Simplifed Reflectance Bridge)
            # Reflectance = Raw / Irradiance
            red_irr = spec_vals[13]
            corrected_img = (cam0_raw.astype(np.float32) / red_irr) if red_irr > 0 else cam0_raw

            # 2. Save Image to File
            time_str = f"{stamp.sec}_{stamp.nanosec}"
            filename = os.path.join(os.path.expanduser('~'), f"parsed_flight/corrected_{time_str}.png")
            cv2.imwrite(filename, (np.clip(corrected_img, 0, 1)*255).astype(np.uint8))

            # 3. Save Data Frame to SQL
            pose = data['pose']
            # Format: x, y, z, q, u, a, t, status, radalt, path, time...
            u = utm.from_latlon(msg.lla[0], msg.lla[1])  # returns easting, northing, zone number, zone letter
            utm_NUM = u[2]
            utm_LET = u[3]
              # save x:easting, y:northing, z:WGS84 altitude

            vals = [
                # UTM -> save x:easting, y:northing, z:WGS84 altitude
                u[0], u[1], pose.lla[2], 
                # quat comes scalar-first in NED -> convert to scalar-last ENU for saving
                pose.qn2b[2], pose.qn2b[1], -pose.qn2b[3], pose.qn2b[0], 
                int(pose.ins_status), float(data['radalt']), f"'{filename}'",
                stamp.sec, stamp.nanosec
            ]
            
            val_str = ','.join(map(str, vals))
            self.dbc.insertIgnoreInto(
                f"{self.sensor_id}_images_{self.get_parameter('db_name').value}",
                "x, y, z, q, u, a, t, ins_status, radalt, save_loc, cam_time1, cam_time2",
                val_str
            )
            
            # self.get_logger().info(f"Cycle Complete: Saved {filename}")

        except Exception as e:
            self.get_logger().error(f"Post-processing failed: {e}")

def main(args=None):
    rclpy.init(args=args)
    node = SyncNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
