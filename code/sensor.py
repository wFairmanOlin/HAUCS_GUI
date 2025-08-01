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

class I2CReader(QThread):
    ysi_publisher = pyqtSignal(float)
    gps_publisher = pyqtSignal(dict)

    #TODO the following values should NOT be hardcoded
    FULL_SCALE = 10500
    ZERO_SCALE = 0
    FULL_MSG = 15

    # accessed externally
    underwater          = False # True if underwater, set by truck_sensor.py


    # accessed internally
    reconnect_period = 5 # Time in seconds to retry reconnection

    ysi_connected = False       # True if ADC initialized
    ysi_reconnect_timer = 0     # Stores the last time a reconnect attempt was made
    ysi_sampling_period = 1     # Modified to match BLE sensor 

    def __init__(self):
        super().__init__()
        self._abort = False

        # I2C Bus
        i2c = board.I2C()
        
        # initialize YSI (ADS1x15) Sensor
        self.ysi_adc = ADS1x15.ADS1115(1)
        # initialize GPS sensor
        self.gps = GPSSensor(i2c, timeout=2)

        # initialize message schedule
        self.scheduled_msgs = {}
        self.scheduled_msgs['gps_signal']    = {'callback':self.publish_gps, 'period':10, 'timer':0, 'underwater':False}
        self.scheduled_msgs['gps_update']    = {'callback':self.gps.update, 'period':5, 'timer':0, 'underwater':False}
        self.scheduled_msgs['ysi']    = {'callback':self.measure_ysi_adc, 'period':self.ysi_sampling_period, 'timer':0, 'underwater':True}
        

    def send_scheduled_messages(self):
        if self.messaging_active:
            for message in self.scheduled_msgs.values():
                if time.time() - message['timer'] > message['period']:
                    message['timer'] = time.time()
                    # only trigger callback if above water or message has underwater priority
                    if not self.underwater or message['underwater']:
                        message['callback']()

    def init_ysi_adc(self):
        try:
            self.ysi_adc = ADS1x15.ADS1115(1)
            self.ysi_adc.setGain(16)
            self.ysi_connected = True
        except Exception as error:
            self.ysi_connected = False



    def measure_ysi_adc(self):
        try:
            val = self.ysi_adc.readADC_Differential_0_1()
        except:
            val = 0
            self.ysi_connected = False
        
        # perform voltage to mgl conversion
        do_mgl = self.FULL_MGL * (val - self.ZERO_SCALE) / (self.FULL_SCALE - self.ZERO_SCALE)
        # set to zero if less than zero
        do_mgl = 0 if do_mgl < 0 else do_mgl

        # publish YSI data
        self.ysi_data.emit(do_mgl)
        return do_mgl

    def set_ysi_sample_rate(self, sample_hz):
        self.ysi_sampling_period = int(1/sample_hz)
        self.scheduled_msgs['ysi']['period'] = self.ysi_sampling_period
    
    def get_gps_data(self):
        '''
        Returns the following signal
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
                }

        return data

    def publish_gps(self):
        '''
        updates pyqt signal for gps. rate set in message scheduler
        '''
        self.gps_publisher.emit(self.get_gps_data())


    def run(self):
        self._abort = False
        
        while not self._abort:

            # reconnect ysi sensor
            if not self.ysi_connected:
                if time.time() - self.ysi_reconnect_timer > self.reconnect_period:
                    self.ysi_reconnect_timer = time.time()
                    self.init_ysi_adc()
            
            # perform sensor updates
            self.send_scheduled_messages()


    def abort(self):
        self.logger_data.emit("info", "Stop YSI normal process")
        self._abort = True