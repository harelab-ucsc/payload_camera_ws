#!/usr/bin/env python3

from rpi_hardware_pwm import HardwarePWM
from time import sleep

#pwm = HardwarePWM(pwm_channel=0, hz=60, chip=0)
pwm = HardwarePWM(pwm_channel=0, hz=60)
pwm.start(50) # full duty cycle

pwm.change_frequency(10)

#sleep(15)

#pwm.stop()

