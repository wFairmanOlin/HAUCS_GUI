from PyQt5.QtCore import QThread, pyqtSignal
from bt_sensor import BluetoothReader
import json, logging
from gps_sensor import GPS_sensor
from datetime import datetime
import time
import pandas as pd
import os
import firebase_admin
from firebase_admin import credentials,db
import concurrent.futures
from ysi_reader import YSIReader
from converter import convert_mgl_to_raw, convert_raw_to_mgl, to_fahrenheit, to_celcius

from firebase_worker import FirebaseWorker

class TruckSensor(QThread):
    update_data = pyqtSignal(dict) 
    status_data = pyqtSignal(str)
    logger_data = pyqtSignal(dict)
    counter_is_running = pyqtSignal(str)
    update_pond_data = pyqtSignal(dict)
    finished = pyqtSignal()
    ysi_data = pyqtSignal(float, float)

    _abort = False
    sdata = {}
    sdatas = []
    data_dict = {}
    sensor_file = "sensor.json"

    latitude = 0
    longitude = 0
    pond_id = 0

    ble = None
    csv_file = ""

    app = None
    cred = None
    fail_counter = 0

    messaging_active = True #semaphore for scheduled messages

    is_30sec = False
    data_size_at30sec = 30
    sample_stop_time = 30
    underwater = False

    water_temp = 0 # celcius
    pressure = 0 # HPA
    do_val = 0 # percent
    ysi_val = 0 # percent
    ysi_csv = ""
    ysi = 0
    ysi_v = 0

    max_fail = 30
    truck_id = "truck1"
    fb_key="fb_key.json"
    database_folder = "database_truck"
    log_folder = "log/"
    do_vals_log = "DO_data/"
    unsaved_json = "unsaved_json"
    completed_upload = "completed_json"
    YSI_folder = "YSI_data/"
    unit = "mgl"

    def __init__(self, parent=None):
        super().__init__(parent)
        
    
    def initialize(self):
        date = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')

        if not os.path.exists(self.log_folder):
            os.makedirs(self.log_folder)

        logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', filename=f"{self.log_folder}log_{date}.log", encoding='utf-8',
                    level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.update_logger_text("info", 'DO Sensor Starting')
        self.init_GPS()
        self.init_ysi()
        self.init_firebase()
        # initialzie PyQt Signals
        self.counter_is_running.connect(self.underwater_status)

    def init_ysi(self):
        self.ysi_worker = YSIReader()
        self.ysi_worker.YSI_folder = self.YSI_folder
        self.ysi_worker.logger_data.connect(self.on_logger_update)
        self.ysi_worker.ysi_data.connect(self.on_ysi_update)
        self.ysi_worker.initialize()
        self.ysi_worker.start()

    def stop_ysi(self):
        self.ysi_worker.abort()
        self.ysi_worker.wait()

    def on_ysi_update(self, do_mgl):
        #TODO: delete this function. Should be directly connected to gui02.py
        if self.water_temp and self.pressure:
            do_ps = convert_mgl_to_raw(do_mgl, self.water_temp, self.presssure)
            self.ysi_data.emit(do_ps, do_mgl)
        else:
            self.ysi_data.emit(-1, do_mgl)

    def init_firebase(self):
        self.firebase_worker = FirebaseWorker()
        self.firebase_worker.max_fail = self.max_fail
        self.firebase_worker.truck_id = self.truck_id
        self.firebase_worker.fb_key = self.fb_key
        self.firebase_worker.database_folder = self.database_folder
        self.firebase_worker.unsaved_json = self.unsaved_json
        self.firebase_worker.completed_upload = self.completed_upload
        self.firebase_worker.logger_data.connect(self.on_logger_update)
        self.firebase_worker.init_firebase()
        self.firebase_worker.start()

    def stop_firebase(self):
        self.firebase_worker.abort()
        self.firebase_worker.wait()

    def on_logger_update(self, level, msg):
        self.update_logger_text(level, msg)

    def underwater_status(self, value):
        if value == "True":
            self.underwater = True
            self.ysi_worker.set_record()
        else:
            self.underwater = False

        print(f"I am {'' if self.underwater else 'not'} underwater!")
        
    

    def restart_firebase(self, in_app):
        logging.info('Attempting to restart Firebase Connection')
        if in_app is not None:
            firebase_admin.delete_app(in_app)
            time.sleep(60)
        if os.path.exists(self.fb_key) and self.cred is None:
            self.cred = credentials.Certificate(self.fb_key)
            self.update_logger_text("warning", 'Firebase initialize failed, no fb_key')
        if self.cred is not None:
            new_app = firebase_admin.initialize_app(self.cred,
                                                {'databaseURL': 'https://haucs-monitoring-default-rtdb.firebaseio.com'})
            return new_app
        return None

    def init_GPS(self):
        self.gps = GPS_sensor()
        print("connect gps")
        self.sdata["prev_pid"] = "unk25"
        self.sdata["pid"] = "unk25"
        self.update_logger_text("info", 'GPS Starting')

    def init_ble(self):
        self.ble = BluetoothReader()
        self.ble.do_vals_log = self.do_vals_log
        print("connect ble")
        update_json, msg, sdata_key = self.ble.run_connection_first()
        if msg:
            self.status_data.emit("Sensor Connection complete")

        self.update_sdata_value(sdata_key)
        self.update_logger_value()

    def init_sensor_status(self):
        self.ble.set_calibration_pressure()
        self.update_logger_text("info", f"Calibration Pressure complete")

        msgs = []
        update_json, msg, sdata_key = self.ble.get_init_do()
        self.update_any(sdata_key, update_json)
        msgs.append(msg)

        update_json, msg, sdata_key = self.ble.get_init_pressure()
        self.update_any(sdata_key, update_json)
        msgs.append(msg)

        self.update_battery()
        
        return msgs
    
    def update_battery(self):
        #TODO: This function should be removed
        update_json, msg, sdata_key = self.ble.get_battery()
        self.update_any(sdata_key, update_json)

    
    def init_message_scheduler(self):
        self.scheduled_msgs = {}
        self.scheduled_msgs['s_size'] = {'callback':self.ble.get_sample_size, 'period':1.1, 'timer':0}
        self.scheduled_msgs['batt']   = {'callback':self.update_battery, 'period':10, 'timer':0}
        self.scheduled_msgs['gps']    = {'callback':self.update_gps, 'period':10, 'timer':0}

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
        self.status_data.emit(self.ble.status_string)
        if just_reconnect:
            self.update_logger_value()
        return msg

    def update_gps(self):
        gps_time = time.time()
        self.pond_id, self.latitude, self.longitude = self.gps.get_GPS_pond()
        self.sdata["prev_pid"] = self.sdata["pid"]
        self.sdata["pid"] = self.pond_id
        data_dict = {}
        data_dict["gps"] = True
        data_dict["pid"] = self.pond_id
        data_dict["lng"] = self.longitude
        data_dict["lat"] = self.latitude
        self.update_data.emit(data_dict)
        if self.sdata["prev_pid"] != self.sdata["pid"]:
            self.update_logger_text("info", f"move to pond ID: {self.pond_id}")
            print(self.pond_id, self.longitude, self.latitude)
        
        print(f"{self.latitude} {self.longitude}")
        print(f"gps update time: {round(time.time() - gps_time, 2)}")
        
    def calibrate_DO(self):
        self.ble.set_calibration_do()
        self.update_logger_text("info", f"Calibration DO complete")
        self.status_data.emit("Calibration DO complete")

    def run(self):
        self._abort = False
        
        # Wait for First Connection
        while self.ble is None or not self.ble.check_connection_status():
            self.init_ble()
            self.msleep(500)
            self.init_sensor_status()
            self.update_logger_text("info", f"Initialize sensor, get init_do, init_pressure")

        self.init_message_scheduler()

        connection_count = 0
        just_reconnect = False

        # reset all buffer in system
        self.ble.set_sample_reset()

        # Main Loop
        while not self._abort:

            # self.msleep(1) # do nothing for Alisa

            # ADD NONE-BLE SENSOR UPDATES FIRST

            connected = self.ble.check_connection_status()
            if not connected:
                # first disconnect event
                if connection_count == 0:
                    self.is_30sec = False
                    self.status_data.emit("BLE connection failed - maybe underwater")
                    data_dict = {'connection' : self.ble.sdata['connection']}
                    self.update_data.emit(data_dict)
                    print("counter started because sensor lost connection")
                    self.counter_is_running.emit("True")
                    self.update_logger_value()
                # do not try to reconnect for first 1500 ms
                elif connection_count > 15:
                    connected = self.reconnection(just_reconnect)
                # continue if still not conneted
                if not connected:
                    connection_count += 1
                    self.msleep(100)
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
                        self.is_30sec = False
                        self.update_logger_text("info", f"Sensor is underwater, while still connected. {self.ble.current_sample_size} {self.ble.prev_sample_size}")
                    # tag 30 scecond mark
                    if self.is_30sec:
                        self.data_size_at30sec = self.ble.current_sample_size #TODO: probably delete this
                    continue # continue sampling

            # THE FOLLOWING ONLY RUNS WHEN DATA HAS BEEN COLLECTED
            self.status_data.emit("data is ready, starting to read")
            self.ysi_worker.stop_record()
            print("counter stopped because sensor reconnected with data available")
            self.counter_is_running.emit("False")

            message_time = time.strftime('%Y%m%d_%H:%M:%S', time.gmtime()) #GMT time
            self.sdata['message_time'] = message_time

            update_json, msg, sdata_key = self.ble.get_sample_text(self.is_30sec, self.data_size_at30sec, self.sample_stop_time)
            if self.ble.logger_status == "warning":
                self.update_logger_text(self.ble.logger_status, self.ble.logger_string)
            self.status_data.emit("Read data finished")
            self.pond_id, self.latitude, self.longitude = self.gps.get_GPS_pond()
            self.update_any(sdata_key, update_json, True, True)

            do_val = self.ble.sdata["do"]
            self.update_logger_text("info", f"Data collected: {self.pond_id}, DO:{do_val}")
            self.csv_file = self.ble.csv_file
            
            update_json, msg, sdata_key = self.ble.set_sample_reset()
            self.update_logger_text("info", f"Reset sample")
            
        self.update_logger_text("info", f"ble thread abort {self._abort}")
        self.finished.emit()

    def abort(self):
        self.update_logger_text("info", "Stop ble normal process")
        self._abort = True

    def update_any(self, sdata_key, update_json, update_pond_data = False, update_gps = False):
        self.update_sdata_value(sdata_key, update_pond_data, update_gps)
        self.save_json(update_json)

    def save_json(self, update_json):
        if update_json:
            with open(self.sensor_file, 'w') as outfile:
                json.dump(self.sdata, outfile)

    def update_sdata_value(self, sdata_key, update_pond_data = False, update_gps = False):
        if sdata_key is not None:
            self.data_dict = {}
            for key in sdata_key:
                # print(key)
                # print(self.ble.sdata[key])
                if key in self.ble.sdata:
                    self.sdata[key] = self.ble.sdata[key]
                    self.data_dict[key] = self.sdata[key]
                if key == 'lat':
                    self.data_dict['gps'] = True

            if update_gps:
                self.sdata["pid"] = self.pond_id
                self.sdata['lng'] = self.longitude
                self.sdata['lat'] = self.latitude
                self.data_dict["gps"] = True
                self.data_dict["pid"] = self.pond_id
                self.data_dict["lng"] = self.longitude
                self.data_dict["lat"] = self.latitude

            if update_pond_data:
                #TODO: This breaks when sampling rate is less than 1
                time_stop = len(self.data_dict["do_vals"])
                self.water_temp = to_celcius(self.data_dict["temp"][0])
                self.pressure = self.data_dict["pressure"][0] #TODO: Make sure this is init pressure
                self.do_val = self.data_dict["do"]
                self.ysi_mgl_array = self.ysi_worker.get_record()
                self.ysi_csv = self.ysi_worker.csv_file
                self.ysi = convert_mgl_to_raw(self.ysi_mgl_array[-1], self.water_temp, self.pressure)
                self.update_logger_text("info", f"YSI value: {self.ysi_mgl_array[-1]} mgl and {100 * self.ysi} %")
                #TODO: CHANGE WHERE SDATA YSI_DO_MGL IS UDPATED
                self.sdata["ysi_do"] = self.ysi
                self.sdata["ysi_do_mgl"] = self.ysi_mgl_array[-1]
                self.data_dict['ysi_do'] = self.sdata['ysi_do']
                self.data_dict['ysi_do_mgl'] = self.sdata['ysi_do_mgl']
                self.data_dict['do'] = self.sdata['do']
                self.data_dict['do_mgl'] = self.sdata['do_mgl']

                self.update_pond_data.emit(self.data_dict)
            self.update_data.emit(self.data_dict)

    def toggle_unit(self, unit):
        #TODO: this function should be removed
        self.unit = unit
        self.data_dict['do'] = self.sdata.get('do',0)
        self.data_dict['do_mgl'] = self.sdata.get('do_mgl',0)
        self.data_dict['ysi_do'] = self.sdata.get('ysi_do',0)
        self.data_dict['ysi_do_mgl'] = self.sdata.get('ysi_do_mgl',0)
        self.data_dict['ysi'] = self.sdata.get('ysi_do_mgl',0) # remove this variable
        self.update_data.emit(self.data_dict)
        print(f"NEW_UNIT: {self.unit}")
        print(f"SDATA\n {self.sdata}")
        print(f"DATA DICT\n{self.data_dict}")

    def update_logger_value(self):
        log = {}
        log["status"] = self.ble.logger_status
        log["message"] = self.ble.logger_string
        print(self.ble.logger_status, self.ble.logger_string)
        if log["status"] == "info":
            self.logger.info(log["message"])
        elif log["status"] == "warning":
            self.logger.warning(log["message"])
        self.logger_data.emit(log)

    def update_logger_text(self, logger_status, logger_string):
        log = {}
        log["status"] = logger_status
        log["message"] = logger_string
        if log["status"] == "info":
            self.logger.info(log["message"])
        elif log["status"] == "warning":
            self.logger.warning(log["message"])
        self.logger_data.emit(log)

    def update_database(self, data_dict):
        #TODO: data_dict is not really used
        truck_id = self.truck_id
        pid = data_dict["pid"]
        do_val = round(self.sdata.get("do", ""), 2)
        do_mgl_val = round(self.sdata.get("do_mgl", -1), 2)
        ysi_do = round(self.sdata.get("ysi_do", -1), 2)
        ysi_do_mgl = round(self.sdata.get("ysi_do_mgl", -1), 2)
        temp_val = round(self.sdata.get("temp", [-1])[0], 2)
        press_val = round(self.sdata.get("pressure", [-1])[0], 2)
        csv_file = self.csv_file
        message_time = self.sdata['message_time']
        self.sdata["pid"] = pid
        time_str = datetime.now().strftime("%H:%M:%S")

        row = {
            "time": time_str,
            "Pond ID": pid,
            "HBOI DO": do_val,
            "HBOI DO MGL":do_mgl_val,
            "YSI DO": ysi_do,
            "YSI DO MGL": ysi_do_mgl,
            "Temperature": temp_val,
            "Pressure": press_val,
            "do csv": csv_file,
            "upload status": False,
            "message_time": message_time,
            "ysi csv": self.ysi_csv
        }

        self.update_logger_text("info", f"upload DO value to database: {pid}, {do_val}")

        self.firebase_worker.add_sdata(self.sdata, csv_file, row)

    def tricker_30sec(self):
        self.is_30sec = True

