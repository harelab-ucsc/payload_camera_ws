#!/usr/bin/env python3
"""
AS7265x continuous streaming ROS 2 node.

Option A: Hardware-driven burst mode (ATBURST=255).
Publishes incoming spectral data automatically.
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Header
from sensor_msgs.msg import Temperature
from as7265x_at_msgs.msg import AS7265xRaw, AS7265xCal

import serial
import threading
import time
import re

DEFAULT_PORT = "/dev/devAS7265x"
DEFAULT_BAUD = 115200
READ_TIMEOUT = 0.1


class AS7265xStreamNode(Node):
    def __init__(self):
        super().__init__('as7265x_stream')

        # Parameters
        self.declare_parameter('serial_port', DEFAULT_PORT)
        self.declare_parameter('baudrate', DEFAULT_BAUD)
        self.declare_parameter('integration_time', 20)  # ~2.8ms increments
        self.declare_parameter('gain', 1)               # 0–3
        self.declare_parameter('interval', 1)           # 1–255
        self.declare_parameter('calibrated', True)      # True → ATCDATA mode

        port = self.get_parameter('serial_port').value
        baud = int(self.get_parameter('baudrate').value)

        # Publishers
        self.pub_raw = self.create_publisher(AS7265xRaw, 'as7265x/raw_values', 10)
        self.pub_cal = self.create_publisher(AS7265xCal, 'as7265x/calibrated_values', 10)
        self.pub_temp = self.create_publisher(Temperature, 'as7265x/temperature', 10)
        self.pub_debug = self.create_publisher(String, 'as7265x/at_raw', 10)

        # Serial link
        try:
            self.ser = serial.Serial(port, baud, timeout=READ_TIMEOUT)
            self.get_logger().info(f"Opened {port} @ {baud}")
        except Exception as e:
            self.get_logger().fatal(f"Failed to open serial: {e}")
            raise SystemExit

        # stop flag for clean exit
        self.stop_evt = threading.Event()

        # Stop any in-progress burst streaming (e.g. from an unclean previous shutdown),
        # flush the drain of buffered burst data, then configure fresh.
        time.sleep(0.2)
        self.ser.reset_input_buffer()
        self.ser.write(b"ATBURST=0\r\n")
        time.sleep(1.0)  # wait for device to stop streaming and flush output
        self.ser.reset_input_buffer()

        # Configure device
        self.configure_device()

        # Start background reader
        self.reader_thread = threading.Thread(target=self.read_loop, daemon=True)
        self.reader_thread.start()

    def _cmd(self, cmd: str) -> str:
        self.ser.reset_input_buffer()
        self.send(cmd)
        resp = self.ser.read(256).decode('utf-8', errors='replace')
        if 'OK\n' not in resp:
            self.get_logger().warn(f"No OK for '{cmd}': {repr(resp)}")
        return resp

    def configure_device(self):
        port = self.get_parameter('serial_port').value
        baud = int(self.get_parameter('baudrate').value)
        cmds = [
            f"ATINTTIME={int(self.get_parameter('integration_time').value)}",
            f"ATGAIN={int(self.get_parameter('gain').value)}",
            f"ATINTRVL={int(self.get_parameter('interval').value)}",
            f"ATBURST=255,{1 if self.get_parameter('calibrated').value else 0}",
        ]
        self.ser.timeout = 2.0
        try:
            resp = [self._cmd(c) for c in cmds]
        except serial.SerialException as e:
            # Device likely did a USB reset after ATBURST=0 stopped streaming.
            # Close, wait for USB re-enumeration, reopen, and retry once.
            self.get_logger().warn(f"Serial disconnect during config: {e}. Reopening port...")
            try:
                self.ser.close()
            except Exception:
                pass
            time.sleep(3.0)
            try:
                self.ser = serial.Serial(port, baud, timeout=2.0)
                time.sleep(0.5)
                self.ser.reset_input_buffer()
                resp = [self._cmd(c) for c in cmds]
            except Exception as e2:
                self.ser.timeout = READ_TIMEOUT
                self.get_logger().info(
                    f"AS7265x config failed after reconnect: {e2}. Killing node."
                )
                self.destroy_node()
                return
        finally:
            self.ser.timeout = READ_TIMEOUT

        if all('OK\n' in r for r in resp):
            self.get_logger().info("AS7265x is now streaming continuously (burst mode 255).")
        else:
            self.get_logger().info("AS7265x configuration failure. Killing node.")
            self.destroy_node()

    # ---------------------------------------------------------
    # Send AT command
    # ---------------------------------------------------------
    def send(self, cmd: str):
        try:
            self.ser.write((cmd + "\r\n").encode('utf-8'))
        except Exception as e:
            self.get_logger().error(f"Write error: {e}")

    # ---------------------------------------------------------
    # Background serial reader
    # ---------------------------------------------------------
    def read_loop(self):
        while not self.stop_evt.is_set():
            try:
                # readline() blocks until \n or READ_TIMEOUT — no busy-spin
                # on partial data unlike read(N) which returns immediately
                raw = self.ser.readline()
                if not raw:
                    continue
                line = raw.rstrip(b'\r\n').decode('utf-8', errors='replace').strip()
                if line:
                    self.handle_line(line)
            except Exception as e:
                self.get_logger().error(f"Serial read error: {e}")
                time.sleep(0.1)

    # ---------------------------------------------------------
    # Parse incoming burst lines
    # ---------------------------------------------------------
    def handle_line(self, line: str):
        # Debug publisher
        dbg = String()
        dbg.data = line
        self.pub_debug.publish(dbg)

        # Parse comma values: raw (ints) or calibrated (floats)
        if "," in line:
            parts = [p.strip() for p in line.split(",")]

            # --- Temperature format: A,B,C ---
            if len(parts) == 3 and all(re.match(r'^-?\d+(\.\d+)?$', p) for p in parts):
                temps = [float(x) for x in parts]
                tmsg = Temperature()
                tmsg.temperature = sum(temps) / len(temps)
                tmsg.variance = 0.0
                self.pub_temp.publish(tmsg)
                return

            elif len(parts) >= 18:
                calibrated = self.get_parameter('calibrated').value

                if calibrated:
                    pub = self.pub_cal
                    m = AS7265xCal()
                    data = [float(p) for p in parts]
                else:
                    pub = self.pub_raw
                    m = AS7265xRaw()
                    data = [int(p) for p in parts]

                try:
                    header = Header()
                    header.stamp = self.get_clock().now().to_msg()
                    header.frame_id = "as7265x"

                    m.header = header
                    m.values = data
                    pub.publish(m)
                    return
                except Exception as e:
                    self.get_logger().info(e)
                    pass

        elif line == "OK":
            # self.get_logger().info(line)
            return

        else:
            self.get_logger().info(f'Unexpected line recieved: \n    {line}')
            return

    def destroy_node(self):
        self.send("ATBURST=0")
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
