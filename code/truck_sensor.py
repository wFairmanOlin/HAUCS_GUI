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
from converter import convert_mgl_to_percent, convert_percent_to_mgl, to_fahrenheit, to_celcius

from firebase_worker import FirebaseWorker

class TruckSensor(QThread):
    update_data = pyqtSignal(dict) 
    status_data = pyqtSignal(str)
    logger_data = pyqtSignal(dict)
    counter_is_running = pyqtSignal(str)
    update_pond_data = pyqtSignal(dict)
    finished = pyqtSignal()

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

    is_30sec = False
    data_size_at30sec = 30
    sample_stop_time = 30

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

    def init_ysi(self):
        self.ysi_worker = YSIReader()
        self.ysi_worker.YSI_folder = self.YSI_folder
        self.ysi_worker.logger_data.connect(self.on_logger_update)
        self.ysi_worker.initialize()
        self.ysi_worker.start()

    def stop_ysi(self):
        self.ysi_worker.abort()
        self.ysi_worker.wait()

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

    def restart_firebase(self, in_app):
        logging.info('Attempting to restart Firebase Connection')
        if in_app is not None:
            firebase_admin.delete_app(in_app)
            sleep(60)
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
        update_sdata, update_json, update_logger, update_status, msg, sdata_key = self.ble.run_connection_first()
        if msg:
            self.status_data.emit("Sensor Connection complete")

        self.update_sdata_value(sdata_key)
        self.update_logger_value(update_logger)

    def init_sensor_status(self):
        update_sdata, update_json, update_logger, update_status, msg, sdata_key = self.ble.set_calibration_pressure()
        self.update_logger_text("info", f"Calibration Pressure complete")

        msgs = []
        update_sdata, update_json, update_logger, update_status, msg, sdata_key = self.ble.get_init_do()
        tell_status = update_status
        tell_logger = update_logger
        self.update_any(sdata_key, update_json)
        msgs.append(msg)

        update_sdata, update_json, update_logger, update_status, msg, sdata_key = self.ble.get_init_pressure()
        tell_status |= update_status
        tell_logger |= update_logger
        self.update_any(sdata_key, update_json)
        msgs.append(msg)

        update_sdata, update_json, update_logger, update_status, msg, sdata_key = self.ble.get_battery()
        tell_status |= update_status
        tell_logger |= update_logger
        self.update_any(sdata_key, update_json)
        msgs.append(msg)

        self.update_status_value(tell_status)
        self.update_logger_value(tell_logger)
        
        return msgs

    def reconnection(self, just_reconnect):
        update_sdata, update_json, update_logger, update_status, msg, sdata_key = self.ble.reconnect()
        if update_sdata is None:
            return True
        self.update_any(sdata_key, update_json)
        self.update_status_value(update_status)
        if update_logger is not None and just_reconnect:
            self.update_logger_value(update_logger)
        return msg

    def update_gps(self):
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
        
    def calibrate_DO(self):
        self.msleep(1000)
        update_sdata, update_json, update_logger, update_status, msg, sdata_key = self.ble.set_calibration_do()
        self.update_logger_text("info", f"Calibration DO complete")
        self.status_data.emit("Calibration DO complete")
        self.msleep(1000)

    def run(self):
        self._abort = False
        while self.ble is None or not self.ble.check_connection_status():
            self.init_ble()
            self.msleep(2500)
            msgs = self.init_sensor_status()
            self.update_logger_text("info", f"Initialize sensor, get init_do, init_pressure, battery")
        # print(msgs)
        self.update_gps()

        counter = 0
        check_batt_counter = 0
        connection_count = 0
        just_reconnect = False
        underwater_alert = False

        # reset all buffer in system
        update_sdata, update_json, update_logger, update_status, msg, sdata_key = self.ble.set_sample_reset()

        # self.restore_unsaved_from_json()

        while not self._abort:
            # self.update_logger_text("info", f"abort {self._abort}")
            connected = self.ble.check_connection_status()
            if not connected:
                if connection_count == 0:
                    self.is_30sec = False
                    self.status_data.emit("BLE connect failed - maybe underwater, on Collecting data")
                    data_dict = {}
                    data_dict['connection'] = self.ble.sdata['connection']
                    self.update_data.emit(data_dict)
                    self.counter_is_running.emit("True")
                    self.ysi_worker.set_record()
                    self.update_logger_value(True)
                connection_count += 1
                just_reconnect = True

            connected = self.reconnection(just_reconnect)
            if not connected:
                self.msleep(500)
                continue

            if just_reconnect:
                data_dict = {}
                data_dict['connection'] = self.ble.sdata['connection']
                self.update_data.emit(data_dict)
            just_reconnect = False
            connection_count = 0

            counter += 1
            check_batt_counter += 1

            self.update_gps()

            if check_batt_counter >= 5:
                check_batt_counter = 0
                update_sdata, update_json, update_logger, update_status, msg, sdata_key = self.ble.get_battery()
                self.update_any(sdata_key, update_json)
                self.update_status_value(update_status)
                self.update_logger_value(update_logger)
                self.msleep(100)

            # read until buffer size stable
            if self.ble.prev_sample_size <= 0 or self.ble.current_sample_size > self.ble.prev_sample_size:
                update_sdata, update_json, update_logger, update_status, msg, sdata_key = self.ble.get_sample_size()
                # self.status_data.emit("prev " + str(self.ble.prev_sample_size) + " current " + str(self.ble.current_sample_size) + " step " + str(counter))
                # print("prev " + str(self.ble.prev_sample_size) + " current " + str(self.ble.current_sample_size) + " step " + str(counter))
                if self.is_30sec:
                    self.data_size_at30sec = self.ble.current_sample_size
                if self.ble.current_sample_size > 0 and self.ble.prev_sample_size <= 0 and not underwater_alert:
                    self.update_logger_text("info", f"Sensor is underwater, while still connecting. {self.ble.current_sample_size} {self.ble.prev_sample_size}")
                    underwater_alert = True
                    self.is_30sec = False
                if self.ble.current_sample_size > self.ble.prev_sample_size and self.ble.current_sample_size > 0:
                    self.ysi_worker.set_record()
                    self.counter_is_running.emit("True")
                    self.status_data.emit("Collecting data")
                    just_reconnect = False
                    self.msleep(500)
                    continue
                elif self.ble.current_sample_size <= 0 and just_reconnect:
                    self.ysi_worker.stop_record(reset=True)
                    self.counter_is_running.emit("False, overground")
                    self.update_logger_text("warning", "Sensor has been reconnect over water, check bluetooth sensor")
                    just_reconnect = False
                    self.is_30sec = False
                    continue
                elif self.ble.current_sample_size == self.ble.prev_sample_size and self.ble.current_sample_size > 0:
                    self.status_data.emit("data is ready, starting to read")
                else:
                    continue
            just_reconnect = False
            underwater_alert = False
            self.ysi_worker.stop_record()
            self.counter_is_running.emit("False")
            self.msleep(500)

            message_time = time.strftime('%Y%m%d_%H:%M:%S', time.gmtime()) #GMT time
            self.sdata['message_time'] = message_time

            update_sdata, update_json, update_logger, update_status, msg, sdata_key = self.ble.get_sample_text(self.is_30sec, self.data_size_at30sec, self.sample_stop_time)
            if self.ble.logger_status == "warning":
                self.update_logger_text(self.ble.logger_status, self.ble.logger_string)
            self.status_data.emit("Read data finished")
            self.pond_id, self.latitude, self.longitude = self.gps.get_GPS_pond()
            self.update_any(sdata_key, update_json, True, True)

            do_val = self.ble.sdata["do"]
            self.update_logger_text("info", f"Data collected: {self.pond_id}, DO:{do_val}")
            self.csv_file = self.ble.csv_file
            self.msleep(100)
            update_sdata, update_json, update_logger, update_status, msg, sdata_key = self.ble.set_sample_reset()
            self.update_logger_text("info", f"Reset sample")
            counter = 0
            
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
                time_stop = len(self.data_dict["do_vals"])
                self.water_temp = to_celcius(self.data_dict["temp"][0])
                self.pressure = self.data_dict["pressure"][0]
                self.do_val = self.data_dict["do"]
                self.ysi_v = self.ysi_worker.get_record(time_stop)
                self.ysi_csv = self.ysi_worker.csv_file
                self.ysi = convert_mgl_to_percent(self.ysi_v, self.water_temp, self.pressure)
                self.update_logger_text("info", f"YSI value: {self.ysi_v} mgl and {self.ysi} %")
                if self.unit == "percent":
                    self.data_dict["ysi"] = self.ysi
                else:
                    self.data_dict["ysi"] = self.ysi_v
                self.sdata["ysi_do"] = self.ysi
                self.sdata["ysi_v"] = self.ysi_v

                self.data_dict = self.check_unit()

                self.update_pond_data.emit(self.data_dict)
            self.update_data.emit(self.data_dict)

    def toggle_unit(self, unit):
        self.unit = unit
        self.data_dict = self.check_unit()
        self.update_data.emit(self.data_dict)

    def check_unit(self):
        def safe_convert(key):
            if key in self.sdata:
                try:
                    if key == "ysi_do":
                        val = float(self.sdata[key])  # ตรวจสอบว่าเป็นตัวเลขได้
                        self.data_dict["ysi"] = convert_percent_to_mgl(val, self.water_temp, self.pressure)
                    else:
                        val = float(self.sdata[key])  # ตรวจสอบว่าเป็นตัวเลขได้
                        self.data_dict[key] = convert_percent_to_mgl(val, self.water_temp, self.pressure)
                except (ValueError, TypeError):
                    pass  # ข้ามถ้าแปลงไม่ได้ (ไม่ใช่ตัวเลข)

        def safe_transfer(key):
            if key in self.sdata:
                try:
                    val = float(self.sdata[key])  # ตรวจสอบว่าเป็นตัวเลขได้
                    if key == "ysi_do":
                        self.data_dict["ysi"] = val
                    else:
                        self.data_dict[key] = val
                except (ValueError, TypeError):
                    pass  # ข้ามถ้าแปลงไม่ได้ (ไม่ใช่ตัวเลข)

        if self.unit == "mgl":
            safe_convert("do")
            safe_convert("ysi_do")
        else:
            safe_transfer("do")
            safe_transfer("ysi_do")

        return self.data_dict

    def update_logger_value(self, update_logger):
        if update_logger:
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

    def update_status_value(self, update_status):
        if update_status:
            self.status_data.emit(self.ble.status_string)

    def update_database(self, data_dict):
        truck_id = self.truck_id
        pid = data_dict["pid"]
        do_val = round(self.sdata.get("do", ""), 2)
        ysi_val = round(self.sdata.get("ysi_do", ""), 2)
        temp_val = round(self.sdata.get("temp", "")[0], 2)
        press_val = round(self.sdata.get("pressure", "")[0], 2)
        csv_file = self.csv_file
        message_time = self.sdata['message_time']
        self.sdata["pid"] = pid
        time_str = datetime.now().strftime("%H:%M:%S")

        # ข้อมูลแถวเดียวที่ต้องบันทึก
        row = {
            "time": time_str,
            "Pond ID": pid,
            "HBOI DO": do_val,
            "YSI DO": ysi_val,
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

