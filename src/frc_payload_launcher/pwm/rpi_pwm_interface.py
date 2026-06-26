#!/usr/bin/env python3

from rpi_hardware_pwm import HardwarePWM


if __name__ == '__main__':
    pwm = HardwarePWM(pwm_channel=0, hz=30, chip=2)
    pwm.start(100)  # full duty cycle

    pwm.change_duty_cycle(10)
    pwm.change_frequency(3)

    # pwm.stop()  # sets duty cycle to 0
