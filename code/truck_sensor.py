from PyQt5.QtCore import QThread, pyqtSignal
from bt_sensor import BluetoothReader
import json, logging
from datetime import datetime
import time
import pandas as pd
import os
import firebase_admin
from firebase_admin import credentials,db
import concurrent.futures
from sensor import I2CReader
from converter import *
import numpy as np
from enum import Enum
import sensor

from firebase_worker import FirebaseWorker

import logging
logger = logging.getLogger(__name__)

class Mode(Enum):
    normal = 0
    ysi_cal = 1

class TruckSensor(QThread):
    update_data = pyqtSignal(dict) 
    sensor_underwater = pyqtSignal(str)
    update_pond_data = pyqtSignal(dict)
    ysi_data = pyqtSignal(float, float)

    _abort = False
    sdata = {'pid':'unk25', 'prev_pid':'unk25', 'do':0, 'do_mgl':0, 'ysi_do':0, 'ysi_do_mgl':0}

    ble = None
    app = None
    cred = None

    messaging_active = True #semaphore for scheduled messages
    mode = Mode.normal #handles special operating modes
    underwater = False

    # environment variables
    water_temp = 0    # celcius
    air_pressure = 0  # HPA
    unit = "mgl"      # mgl or percent

    fb_key="fb_key.json"
    database_folder = "database_truck"


    def __init__(self, calibration, settings, parent=None):
        super().__init__(parent)
        # initialize firebase
        self.init_firebase()
        self.calibration = calibration
        self.settings = settings
        # initialize I2C sensor bus
        self.sensors = I2CReader(calibration)
        self.sensors.start()

        #internally accessed variables
        self.ysi_do_mgl_arr = []
        # initialzie PyQt Signals
        self.sensor_underwater.connect(self.underwater_status_change)
        self.sensors.gps_publisher.connect(self.on_gps_update)
        self.sensors.ysi_publisher.connect(self.on_ysi_update)

    # YSI COMMANDS
    def on_ysi_update(self, do_mgl, raw_adc):
        if self.water_temp and self.air_pressure:
            do_ps = convert_mgl_to_raw(do_mgl, self.water_temp, self.air_pressure)
        else:
            do_ps = -1
        # emit when in calibration mode
        if self.mode == Mode.ysi_cal:
            self.ysi_data.emit(raw_adc, raw_adc)
        # only emit data when underwater
        elif self.underwater:
            self.ysi_do_mgl_arr.append(do_mgl)
            self.ysi_data.emit(do_ps, do_mgl)
        

    def start_ysi_calibration(self, sample_hz):
        self.mode = Mode.ysi_cal
        self.sensors.set_ysi_sample_rate(sample_hz)
        self.sensors.message_priority = sensor.Priority.high
        
    def stop_ysi_calibration(self):
        self.mode = Mode.normal
        self.sensors.set_ysi_sample_rate(self.sdata['sample_hz'])
        self.sensors.message_priority = sensor.Priority.low
    
    def set_ysi_calibration(self, zero, full_scale):
        self.sensors.set_calibration(zero, full_scale)

    def init_firebase(self):
        self.firebase_worker = FirebaseWorker()
        self.firebase_worker.start()

    def stop_firebase(self):
        self.firebase_worker.abort()
        self.firebase_worker.wait()

    def underwater_status_change(self, value):
        if value == "True":
            self.underwater = True
            self.sensors.message_priority = sensor.Priority.high # only process high priority messages 
        else:
            self.underwater = False
            self.sensors.message_priority = sensor.Priority.low 


    def init_ble(self):
        self.ble = BluetoothReader()
        if self.ble.connect():
            self.sync_ble_sdata()
            self.ble.set_lights('navigation')
            logger.debug('connected to sensor, activated lights')

    def init_sensor_status(self):
        self.ble.set_calibration_pressure()
        logger.info("pressure calibration complete")

        self.ble.get_init_do()
        self.ble.get_init_pressure()
        self.ble.get_battery()
        self.ble.get_sampling_rate()
        self.ble.set_threshold(self.settings['depth_threshold'])

        self.sync_ble_sdata()

    def set_pressure_threshold(self, depth_in):
        threshold = depth_to_pressure(depth_in, 0)
        if not self.ble.set_threshold(threshold):
            logger.error(f"setting pressure threshold failed {threshold}")


    def init_message_scheduler(self):
        self.scheduled_msgs = {}
        self.scheduled_msgs['s_size'] = {'callback':self.ble.get_sample_size, 'period':1.1, 'timer':0}
        self.scheduled_msgs['batt']   = {'callback':self.ble.get_battery, 'period':10, 'timer':0}
        self.scheduled_msgs['sync']   = {'callback':self.sync_ble_sdata, 'period':15, 'timer':0}

    def send_scheduled_messages(self):
        if self.messaging_active:
            for message in self.scheduled_msgs.values():
                if time.time() - message['timer'] > message['period']:
                    message['timer'] = time.time()
                    message['callback']()


    def on_gps_update(self, data):
        self.sdata['prev_pid'] = self.sdata['pid']
        #update sdata with new gps data
        for key, val in data.items():
            self.sdata[key] = val

        self.sync_ble_sdata()
        if self.sdata["prev_pid"] != self.sdata["pid"]:
            logger.info(f"moved to pid: {self.sdata['pid']}")
        
    def calibrate_DO(self):
        status = self.ble.set_calibration_do()
        if status:
            logger.info("do calibration complete")
        else:
            logger.warning("do calibration failed")
        return status

    def run(self):
        self._abort = False
        
        # Wait for First Connection
        while self.ble is None or not self.ble.check_connection_status():
            self.init_ble()
            self.init_sensor_status()
            self.msleep(100)

        self.init_message_scheduler()

        connection_count = 0

        # reset all buffer in system
        self.ble.set_sample_reset()

        # create local connection variable
        connected = self.ble.check_connection_status()

        # Main Loop
        while not self._abort:

            self.msleep(50)

            # check if still connected
            if connected:
                connected = self.ble.check_connection_status()
                if not connected:
                    connection_count = 0
                    self.msleep(150)
                    continue
            # handle not connected case
            else:
                connected = self.ble.check_connection_status()
                if not connected:
                    # first disconnect event
                    if connection_count == 0:
                        logger.debug(f'sensor disconnected, connection count {connection_count}')
                        self.sensor_underwater.emit("True")
                        self.sync_ble_sdata()
                        
                    # do not try to reconnect for first 5000 ms
                    elif connection_count > 25:
                        logger.debug(f"attempting reconnect after waiting {connection_count * 200} ms")
                        connected = self.ble.reconnect()
                    # continue if still not connected
                    if not connected:
                        connection_count += 1
                        self.msleep(150)
                        continue
                # first reconnect
                else:
                    connection_count = 0
                    self.sync_ble_sdata()
            
            # RUNS WHEN SENSOR IS CONNECTED 

            self.send_scheduled_messages()
            # sensor is connected with no data
            if self.ble.current_sample_size <= 0:
                # sensor reconncected with no data available
                if self.underwater:
                    logger.info('sensor reconnected with no data, try again')
                    self.sensor_underwater.emit("False")
                self.ysi_do_mgl_arr = []
                continue # continue sampling
            # sensor has data
            elif self.ble.current_sample_size > 0:
                # sensor is actively collecting data
                if self.ble.prev_sample_size < self.ble.current_sample_size:
                    # underwater, trigger any underwater events
                    if not self.underwater:
                        self.sensor_underwater.emit("True")
                        logger.info('sensor is collecting data while connected')
                    continue # continue sampling

            # ignore sample sizes less than 4, reset ysi mgl array
            if self.ble.current_sample_size < 4:
                logger.warning(f"sensor reconnected with {self.ble.current_sample_size} data points, try again")
                if self.underwater:
                    self.sensor_underwater.emit("False")
                self.ble.set_sample_reset()
                self.ysi_do_mgl_arr = []

                continue
            
            # RUNS WHEN DATA IS AVAILABLE

            self.sensor_underwater.emit("False")

            message_time = time.strftime('%Y%m%d_%H:%M:%S', time.gmtime()) #GMT time
            self.sdata['message_time'] = message_time

            self.ble.get_sample_data()  # retrieve data 
            self.sync_ble_sdata()       # sync data to self.sdata
            self.generate_pond_data()   # start firebase/display routine
            self.ble.set_sample_reset() # reset sample buffer
            self.ysi_do_mgl_arr = []    # clear ysi data buffer
            # END MAIN LOOP

    def sync_ble_sdata(self):
        '''
        transfer all ble data to truck's sdata dict
        '''
        for key in self.ble.sdata:
            self.sdata[key] = self.ble.sdata[key]
        
        self.update_data.emit(self.sdata)


    def abort(self):
        self._abort = True

    def generate_pond_data(self):

        sample_duration = len(self.sdata['do_vals']) / self.sdata['sample_hz']
        self.sdata['sample_duration'] = sample_duration

        # IDEAL RECORD TIME FOR DATA
        record_time = 30 #TODO: this should be in setting.setting

        # water temperature
        self.water_temp = sum(self.sdata['temp_vals'])/len(self.sdata['temp_vals'])
        self.sdata['water_temp'] = self.water_temp
        # Pressure
        self.air_pressure = self.sdata['init_pressure']
        self.sdata['sample_pressure'] = sum(self.sdata['pressure_vals'])/len(self.sdata['pressure_vals'])
        self.sample_depth = pressure_to_depth(self.sdata['sample_pressure'], self.air_pressure)
        
        self.sdata['sample_depth'] = self.sample_depth

        #  HBOI DO
        do_arr = self.sdata['do_vals']
        p, f = calculate_do_fit(do_arr, record_time, self.sdata['sample_hz'])
        do_guess = generate_do(record_time, p, f)
        do = do_guess if do_guess > 0 else do_arr[-1]
        do_mgl_arr = convert_raw_to_mgl(do_arr, self.water_temp, self.air_pressure)
        do_mgl = convert_raw_to_mgl(do, self.water_temp, self.air_pressure)
        
        # YSI DO
        p, f = calculate_do_fit(self.ysi_do_mgl_arr,record_time, self.sdata['sample_hz'])
        do_guess = generate_do(record_time, p, f)
        ysi_do_mgl = do_guess if do_guess > 0 else self.ysi_do_mgl_arr[-1]
        ysi_do_arr = convert_mgl_to_raw(self.ysi_do_mgl_arr, self.water_temp, self.air_pressure)
        ysi_do = convert_mgl_to_raw(ysi_do_mgl, self.water_temp, self.air_pressure)

        #TODO: JUST RETURN SDATA
        
        self.sdata["ysi_do"] = ysi_do
        self.sdata["ysi_do_mgl"] = ysi_do_mgl
        self.sdata['do'] = do
        self.sdata['do_mgl'] = do_mgl
        self.sdata['do_mgl_arr'] = do_mgl_arr
        self.sdata['ysi_do_mgl_arr'] = self.ysi_do_mgl_arr
        self.sdata['ysi_do_arr'] = ysi_do_arr

        self.update_pond_data.emit(self.sdata)
        self.update_data.emit(self.sdata)

    def toggle_unit(self, unit):
        self.unit = unit
        self.sync_ble_sdata()

    def update_database(self, data_dict):
        '''
        Use argument data_dict instead of self.sdata because it may contain user-corrected variables
        '''
        time_str = datetime.now().strftime("%H:%M:%S")

        row = {
            "time": time_str,
            "pond_id": data_dict['pid'],
            "hboi_do": round(data_dict['do'],2),
            "hboi_do_mgl":round(data_dict['do_mgl'],2),
            "ysi_do": round(data_dict['ysi_do'],2),
            "ysi_do_mgl": round(data_dict['ysi_do_mgl'],2),
            "temperature": round(data_dict['water_temp'],2),
            "depth": round(data_dict['sample_depth'],2),
            "upload_status": False,
            "message_time": data_dict['message_time'],
        }
        self.firebase_worker.add_sdata(data_dict, row)

