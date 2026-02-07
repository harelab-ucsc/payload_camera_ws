# #!/usr/bin/env python3
# """
# File:
#     as7265x_at_node.py

# Description:
#     AS7265x continuous streaming ROS 2 node
#     Option A: Hardware-driven burst mode (ATBURST=255)
#     Publishes incoming spectral data automatically.

# Date:
#     20 Jan 2026

# Version:
#     0.1.1
# """
# import rclpy
# from rclpy.node import Node
# from std_msgs.msg import String, Header
# from sensor_msgs.msg import Temperature
# from as7265x_at_msgs.msg import AS7265xRaw, AS7265xCal

# import serial
# import threading
# import time
# import re


# DEFAULT_PORT = "/dev/ttyUSB0"
# DEFAULT_BAUD = 115200
# READ_TIMEOUT = 0.1


# class AS7265xStreamNode(Node):
#     """
#     """
#     def __init__(self):
#         super().__init__('as7265x_stream')

#         # Parameters
#         self.declare_parameter('serial_port', DEFAULT_PORT)
#         self.declare_parameter('baudrate', DEFAULT_BAUD)
#         self.declare_parameter('integration_time', 20)  # ~2.8ms increments
#         self.declare_parameter('gain', 1)               # 0–3
#         self.declare_parameter('interval', 1)           # 1–255
#         self.declare_parameter('calibrated', True)      # True → ATCDATA mode

#         port = self.get_parameter('serial_port').value
#         baud = int(self.get_parameter('baudrate').value)

#         # Publishers
#         self.pub_raw = self.create_publisher(
#             AS7265xRaw,
#             'as7265x/raw_values',
#             10
#         )
#         self.pub_cal = self.create_publisher(
#             AS7265xCal,
#             'as7265x/calibrated_values',
#             10
#         )
#         self.pub_temp = self.create_publisher(
#             Temperature,
#             'as7265x/temperature',
#             10
#         )
#         self.pub_debug = self.create_publisher(String, 'as7265x/at_raw', 10)

#         # Serial link
#         try:
#             self.ser = serial.Serial(port, baud, timeout=READ_TIMEOUT)
#             self.get_logger().info(f"Opened {port} @ {baud}")
#         except Exception as e:
#             self.get_logger().fatal(f"Failed to open serial: {e}")
#             raise SystemExit

#         # Stop flag for clean exit
#         self.stop_evt = threading.Event()

#         # Configure device
#         self.configure_device()

#         # Start background reader
#         self.reader_thread = threading.Thread(
#             target=self.read_loop,
#             daemon=True
#         )
#         self.reader_thread.start()


#     def configure_device(self):
#         resp = []
#         # Integration time
#         it = int(self.get_parameter('integration_time').value)
#         self.send(f"ATINTTIME={it}")
#         resp.append(self.ser.read(256).decode('utf-8', errors='replace'))

#         # Gain
#         g = int(self.get_parameter('gain').value)
#         self.send(f"ATGAIN={g}")
#         resp.append(self.ser.read(256).decode('utf-8', errors='replace'))

#         # Sampling interval multiplier
#         iv = int(self.get_parameter('interval').value)
#         self.send(f"ATINTRVL={iv}")
#         resp.append(self.ser.read(256).decode('utf-8', errors='replace'))

#         # Enable continuous burst mode
#         mode = 1 if self.get_parameter('calibrated').value else 0
#         self.send(f"ATBURST=255,{mode}")
#         resp.append(self.ser.read(256).decode('utf-8', errors='replace'))

#         # self.get_logger().info(resp)
#         if all('OK\n' in r for r in resp):
#             self.get_logger().info(
#                 "AS7265x is now streaming continuously (burst mode 255)."
#             )
#         else:
#             self.get_logger().info(
#                 "AS7265x configuration failure. Killing node."
#             )
#             self.destroy_node()

#     # ---------------------------------------------------------
#     # Send AT commands over serial connection
#     # ---------------------------------------------------------
#     def send(self, cmd: str):
#         try:
#             self.ser.write((cmd + "\r\n").encode('utf-8'))
#         except Exception as e:
#             self.get_logger().error(f"Write error: {e}")

