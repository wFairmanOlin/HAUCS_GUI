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

from firebase_worker import FirebaseWorker

import logging
logger = logging.getLogger(__name__)

class TruckSensor(QThread):
    update_data = pyqtSignal(dict) 
    counter_is_running = pyqtSignal(str)
    update_pond_data = pyqtSignal(dict)
    ysi_data = pyqtSignal(float, float)

    _abort = False
    sdata = {'pid':'unk25', 'prev_pid':'unk25', 'do':0, 'do_mgl':0, 'ysi_do':0, 'ysi_do_mgl':0}
    data_dict = {}
    sensor_file = "sensor.json"

    ble = None
    csv_file = ""

    app = None
    cred = None
    fail_counter = 0

    messaging_active = True #semaphore for scheduled messages

    underwater = False

    # environment variables
    water_temp = 0    # celcius
    air_pressure = 0  # HPA
    unit = "mgl"      # mgl or percent

    max_fail = 30
    fb_key="fb_key.json"
    database_folder = "database_truck"
    log_folder = "log/"
    do_vals_log = "DO_data/"
    unsaved_json = "unsaved_json"
    completed_upload = "completed_json"

    def __init__(self, parent=None):
        super().__init__(parent)
        
    
    def initialize(self):
        date = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')

        logger.info('truck .py starting')
        self.init_firebase()

        # initialize I2C sensor bus
        self.sensors = I2CReader()
        self.sensors.start()

        #internally accessed variables
        self.ysi_do_mgl_arr = []

        # initialzie PyQt Signals
        self.counter_is_running.connect(self.underwater_status) #TODO underwaters status should trigger counter
        self.sensors.gps_publisher.connect(self.on_gps_update)
        self.sensors.ysi_publisher.connect(self.on_ysi_update)


    def on_ysi_update(self, do_mgl):
        if self.water_temp and self.air_pressure:
            do_ps = convert_mgl_to_raw(do_mgl, self.water_temp, self.air_pressure)
        else:
            do_ps = -1
        
        # only emit data when underwater
        if self.underwater:
            self.ysi_do_mgl_arr.append(do_mgl)
            self.ysi_data.emit(do_ps, do_mgl)

    def init_firebase(self):
        self.firebase_worker = FirebaseWorker()
        self.firebase_worker.max_fail = self.max_fail
        self.firebase_worker.completed_upload = self.completed_upload
        self.firebase_worker.init_firebase()
        self.firebase_worker.start()

    def stop_firebase(self):
        self.firebase_worker.abort()
        self.firebase_worker.wait()

    def underwater_status(self, value):
        if value == "True":
            self.underwater = True
            self.sensors.underwater = True
        else:
            self.underwater = False
            self.sensors.underwater = False


    def init_ble(self):
        self.ble = BluetoothReader()
        self.ble.do_vals_log = self.do_vals_log
        print("connect ble")
        update_json, msg, sdata_key = self.ble.run_connection_first()
        if msg:
            logger.info("Sensor Connection complete")

        self.update_sdata_value(sdata_key)

    def init_sensor_status(self):
        self.ble.set_calibration_pressure()
        logger.info("pressure calibration complete")

        update_json, msg, sdata_key = self.ble.get_init_do()
        self.update_any(sdata_key, update_json)

        update_json, msg, sdata_key = self.ble.get_init_pressure()
        self.update_any(sdata_key, update_json)

        self.update_battery()

        update_json, msg, sdata_key = self.ble.get_sampling_rate()
        self.update_any(sdata_key, update_json)

        self.ble.set_threshold(10) #TODO: ADD TO SETTING PAGE

    
    def update_battery(self):
        #TODO: This function should be removed
        update_json, msg, sdata_key = self.ble.get_battery()
        self.update_any(sdata_key, update_json)

    
    def init_message_scheduler(self):
        self.scheduled_msgs = {}
        self.scheduled_msgs['s_size'] = {'callback':self.ble.get_sample_size, 'period':1.1, 'timer':0}
        self.scheduled_msgs['batt']   = {'callback':self.update_battery, 'period':10, 'timer':0}

    def send_scheduled_messages(self):
        if self.messaging_active:
            for message in self.scheduled_msgs.values():
                if time.time() - message['timer'] > message['period']:
                    message['timer'] = time.time()
                    message['callback']()

    def reconnection(self, just_reconnect):
        update_json, msg, sdata_key = self.ble.reconnect()
        if sdata_key is None:
            return True
        self.update_any(sdata_key, update_json)
        if just_reconnect:
            pass #TODO
        return msg

    def on_gps_update(self, data):
        self.sdata['prev_pid'] = self.sdata['pid']

        #update sdata with new gps data
        for key, val in data.items():
            self.sdata[key] = val

        self.update_data.emit(data)
        if self.sdata["prev_pid"] != self.sdata["pid"]:
            logger.info(f"move to pond ID: {self.sdata['pid']}")
        
    def calibrate_DO(self):
        self.ble.set_calibration_do()
        logger.info("do calibration complete")

    def run(self):
        self._abort = False
        
        # Wait for First Connection
        while self.ble is None or not self.ble.check_connection_status():
            self.init_ble()
            self.init_sensor_status()
            self.msleep(100)

        self.init_message_scheduler()

        connection_count = 0
        just_reconnect = False

        # reset all buffer in system
        self.ble.set_sample_reset()

        # Main Loop
        while not self._abort:

            self.msleep(50)

            connected = self.ble.check_connection_status()
            if not connected:
                # first disconnect event
                if connection_count == 0:
                    logger.info('disconnect noticed')
                    data_dict = {'connection' : self.ble.sdata['connection']}
                    self.update_data.emit(data_dict)
                    self.counter_is_running.emit("True")
                # do not try to reconnect for first 5000 ms
                elif connection_count > 25:
                    connected = self.reconnection(just_reconnect)
                # continue if still not conneted
                if not connected:
                    connection_count += 1
                    self.msleep(150)
                    continue

            if just_reconnect:
                data_dict = {}
                data_dict['connection'] = self.ble.sdata['connection']
                self.update_data.emit(data_dict)
            just_reconnect = False
            connection_count = 0

            self.send_scheduled_messages()

            # sensor is connected with no data
            if self.ble.current_sample_size <= 0:
                # sensor reconncected with no data available
                if self.underwater:
                    print("sensor has no data, probably disconnected without going underwater")
                    self.counter_is_running.emit("False")
                continue # continue sampling
            # sensor has data
            elif self.ble.current_sample_size > 0:
                # sensor is actively collecting data
                if self.ble.prev_sample_size < self.ble.current_sample_size:
                    # underwater, trigger any underwater events
                    if not self.underwater:
                        print("underwater, trigger first time events")
                        self.counter_is_running.emit("True")
                        self.status_data.emit("Collecting Data")
                        logger.info('Sensor is underwater, while still connected')
                    continue # continue sampling

            # ignore sample sizes less than 4, reset ysi mgl array
            if self.ble.current_sample_size < 4:
                logger.warning("sensor reconnected without data")
                self.ble.set_sample_reset()
                self.ysi_do_mgl_arr = []
                continue

            self.counter_is_running.emit("False")

            message_time = time.strftime('%Y%m%d_%H:%M:%S', time.gmtime()) #GMT time
            self.sdata['message_time'] = message_time

            update_json, _, sdata_key = self.ble.get_sample_text()
            self.update_any(sdata_key, update_json, True)

            self.csv_file = self.ble.csv_file
            
            update_json, msg, sdata_key = self.ble.set_sample_reset()
            # END MAIN LOOP

    def abort(self):
        logger.warning("truck thread stopped")
        self._abort = True

    def update_any(self, sdata_key, update_json, update_pond_data = False):
        self.update_sdata_value(sdata_key, update_pond_data)
        self.save_json(update_json)

    def save_json(self, update_json):
        if update_json:
            with open(self.sensor_file, 'w') as outfile:
                json.dump(self.sdata, outfile)

    def update_sdata_value(self, sdata_key, update_pond_data = False):
        if sdata_key is not None:
            self.data_dict = {}
            for key in sdata_key:
                if key in self.ble.sdata:
                    self.sdata[key] = self.ble.sdata[key]
                    self.data_dict[key] = self.sdata[key]
                if key == 'lat':
                    self.data_dict['gps'] = True

            if update_pond_data:
                # sample duration
                sample_rate = self.sdata.get('sample_hz', 1)
                sample_duration = len(self.data_dict['do_vals']) / sample_rate
                self.data_dict['sample_hz'] = sample_rate
                self.data_dict['sample_duration'] = sample_duration

                # IDEAL RECORD TIME FOR DATA
                record_time = 30 #TODO: this should be in setting.setting

                # water temperature
                self.water_temp = sum(self.data_dict['temp_vals'])/len(self.data_dict['temp_vals'])
                self.data_dict['water_temp'] = self.water_temp
                # Pressure
                self.air_pressure = self.sdata['init_pressure']
                self.data_dict['sample_pressure'] = sum(self.sdata['pressure_vals'])/len(self.sdata['pressure_vals'])
                self.sample_depth = pressure_to_depth(self.data_dict['sample_pressure'], self.air_pressure)
                
                self.data_dict['sample_depth'] = self.sample_depth

                #  HBOI DO
                do_arr = self.data_dict['do_vals']
                p, f = calculate_do_fit(do_arr, record_time, sample_rate)
                do_guess = generate_do(record_time, p, f)
                do = do_guess if do_guess > 0 else do_arr[-1]
                do_mgl_arr = convert_raw_to_mgl(do_arr, self.water_temp, self.air_pressure)
                do_mgl = convert_raw_to_mgl(do, self.water_temp, self.air_pressure)
                
                # YSI DO
                p, f = calculate_do_fit(self.ysi_do_mgl_arr,record_time, sample_rate)
                do_guess = generate_do(record_time, p, f)
                ysi_do_mgl = do_guess if do_guess > 0 else self.ysi_do_mgl_arr[-1]
                ysi_do_arr = convert_mgl_to_raw(self.ysi_do_mgl_arr, self.water_temp, self.air_pressure)
                ysi_do = convert_mgl_to_raw(ysi_do_mgl, self.water_temp, self.air_pressure)

                #TODO: JUST RETURN SDATA
                
                self.sdata["ysi_do"] = ysi_do
                self.sdata["ysi_do_mgl"] = ysi_do_mgl
                self.sdata['do'] = do
                self.sdata['do_mgl'] = do_mgl
                self.data_dict['ysi_do'] = ysi_do
                self.data_dict['ysi_do_mgl'] = ysi_do_mgl
                self.data_dict['do'] = do
                self.data_dict['do_mgl'] = do_mgl
                self.data_dict['do_mgl_arr'] = do_mgl_arr
                self.data_dict['ysi_do_mgl_arr'] = self.ysi_do_mgl_arr
                self.data_dict['ysi_do_arr'] = ysi_do_arr
                self.data_dict["pid"] = self.sdata['pid']
                self.data_dict["lng"] = self.sdata['lng']
                self.data_dict["lat"] = self.sdata['lat']
                self.data_dict['hdg'] = self.sdata['hdg']
                self.data_dict['message_time'] = self.sdata['message_time']
 
                self.update_pond_data.emit(self.data_dict)

            self.update_data.emit(self.data_dict)

    def toggle_unit(self, unit):
        #TODO: this function should be removed
        self.unit = unit
        self.data_dict['do'] = self.sdata['do']
        self.data_dict['do_mgl'] = self.sdata['do_mgl']
        self.data_dict['ysi_do'] = self.sdata['ysi_do']
        self.data_dict['ysi_do_mgl'] = self.sdata['ysi_do_mgl']
        self.update_data.emit(self.data_dict)

    def update_database(self, data_dict):
        #TODO: data_dict is not really used
        csv_file = self.csv_file
        # data_dict['message_time'] = self.sdata['message_time']
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
            "do_csv": csv_file,
            "upload_status": False,
            "message_time": data_dict['message_time'],
        }
        self.firebase_worker.add_sdata(data_dict, row)

