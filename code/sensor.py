import os
from PyQt5.QtCore import QThread, pyqtSignal, QObject
import pandas as pd
from datetime import datetime
import numpy as np
import shutil
import ADS1x15
from gpiozero.pins.pigpio import PiGPIOFactory
import csv
import time
from converter import *
from gps_sensor import GPSSensor
import board
import adafruit_bno055
import logging
from enum import Enum
from functools import total_ordering

#init logger
logger = logging.getLogger(__name__)

@total_ordering
class Priority(Enum):
    low = 0
    high = 1
    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented

class I2CReader(QThread):
    ysi_publisher = pyqtSignal(float, float)
    gps_publisher = pyqtSignal(dict)

    full_scale = 10500
    zero_scale = 0
    FULL_MGL = 15

    # accessed externally
    underwater          = False # True if underwater, set by truck_sensor.py
    message_priority    = Priority.low # Indicates the minimum level needed to run a message


    # accessed internally
    reconnect_period = 5 # Time in seconds to retry reconnection

    ysi_connected = False       # True if ADC initialized
    ysi_reconnect_timer = 0     # Stores the last time a reconnect attempt was made
    ysi_sampling_period = 1     # Modified to match BLE sensor 

    def __init__(self, calibration):
        super().__init__()
        self._abort = False

        # store calibration dict
        self.set_calibration(calibration.get('ysi_zero_scale',self.zero_scale),
                             calibration.get('ysi_full_scale', self.full_scale))
        # I2C Bus
        i2c = board.I2C()
        
        # initialize YSI (ADS1x15) Sensor
        self.init_ysi_adc()
        logger.debug(f"initializing ysi adc, sensor {'' if self.ysi_connected else 'not'} found")
        # initialize GPS sensor
        self.gps = GPSSensor(i2c, timeout=2)
        # initialize BNO055
        try:
            self.imu = adafruit_bno055.BNO055_I2C(i2c)
        except Exception as error:
            logger.error(f'cannot initialize bno055: {error}')

        # initialize message schedule
        self.scheduled_msgs = {}
        self.scheduled_msgs['gps']    = {'callback':self.publish_gps, 'period':2, 'timer':0, 'priority':Priority.low}
        self.scheduled_msgs['ysi']    = {'callback':self.measure_ysi_adc, 'period':self.ysi_sampling_period, 'timer':0, 'priority':Priority.high}
        

    def send_scheduled_messages(self):
        for message in self.scheduled_msgs.values():
            if time.time() - message['timer'] > message['period']:
                message['timer'] = time.time()
                # only trigger callback if above water or message has underwater priority
                if message['priority'] >= self.message_priority:
                    message['callback']()

    def init_ysi_adc(self):
        try:
            self.ysi_adc = ADS1x15.ADS1115(1)
            self.ysi_adc.setGain(16)
            self.ysi_connected = True
        except:
            self.ysi_connected = False

    def measure_ysi_adc(self):
        try:
            val = self.ysi_adc.readADC_Differential_0_1()
        except:
            val = 0
            self.ysi_connected = False
        
        # perform voltage to mgl conversion
        do_mgl = self.FULL_MGL * (val - self.zero_scale) / (self.full_scale - self.zero_scale)
        # set to zero if less than zero
        do_mgl = 0 if do_mgl < 0 else do_mgl
        self.ysi_publisher.emit(do_mgl, val)
        return do_mgl, val

        
    def set_schedule(self, name, callback, period, underwaterFlag):
        """
        Add message callback to sensor message scheduler
        name: name of message (needs to be called to remove schedule)
        underwaterFlag: runs when sensor is underwater (True/False)
        """
        if not period.isnumeric():
            logger.error(f"sensor set schedule failed {name}")
        else:
            msg = {'callback':callback, 'period':period, 'timer':0, 'underwater':underwaterFlag}
            self.scheduled_msgs[name] = msg

    def remove_schedule(self, name):
        if name in self.scheduled_msgs:
            del self.scheduled_msgs[name]
        else:
            logger.warning(f"could not find {name} in message schedule")

    def set_ysi_sample_rate(self, sample_hz):
        self.ysi_sampling_period = float(1/sample_hz)
        self.scheduled_msgs['ysi']['period'] = self.ysi_sampling_period
    
    def set_calibration(self, zero, full_scale):
        self.zero_scale = zero
        self.full_scale = full_scale

    def publish_gps(self):
        '''
        Publishes and returns the following signal
        lat: latitude
        lng: longitude
        hdg: gps heading (not compass)
        pid: pond id
        nsat: number of satellites in view
        '''
        self.gps.update()
        data = {'lat':self.gps.latitude,
                'lng':self.gps.longitude,
                'hdg':self.gps.heading,
                'pid':self.gps.pond_id,
                'nsat':self.gps.numsat,
                'spd_kmh':self.gps.speed_kmh,
                }
        logger.debug(f"gps data {data}")
        self.gps_publisher.emit(data)
        return data

    def run(self):
        self._abort = False
        
        while not self._abort:
            self.msleep(50)
            # reconnect ysi sensor
            if not self.ysi_connected:
                if time.time() - self.ysi_reconnect_timer > self.reconnect_period:
                    self.ysi_reconnect_timer = time.time()
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
        print()

        time.sleep(1)