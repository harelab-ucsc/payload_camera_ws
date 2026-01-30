# #!/usr/bin/env python3
# import re
# import subprocess
# import threading

# import rclpy
# from rclpy.node import Node
# from builtin_interfaces.msg import Time


# class PpsTimePub(Node):
#     def __init__(self):
#         super().__init__("pps_time_pub")
#         self.pub = self.create_publisher(Time, "/pps/time", 10)

#         self.get_logger().info("Starting ppstest /dev/pps0 publisher...")
#         self.th = threading.Thread(target=self._run, daemon=True)
#         self.th.start()

#     def _run(self):
#         cmd = ["sudo", "ppstest", "/dev/pps0"]
#         assert_re = re.compile(r"assert\s+(\d+)\.(\d+)")

#         try:
#             proc = subprocess.Popen(
#                 cmd,
#                 stdout=subprocess.PIPE,
#                 stderr=subprocess.STDOUT,
#                 text=True,
#                 bufsize=1
#             )
#         except Exception as e:
#             self.get_logger().error(f"Failed to start ppstest: {e}")
#             return

#         for line in proc.stdout:
#             m = assert_re.search(line)
#             if not m:
#                 continue

#             sec_str, nsec_str = m.group(1), m.group(2)
#             nsec_str = (nsec_str + "0" * 9)[:9]

#             t = Time()
#             t.sec = int(sec_str)
#             t.nanosec = int(nsec_str)
#             self.pub.publish(t)

#         proc.wait()
#         self.get_logger().warn("ppstest exited; PPS publisher stopped")


# def main():
#     rclpy.init()
#     node = PpsTimePub()
#     try:
#         rclpy.spin(node)
#     except KeyboardInterrupt:
#         pass
#     finally:
#         node.destroy_node()
#         rclpy.shutdown()


# if __name__ == "__main__":
#     main()



# above is the old script 


#!/usr/bin/env python3
import re
import subprocess
import threading
import time

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

        # Script that *generates* the PPS pulses (your rpi_pwm_control.py)
        self.declare_parameter("pwm_script", "/home/pi4/rpi_pwm_control.py")
        self.declare_parameter("pwm_python", "python3")
        self.declare_parameter("start_pwm", True)
        self.declare_parameter("pwm_start_delay_s", 0.25)

        # Whether to run ppstest with sudo
        # (Recommended: fix perms so you can set this False)
        self.declare_parameter("use_sudo", True)

        self.pps_device = self.get_parameter("pps_device").value
        self.pps_topic = self.get_parameter("pps_topic").value

        # Re-create publisher on configured topic (if user overrides)
        if self.pps_topic != "/pps/time":
            self.pub = self.create_publisher(Time, self.pps_topic, 10)

        self.stop_evt = threading.Event()
        self.pwm_proc = None
        self.ppstest_proc = None

        self.get_logger().info(
            f"pps_time_pub starting. device={self.pps_device} topic={self.pps_topic}"
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
            except Exception as e:
                self.get_logger().error(f"Failed to start PWM generator script: {e}")
                # We continue anyway in case PPS is coming from elsewhere

            delay = float(self.get_parameter("pwm_start_delay_s").value)
            time.sleep(max(0.0, delay))

        # 2) Start ppstest
        use_sudo = bool(self.get_parameter("use_sudo").value)
        cmd = ["ppstest", self.pps_device]
        if use_sudo:
            cmd = ["sudo"] + cmd

        self.get_logger().info(f"Starting: {' '.join(cmd)}")

        # Matches lines like:
        # "source 0 - assert 1769636816.200814364, sequence: 22 - clear ..."
        assert_re = re.compile(r"assert\s+(\d+)\.(\d+)")

        try:
            self.ppstest_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            self.get_logger().error(f"Failed to start ppstest: {e}")
            return

        saw_assert = False
        last_warn = 0.0

        for line in self.ppstest_proc.stdout:
            if self.stop_evt.is_set():
                break

            # Helpful logging if it's timing out (your earlier error)
            if "Connection timed out" in line:
                now = time.time()
                if now - last_warn > 2.0:
                    self.get_logger().warn("ppstest: Connection timed out (no PPS edges yet)")
                    last_warn = now
                continue

            m = assert_re.search(line)
            if not m:
                continue

            saw_assert = True

            sec_str, nsec_str = m.group(1), m.group(2)
            nsec_str = (nsec_str + "0" * 9)[:9]  # pad/truncate to 9 digits

            t = Time()
            t.sec = int(sec_str)
            t.nanosec = int(nsec_str)
            self.pub.publish(t)

        # If ppstest exits
        try:
            rc = self.ppstest_proc.wait(timeout=1.0)
        except Exception:
            rc = None

        if not saw_assert:
            self.get_logger().warn(
                "ppstest exited (or stopped) without receiving any asserts. "
                "Likely PPS generation never started."
            )
        self.get_logger().warn(f"ppstest exited (rc={rc}); PPS publisher stopped")

    def destroy_node(self):
        self.stop_evt.set()

        # Stop ppstest
        if self.ppstest_proc is not None:
            try:
                self.ppstest_proc.terminate()
            except Exception:
                pass

        # Stop PWM generator script
        if self.pwm_proc is not None:
            try:
                self.pwm_proc.terminate()
            except Exception:
                pass

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

