import os
from PyQt5.QtCore import QThread, pyqtSignal, QObject
import pandas as pd
from datetime import datetime
import numpy as np
import shutil
from gpiozero.pins.pigpio import PiGPIOFactory
import csv
import time
from converter import *
from gps_sensor import GPSSensor
import board
import adafruit_bno055
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import logging
from enum import Enum
from functools import total_ordering
from bno055.bno055 import Compass

# init logger
logger = logging.getLogger(__name__)


@total_ordering
class Priority(Enum):
    low = 0
    medium = 1
    high = 2

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented


class I2CReader(QThread):
    ysi_publisher = pyqtSignal(float, float)
    gps_publisher = pyqtSignal(dict)
    calibration_publisher = pyqtSignal(dict)

    full_scale = 10500
    zero_scale = 0
    FULL_MGL = 15

    # accessed externally
    underwater = False  # True if underwater, set by truck_sensor.py
    message_priority = (
        Priority.low
    )  # Indicates the minimum level needed to run a message

    # accessed internally
    reconnect_period = 5  # Time in seconds to retry reconnection

    ysi_connected = False  # True if ADC initialized
    ysi_reconnect_timer = 0  # Stores the last time a reconnect attempt was made
    ysi_sampling_period = 1  # Modified to match BLE sensor

    def __init__(self, calibration):
        super().__init__()
        self._abort = False

        # store calibration dict
        self.set_ysi_calibration(
            calibration.get("ysi_zero_scale", self.zero_scale),
            calibration.get("ysi_full_scale", self.full_scale),
        )
        # I2C Bus
        self.i2c = board.I2C()
        # initialize YSI (ADS1x15) Sensor
        self.init_ysi_adc()
        logger.debug(
            f"initializing ysi adc, sensor {'' if self.ysi_connected else 'not'} found"
        )
        # initialize GPS sensor
        self.gps = GPSSensor(self.i2c, timeout=2)
        # initialize BNO055
        self.compass = Compass(self.i2c, calibration)
        # initialize message schedule
        self.scheduled_msgs = {}
        self.scheduled_msgs["gps"] = {
            "callback": self.publish_gps,
            "period": 2,
            "timer": 0,
            "priority": Priority.high,
        }
        self.scheduled_msgs["ysi"] = {
            "callback": self.measure_ysi_adc,
            "period": self.ysi_sampling_period,
            "timer": 0,
            "priority": Priority.high,
        }
        self.scheduled_msgs["hdg_offset"] = {
            "callback": self.update_heading_offset,
            "period": 10,
            "timer": time.monotonic(),
            "priority": Priority.low
        }
        self.scheduled_msgs["cal_save"] = {
            "callback": self.save_imu_calibration,
            "period": 10, #TODO: 2 minutes
            "timer": time.monotonic(),
            "priority": Priority.low
        }

    def send_scheduled_messages(self):
        for message in self.scheduled_msgs.values():
            if time.monotonic() - message["timer"] > message["period"]:
                message["timer"] = time.monotonic()
                # only trigger callback if above water or message has underwater priority
                if message["priority"] >= self.message_priority:
                    message["callback"]()

    def set_schedule(self, name, callback, period, priority):
        """
        Add message callback to sensor message scheduler
        name: name of message (needs to be called to remove schedule)
        underwaterFlag: runs when sensor is underwater (True/False)
        """
        if not period.isnumeric():
            logger.error(f"sensor set schedule failed {name}")
        else:
            msg = {
                "callback": callback,
                "period": period,
                "timer": 0,
                "priority": priority,
            }
            self.scheduled_msgs[name] = msg

    def remove_schedule(self, name):
        if name in self.scheduled_msgs:
            del self.scheduled_msgs[name]
        else:
            logger.warning(f"could not find {name} in message schedule")

    def set_ysi_sample_rate(self, sample_hz):
        self.ysi_sampling_period = float(1 / sample_hz)
        self.scheduled_msgs["ysi"]["period"] = self.ysi_sampling_period

    def set_ysi_calibration(self, zero, full_scale):
        self.zero_scale = zero
        self.full_scale = full_scale

    def init_ysi_adc(self):
        try:
            self.ysi_adc = ADS.ADS1115(self.i2c, gain=16)
            self.ysi_chan = AnalogIn(self.ysi_adc, ADS.P0, ADS.P1)
            self.ysi_connected = True
        except Exception as e:
            self.ysi_connected = False
            logger.debug("could not intialize ADC: %s", e)

    def measure_ysi_adc(self):
        try:
            val = self.ysi_chan.value
        except:
            val = 0
            self.ysi_connected = False

        # perform voltage to mgl conversion
        do_mgl = (
            self.FULL_MGL
            * (val - self.zero_scale)
            / (self.full_scale - self.zero_scale)
        )
        # set to zero if less than zero
        do_mgl = 0 if do_mgl < 0 else do_mgl
        self.ysi_publisher.emit(do_mgl, val)
        return do_mgl, val
    
    def publish_gps(self):
        """
        Publishes and returns the following signal
        lat: latitude
        lng: longitude
        hdg: gps heading (prefer imu)
        hdg_type: gps or imu
        pid: pond id
        nsat: number of satellites in view
        spd: speed kmh
        """
        self.gps.update()
        self.compass.update()

        data = {
            "lat": self.gps.latitude,
            "lng": self.gps.longitude,
            "pid": self.gps.pond_id,
            "nsat": self.gps.numsat,
            "spd": self.gps.speed_kmh,
        }
        # add IMU heading if available
        if self.compass.offset_heading != None:
            data["hdg"] = self.compass.offset_heading
            data["hdg_type"] = "imu"
        # otherwise fallback to GPS headning
        else:
            data["hdg"] = self.gps.heading
            data["hdg_type"] = "gps"

        logger.debug(f"gps data {data}")
        self.gps_publisher.emit(data)
        return data

    def update_heading_offset(self):
        self.gps.update()
        self.compass.check_and_calibrate_heading(self.gps.speed_kmh, self.gps.heading)

    def save_imu_calibration(self):
        data = self.compass.get_calibration()
        self.calibration_publisher.emit(data)

    def run(self):
        self._abort = False

        while not self._abort:
            self.msleep(50)
            # reconnect ysi sensor
            if not self.ysi_connected:
                if time.monotonic() - self.ysi_reconnect_timer > self.reconnect_period:
                    self.ysi_reconnect_timer = time.monotonic()
                    self.init_ysi_adc()

            # perform sensor updates
            self.send_scheduled_messages()

    def abort(self):
        self._abort = True


if __name__ == "__main__":
    i2c = board.I2C()
    sensor = adafruit_bno055.BNO055_I2C(i2c)
    while True:
        print(f"Accelerometer (m/s^2): {sensor.acceleration}")
        print(f"Magnetometer (microteslas): {sensor.magnetic}")
        print(f"Gyroscope (rad/sec): {sensor.gyro}")
        print(f"Euler angle: {sensor.euler}")
        print(f"Quaternion: {sensor.quaternion}")
        print(f"Linear acceleration (m/s^2): {sensor.linear_acceleration}")
        print(f"Gravity (m/s^2): {sensor.gravity}")
        print(f"  Offsets_Magnetometer:  {sensor.offsets_magnetometer}")
        print(f"  Offsets_Gyroscope:     {sensor.offsets_gyroscope}")
        print(f"  Offsets_Accelerometer: {sensor.offsets_accelerometer}")
        print()

        time.sleep(1)
