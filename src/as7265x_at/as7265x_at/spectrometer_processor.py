#!/usr/bin/env python3
"""
File: spectrometer_processor.py
Description: 
    Subscribes to AS7265x calibrated data, maps indices to wavelengths,
    and calculates basic indices like NDVI for vegetation analysis.
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32, Float32MultiArray
from as7265x_at_msgs.msg import AS7265xCal

class SpectrometerProcessor(Node):
    def __init__(self):
        super().__init__('spectrometer_processor')

    # Mapping based on AS7265x (Triad) standard channel order:
    # AS72652 (UV): 410, 435, 460, 485, 510, 535 nm
    # AS72653 (VIS): 560, 585, 645, 705, 900, 940 nm
    # AS72651 (NIR): 610, 680, 730, 760, 810, 860 nm
    # Sorted order for processing:
        self.wavelengths = [
            410, 435, 460, 485, 510, 535, 
            560, 585, 610, 645, 680, 705, 
            730, 760, 810, 860, 900, 940
        ]

        # Subscribers
        self.subscription = self.create_subscription(
            AS7265xCal,
            'as7265x/calibrated_values',
            self.listener_callback,
            10
        )

        # Publishers
        self.ndvi_pub = self.create_publisher(Float32, 'spectrometer/ndvi', 10)
        self.total_irradiance_pub = self.create_publisher(Float32, 'spectrometer/total_intensity', 10)

        self.get_logger().info("Spectrometer Processor Node Started")

    def listener_callback(self, msg):
        data = msg.values
        
        if len(data) < 18:
            self.get_logger().warn(f"Received incomplete data: {len(data)} channels")
            return

        # 1. Calculate Peak Wavelength
        max_val = max(data)
        peak_idx = data.index(max_val)
        peak_wavelength = self.wavelengths[peak_idx]

        # 2. Vegetation Indices (MicaSense Style)
        # Red is usually ~680nm (Index 10), NIR is usually ~810nm (Index 14)
        # Indices depend on how your AT firmware orders the 18-comma string.
        # Typically: 410(0), 435(1), 460(2), 485(3), 510(4), 535(5), 
        #            560(6), 585(7), 645(8), 705(9), 900(10), 940(11),
        #            610(12), 680(13), 730(14), 760(15), 810(16), 860(17)
        # Check your hardware datasheet/firmware to confirm index mapping!
        
        try:
            red = data[13] # 680nm
            nir = data[16] # 810nm
            
            if (nir + red) != 0:
                ndvi = (nir - red) / (nir + red)
                ndvi_msg = Float32()
                ndvi_msg.data = float(ndvi)
                self.ndvi_pub.publish(ndvi_msg)
        except IndexError:
            pass

        # 3. Calculate Total Intensity (Integration)
        total_intensity = sum(data)
        ti_msg = Float32()
        ti_msg.data = float(total_intensity)
        self.total_irradiance_pub.publish(ti_msg)

        # Log Status
        self.get_logger().info(
            f"Peak: {peak_wavelength}nm | Intensity: {total_intensity:.2f}", 
            throttle_duration_sec=1.0
        )

def main(args=None):
    rclpy.init(args=args)
    node = SpectrometerProcessor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()