#     # ---------------------------------------------------------
#     # Background serial reader
#     # ---------------------------------------------------------
#     def read_loop(self):
#         """
#         Robust serial reader that:
#         - handles partial reads
#         - handles None returns from serial.read()
#         - safely buffers until newline
#         - supports CR, LF, CRLF, \r\r\n
#         - never crashes on invalid UTF-8
#         """
#         buf = bytearray()

#         while not self.stop_evt.is_set():
#             try:
#                 data = self.ser.read(256)

#                 # pyserial CAN return None on USB glitches
#                 if data is None:
#                     time.sleep(0.01)
#                     continue

#                 # If no data, loop again
#                 if len(data) == 0:
#                     time.sleep(0.005)
#                     continue

#                 # Append incoming bytes
#                 buf.extend(data)

#                 # Process complete lines
#                 while True:
#                     nl = buf.find(b'\n')
#                     if nl == -1:
#                         break  # no complete line yet

#                     # Extract line (strip CR and whitespace)
#                     raw = buf[:nl].rstrip(b'\r')
#                     del buf[:nl+1]  # remove line including newline

#                     if not raw:
#                         continue

#                     # Decode safely
#                     try:
#                         line = raw.decode('utf-8', errors='replace').strip()
#                     except Exception as e:
#                         self.get_logger().warn(f"Decode error: {e}")
#                         continue

#                     if line:
#                         self.handle_line(line)

#             except Exception as e:
#                 self.get_logger().error(f"Serial read error: {e}")
#                 time.sleep(0.1)

#     # ---------------------------------------------------------
#     # Parse incoming burst lines
#     # ---------------------------------------------------------
#     def handle_line(self, line: str):
#         # Debug publisher
#         dbg = String()
#         dbg.data = line
#         self.pub_debug.publish(dbg)

#         line = line.strip()
#         if line.lower().startswith("data:"):
#             line = line.split(":", 1)[1].strip()


#         # Parse comma values: raw (ints) or calibrated (floats)
#         if "," in line:
#             parts = [p.strip() for p in line.split(",")]

#             # --- Temperature format: A,B,C ---
#             if len(parts) == 3 and all(re.match(r'^-?\d+(\.\d+)?$', p) for p in parts):
#                 temps = [float(x) for x in parts]
#                 tmsg = Temperature()
#                 tmsg.temperature = sum(temps) / len(temps)
#                 tmsg.variance = 0.0
#                 self.pub_temp.publish(tmsg)
#                 return

#             elif len(parts) >= 18:
#                 calibrated = self.get_parameter('calibrated').value

#                 if calibrated:
#                     pub = self.pub_cal
#                     m = AS7265xCal()
#                     data = [float(p) for p in parts]
#                 else:
#                     pub = self.pub_raw
#                     m = AS7265xRaw()
#                     data = [int(p) for p in parts]

#                 try:
#                     header = Header()
#                     header.stamp = self.get_clock().now().to_msg()
#                     header.frame_id = "as7265x"

#                     m.header = header
#                     m.values = data
#                     pub.publish(m)
#                     return
#                 except Exception as e:
#                     self.get_logger().info(e)
#                     pass

#         elif line == "OK":
#             # self.get_logger().info(line)
#             return

#         else:
#             self.get_logger().info(f'Unexpected line recieved: \n    {line}')
#             return


#     def destroy_node(self):
#         self.send(f"ATBURST=0")
#         self.stop_evt.set()
#         try:
#             self.ser.close()
#         except:
#             pass
#         super().destroy_node()


# def main(args=None):
#     rclpy.init(args=args)
#     node = AS7265xStreamNode()
#     try:
#         rclpy.spin(node)
#     except KeyboardInterrupt:
#         pass
#     finally:
#         node.destroy_node()
#         rclpy.shutdown()


# if __name__ == "__main__":
#     main()









