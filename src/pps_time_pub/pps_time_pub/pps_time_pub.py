#!/usr/bin/env python3
import subprocess
import threading
import time

import pps_tools

import rclpy
from rclpy.node import Node
from builtin_interfaces.msg import Time


class PpsTimePub(Node):
    def __init__(self):
        super().__init__("pps_time_pub")
        self.pub = self.create_publisher(Time, "/pps/time", 10)

        # ---------- Parameters ----------
        self.declare_parameter("pps_device", "/dev/pps0")
        self.declare_parameter("pps_topic", "/pps/time")

        self.declare_parameter("start_pwm", True)
        self.declare_parameter("pwm_script", "/home/pi4/rpi_pwm_control.py")
        self.declare_parameter("pwm_python", "python3")
        self.declare_parameter("pwm_start_delay_s", 0.25)

        # How long (s) without a PPS edge before the watchdog fires
        self.declare_parameter("watchdog_interval_s", 10.0)

        self.pps_device = self.get_parameter("pps_device").value
        self.pps_topic = self.get_parameter("pps_topic").value
        self.watchdog_interval = float(
            self.get_parameter("watchdog_interval_s").value
        )

        if self.pps_topic != "/pps/time":
            self.pub = self.create_publisher(Time, self.pps_topic, 10)

        self.stop_evt = threading.Event()
        self.pwm_proc = None

        self.get_logger().info(
            f"pps_time_pub starting. device={self.pps_device} topic={self.pps_topic}"
        )
        self.get_logger().debug(
            f"  start_pwm={self.get_parameter('start_pwm').value}"
            f"  pwm_python={self.get_parameter('pwm_python').value}"
            f"  pwm_script={self.get_parameter('pwm_script').value}"
            f"  pwm_start_delay_s={self.get_parameter('pwm_start_delay_s').value}"
            f"  watchdog_interval_s={self.watchdog_interval}"
        )

        self.th = threading.Thread(target=self._run, daemon=True)
        self.th.start()

    def _run(self):
        # 1) Start PWM generator script (if enabled)
        if bool(self.get_parameter("start_pwm").value):
            py = self.get_parameter("pwm_python").value
            script = self.get_parameter("pwm_script").value
            self.get_logger().info(f"Starting PWM generator: {py} {script}")
            try:
                self.pwm_proc = subprocess.Popen(
                    [py, script],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                self.get_logger().info(
                    f"PWM generator started (pid={self.pwm_proc.pid})"
                )
            except Exception as e:
                self.get_logger().error(f"Failed to start PWM generator: {e}")

            delay = float(self.get_parameter("pwm_start_delay_s").value)
            time.sleep(max(0.0, delay))

        # 2) Open PPS device directly — no sudo, no subprocess
        try:
            ppsf = pps_tools.PpsFile(self.pps_device)
        except Exception as e:
            self.get_logger().error(
                f"Failed to open {self.pps_device}: {e}\n"
                "Tip: add a udev rule so you don't need sudo:\n"
                '  KERNEL=="pps0", GROUP="dialout", MODE="0660"'
            )
            return

        with ppsf:
            try:
                params = ppsf.get_params()
                params["mode"] = pps_tools.data.PPS_CAPTUREASSERT
                ppsf.set_params(**params)
            except Exception as e:
                self.get_logger().error(f"Failed to configure PPS params: {e}")
                return

            self.get_logger().info(f"Opened {self.pps_device} — waiting for PPS events")

            saw_assert = False
            last_warn = 0.0
            last_edge = time.time()
            pub_count = 0

            while not self.stop_evt.is_set():
                try:
                    # 2-second timeout so we wake up and check stop_evt regularly
                    edge = ppsf.fetch(timeout=2)
                except Exception as e:
                    if self.stop_evt.is_set():
                        break
                    self.get_logger().warn(f"PPS fetch: {e}")
                    continue

                now = time.time()

                if edge is None:
                    # No-edge timeout: fire watchdog if we haven't warned recently
                    if not saw_assert or (now - last_warn > self.watchdog_interval):
                        self.get_logger().warn(
                            "No PPS edge received. Is the PWM generator running?"
                            f" (last edge {now - last_edge:.1f}s ago)"
                        )
                        last_warn = now
                    continue

                saw_assert = True
                last_edge = now
                last_warn = 0.0  # reset so next gap triggers immediately

                t = Time()
                t.sec = edge.assert_tu.sec
                t.nanosec = edge.assert_tu.nsec
                self.pub.publish(t)

                pub_count += 1
                self.get_logger().debug(
                    f"PPS edge #{pub_count}: {t.sec}.{t.nanosec:09d}"
                )

        self.get_logger().info(f"PPS device {self.pps_device} closed")
        self.get_logger().info("PPS reader thread exiting")

    def destroy_node(self):
        self.stop_evt.set()

        # Stop PWM generator
        if self.pwm_proc is not None:
            rc = self.pwm_proc.poll()
            if rc is not None:
                self.get_logger().info(
                    f"PWM generator already exited (rc={rc})"
                )
            else:
                try:
                    self.pwm_proc.terminate()
                    self.pwm_proc.wait(timeout=3.0)
                    self.get_logger().info("PWM generator stopped")
                except subprocess.TimeoutExpired:
                    self.pwm_proc.kill()
                    self.pwm_proc.wait()
                    self.get_logger().warn("PWM generator killed (did not stop in time)")
                except Exception:
                    pass

        self.th.join(timeout=3.0)
        super().destroy_node()


def main():
    rclpy.init()
    node = PpsTimePub()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
