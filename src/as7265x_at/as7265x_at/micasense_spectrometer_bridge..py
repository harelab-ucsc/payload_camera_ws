#!/usr/bin/env python3
"""
File: micasense_spectrometer_bridge.py
Description:
    Processes AS7265x spectral data for MicaSense-style reflectance calculations.
    - Maps 18 channels to wavelengths.
    - Provides a service to "Capture Panel" (Calibration).
    - Publishes Irradiance and Reflectance.
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray, Header
from std_srvs.srv import Trigger
from as7265x_at_msgs.msg import AS7265xCal

class MicaSenseSpectrometerBridge(Node):
    def __init__(self):
        super().__init__('micasense_spectrometer_bridge')

    # Wavelength mapping for AS72651, AS72652, AS72653 (Triad Spectral Sensor)
    # The default AT command firmware outputs values in a specific order:
    # A, B, C, D, E, F, G, H, I, J, K, L, R, S, T, U, V, W
        self.wavelengths = [
            410, 435, 460, 485, 510, 535, # AS72652 (UV)
            560, 585, 645, 705, 900, 940, # AS72653 (VIS)
            610, 680, 730, 760, 810, 860  # AS72651 (NIR)
        ]

        # Calibration storage (for Reflectance calculation)
        self.panel_calibration = None 

        # Publishers
        self.irradiance_pub = self.create_publisher(Float32MultiArray, 'spectrometer/irradiance', 10)
        self.reflectance_pub = self.create_publisher(Float32MultiArray, 'spectrometer/reflectance', 10)

        # Subscriber to your driver
        self.subscription = self.create_subscription(
            AS7265xCal,
            'as7265x/calibrated_values',
            self.spectral_callback,
            10
        )

        # Service to "Set Calibration Panel" 
        # Call this when the sensor is over the MicaSense white calibration panel
        self.srv = self.create_service(Trigger, 'spectrometer/capture_panel', self.capture_panel_callback)

        self.get_logger().info("MicaSense Spectrometer Bridge Node Initialized.")

    def capture_panel_callback(self, request, response):
        """ Stores the current spectral reading as the white reference (100% reflectance) """
        self.last_data = getattr(self, 'current_raw_data', None)
        if self.last_data is not None:
            self.panel_calibration = self.last_data
            response.success = True
            response.message = f"Captured panel calibration across {len(self.panel_calibration)} bands."
            self.get_logger().info(response.message)
        else:
            response.success = False
            response.message = "No data received from sensor yet."
        return response

    def spectral_callback(self, msg: AS7265xCal):
        self.current_raw_data = msg.values
        
        # 1. Publish Irradiance (Raw calibrated values from sensor)
        irr_msg = Float32MultiArray()
        irr_msg.data = [float(x) for x in msg.values]
        self.irradiance_pub.publish(irr_msg)

        # 2. Publish Reflectance (If panel has been captured)
        if self.panel_calibration is not None:
            reflectance = []
            for i in range(len(msg.values)):
                # Reflectance = Current / Panel_Reference
                # (Assuming the panel is a 1.0 lambertian reflector)
                denom = self.panel_calibration[i]
                val = (msg.values[i] / denom) if denom != 0 else 0.0
                reflectance.append(float(val))
            
            ref_msg = Float32MultiArray()
            ref_msg.data = reflectance
            self.reflectance_pub.publish(ref_msg)

def main(args=None):
    rclpy.init(args=args)
    node = MicaSenseSpectrometerBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()