#!/usr/bin/env python3
"""
File:
    as7265x_at_node.py

Description:
    AS7265x continuous streaming ROS 2 node (AT command interface)
    - Enables burst streaming (ATBURST=255)
    - Publishes raw or calibrated spectral values
    - Publishes temperature (3-value format) if present
    - Publishes debug raw AT lines
    - Stamps outgoing messages using PPS time from /pps/time if available,
      otherwise falls back to node clock time.

Date:
    20 Jan 2026

Version:
    0.1.3  (PPS stamping + flexible spectral length)
"""

import rclpy
from rclpy.node import Node

from std_msgs.msg import String, Header
from sensor_msgs.msg import Temperature
from builtin_interfaces.msg import Time as BuiltinTime

from as7265x_at_msgs.msg import AS7265xRaw, AS7265xCal

import serial
import threading
import time
import re


DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_BAUD = 115200
READ_TIMEOUT = 0.1


class AS7265xStreamNode(Node):
    def __init__(self):
        super().__init__('as7265x_stream')

        # ----------------------------
        # Parameters
        # ----------------------------
        self.declare_parameter('serial_port', DEFAULT_PORT)
        self.declare_parameter('baudrate', DEFAULT_BAUD)
        self.declare_parameter('integration_time', 20)  # ~2.8ms increments
        self.declare_parameter('gain', 1)               # 0–3
        self.declare_parameter('interval', 1)           # 1–255
        self.declare_parameter('calibrated', True)      # True → ATCDATA / calibrated
        self.declare_parameter('pps_topic', '/pps/time')

        port = self.get_parameter('serial_port').value
        baud = int(self.get_parameter('baudrate').value)
        self.pps_topic = self.get_parameter('pps_topic').value

        # ----------------------------
        # Publishers
        # ----------------------------
        self.pub_raw = self.create_publisher(AS7265xRaw, 'as7265x/raw_values', 10)
        self.pub_cal = self.create_publisher(AS7265xCal, 'as7265x/calibrated_values', 10)
        self.pub_temp = self.create_publisher(Temperature, 'as7265x/temperature', 10)
        self.pub_debug = self.create_publisher(String, 'as7265x/at_raw', 10)

        # ----------------------------
        # PPS subscriber
        # ----------------------------
        self.latest_pps_stamp = None
        self.pps_lock = threading.Lock()
        self.warned_no_pps = False

        self.create_subscription(
            BuiltinTime,
            self.pps_topic,
            self.pps_cb,
            10
        )

        # ----------------------------
        # Serial link
        # ----------------------------
        try:
            self.ser = serial.Serial(port, baud, timeout=READ_TIMEOUT)
            self.get_logger().info(f"Opened {port} @ {baud}")
        except Exception as e:
            self.get_logger().fatal(f"Failed to open serial: {e}")
            raise SystemExit

        # Stop flag for clean exit
        self.stop_evt = threading.Event()

        # Configure device
        self.configure_device()

        # Start background reader
        self.reader_thread = threading.Thread(target=self.read_loop, daemon=True)
        self.reader_thread.start()

        self.get_logger().info(f"AS7265xStreamNode running. Using PPS topic: {self.pps_topic}")

    # ----------------------------
    # PPS callback
    # ----------------------------
    def pps_cb(self, msg: BuiltinTime):
        with self.pps_lock:
            self.latest_pps_stamp = msg

    # ----------------------------
    # Device configuration
    # ----------------------------
    def configure_device(self):
        resp = []

        it = int(self.get_parameter('integration_time').value)
        self.send(f"ATINTTIME={it}")
        resp.append(self.ser.read(256).decode('utf-8', errors='replace'))

        g = int(self.get_parameter('gain').value)
        self.send(f"ATGAIN={g}")
        resp.append(self.ser.read(256).decode('utf-8', errors='replace'))

        iv = int(self.get_parameter('interval').value)
        self.send(f"ATINTRVL={iv}")
        resp.append(self.ser.read(256).decode('utf-8', errors='replace'))

        mode = 1 if bool(self.get_parameter('calibrated').value) else 0
        self.send(f"ATBURST=255,{mode}")
        resp.append(self.ser.read(256).decode('utf-8', errors='replace'))

        if all('OK\n' in r for r in resp):
            self.get_logger().info("AS7265x is now streaming continuously (burst mode 255).")
        else:
            self.get_logger().error("AS7265x configuration failure. Killing node.")
            self.destroy_node()

    # ----------------------------
    # Send AT commands
    # ----------------------------
    def send(self, cmd: str):
        try:
            self.ser.write((cmd + "\r\n").encode('utf-8'))
        except Exception as e:
            self.get_logger().error(f"Write error: {e}")

    # ----------------------------
    # Stamp helper: PPS if available, else node time
    # ----------------------------
    def get_best_stamp(self) -> BuiltinTime:
        with self.pps_lock:
            pps_stamp = self.latest_pps_stamp

        if pps_stamp is None:
            if not self.warned_no_pps:
                self.get_logger().warn(
                    f"No PPS timestamp received on {self.pps_topic} yet; using node clock time."
                )
                self.warned_no_pps = True
            return self.get_clock().now().to_msg()

        return pps_stamp

    # ----------------------------
    # Background serial reader
    # ----------------------------
    def read_loop(self):
        buf = bytearray()

        while not self.stop_evt.is_set():
            try:
                data = self.ser.read(256)

                if data is None:
                    time.sleep(0.01)
                    continue

                if len(data) == 0:
                    time.sleep(0.005)
                    continue

                buf.extend(data)

                while True:
                    nl = buf.find(b'\n')
                    if nl == -1:
                        break

                    raw = buf[:nl].rstrip(b'\r')
                    del buf[:nl + 1]

                    if not raw:
                        continue

                    line = raw.decode('utf-8', errors='replace').strip()
                    if line:
                        self.handle_line(line)

            except Exception as e:
                self.get_logger().error(f"Serial read error: {e}")
                time.sleep(0.1)

    # ----------------------------
    # Parse incoming burst lines
    # ----------------------------
    def handle_line(self, line: str):
        # Debug publisher (raw AT line)
        dbg = String()
        dbg.data = line
        self.pub_debug.publish(dbg)

        line = line.strip()
        if line.lower().startswith("data:"):
            line = line.split(":", 1)[1].strip()

        # Parse comma values
        if "," in line:
            parts = [p.strip() for p in line.split(",")]

            # Temperature format: "A,B,C"
            if len(parts) == 3 and all(re.match(r'^-?\d+(\.\d+)?$', p) for p in parts):
                temps = [float(x) for x in parts]
                tmsg = Temperature()
                tmsg.header.stamp = self.get_best_stamp()
                tmsg.header.frame_id = "as7265x"
                tmsg.temperature = sum(temps) / len(temps)
                tmsg.variance = 0.0
                self.pub_temp.publish(tmsg)
                return

            # Spectral payload: accept 12+ values (some firmwares output 14, others 18)
            if len(parts) >= 12:
                calibrated = bool(self.get_parameter('calibrated').value)

                if calibrated:
                    pub = self.pub_cal
                    m = AS7265xCal()
                    try:
                        data = [float(p) for p in parts]
                    except ValueError:
                        return
                else:
                    pub = self.pub_raw
                    m = AS7265xRaw()
                    try:
                        data = [int(float(p)) for p in parts]
                    except ValueError:
                        return

                header = Header()
                header.stamp = self.get_best_stamp()
                header.frame_id = "as7265x"

                m.header = header
                m.values = data
                pub.publish(m)
                return

        if line == "OK":
            return

        # Anything else
        self.get_logger().info(f"Unexpected line received:\n    {line}")

    # ----------------------------
    # Cleanup
    # ----------------------------
    def destroy_node(self):
        try:
            self.send("ATBURST=0")
        except Exception:
            pass

        self.stop_evt.set()

        try:
            self.ser.close()
        except Exception:
            pass

        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = AS7265xStreamNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

