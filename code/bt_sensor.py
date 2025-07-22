from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService

import random, csv
import numpy as np
from scipy.optimize import curve_fit
import pandas as pd
import json, logging, time, os, sys
from time import sleep
from datetime import datetime
import subprocess
import serial
from subprocess import call
from converter import convert_mgl_to_percent, convert_percent_to_mgl, to_fahrenheit, to_celcius

from PyQt5.QtCore import QObject, QThread, pyqtSignal

class BluetoothReader(QObject):
    data_updated = pyqtSignal(dict)
    uart_connection = None
    status_string = ""
    sdata = {}
    init_do_val = 0
    init_p_val = 0
    batt_v = 0
    batt_status = "no batt"
    connection_status = "not connected"
    previous_connect = False
    sensor_name = "xyz"
    current_sample_size = -1
    prev_sample_size = -1
    do_vals = []
    temp_vals = []
    pressure_vals = []
    do_val = 0
    temp_val = 0
    pressure_val = 0
    csv_file = None

    is_30sec = False
    data_size_at30sec = 30
    sample_stop_time = 30

    do_vals_log = "DO_data/"
    msg_command = ["get init_do", 'get init_p', 'batt', 'sample reset', 'sample size', 'sample print', 'cal ps', 'cal do']

    ################## logger #########################
    logger_status = "normal"
    logger_string = ""

    def update_logger(self, logger_status, logger_string):
        self.logger_status = logger_status
        self.logger_string = logger_string

    def call_logger(self):
        return self.logger_status, self.logger_string
    ################ end logger #######################
    # all msg status will return update_sdata, update_json, update_logger, update_status, msg, sdata_key list

    def __init__(self, sensor_file="sensor.json"):
        super().__init__()
        self.ble = BLERadio()
        self._abort = False
        self.sensor_file = sensor_file
        #set a flag to indicate first time connect to the payload
        self.check_size = -1 # check the dsize
        self.batt_cnt = 0

    def connect(self):
        print("searching for sensor ...")
        for adv in self.ble.start_scan(ProvideServicesAdvertisement):
            #print('ble:'+adv.services)
            if UARTService in adv.services:
                self.uart_connection = self.ble.connect(adv)
                self.status_string = "connected to: " + adv.complete_name
                self.sensor_name = adv.complete_name
                self.sdata['name'] = adv.complete_name[9:]
                break
        self.ble.stop_scan()

    def run_connection_first(self):
        # os.popen('sudo hciconfig hci0 reset')
        # self.status_string = "doing hciconfig hci0 reset"
        # time.sleep(5)
        try:
            self.connect()
            self.send_sensor("set light xmas")
            self.connection_status = "connected"
            self.sdata['connection'] = self.connection_status
            self.update_logger("info", 'first time connected to the payload (boot up)')
            previous_connect = True
            update_sdata, update_json, update_logger, update_status, msg = True, True, True, True, True
            return update_sdata, update_json, update_logger, update_status, msg, ['name', 'connection']
        except:
            self.update_logger("warning", "BLE connect failed")
            #fails['ble'] += 1
            self.status_string = "BLE connect failed"
            self.connection_status = "not connected"
            self.sdata['connection'] = self.connection_status
        update_sdata, update_json, update_logger, update_status, msg = False, False, True, True, False
        return update_sdata, update_json, update_logger, update_status, msg, None

    def check_connection_status(self):
        if not (self.uart_connection and self.uart_connection.connected):
            self.update_logger("warning", "BLE connect failed - maybe underwater")
            self.connection_status = "not connected"
            self.sdata['connection'] = self.connection_status
            self.previous_connect = False
        return (self.uart_connection and self.uart_connection.connected)

    def reconnect(self):
        if not (self.uart_connection and self.uart_connection.connected):
            update_json = False
            if self.sdata.get('connection') != "not connected":
                self.connection_status = "not connected"
                self.sdata['connection'] = self.connection_status
                self.previous_connect = False
                update_json = True
                
            self.status_string = "trying to reconnect"
            try:
                self.connect()
                self.connection_status = "connected"
                self.sdata['connection'] = self.connection_status
                update_json = True
                if not self.previous_connect:
                    self.update_logger("info", 'reconnect after disconnect - finished sampling and re-emerge')
                    self.previous_connect = True
                # self.check_size = 1
                update_sdata, update_logger, update_status, msg = True, True, True, True
                return update_sdata, update_json, update_logger, update_status, msg, ['connection']
            except:
                self.update_logger("warning", "BLE connect failed - maybe underwater")
                #fails['ble'] += 1
                self.status_string = "BLE connect failed - maybe underwater"
                update_sdata, update_logger, update_status, msg = True, True, True, False
                return update_sdata, update_json, update_logger, update_status, msg, ['connection']

        else: # do nothing
            previous_connect = True
            update_sdata, update_json, update_logger, update_status, msg = None, None, None, None, None
            return update_sdata, update_json, update_logger, update_status, msg, None

    def get_init_do(self):
        self.sdata["init_do"] = 0
        update_sdata, update_json, update_logger, update_status = True, False, False, False
        msg = self.send_receive_command(self.msg_command[0])
        return update_sdata, update_json, update_logger, update_status, msg, ["init_do"]

    def get_init_pressure(self):
        self.sdata["init_pressure"] = 0
        update_sdata, update_json, update_logger, update_status = True, False, False, False
        msg = self.send_receive_command(self.msg_command[1])
        return update_sdata, update_json, update_logger, update_status, msg, ["init_pressure"]

    def get_battery(self):
        update_sdata, update_json, update_logger, update_status = True, True, False, False
        msg = self.send_receive_command(self.msg_command[2])
        return update_sdata, update_json, update_logger, update_status, msg, ['battv', 'batt_status']

    def set_sample_reset(self):
        update_sdata, update_json, update_logger, update_status = False, False, False, False
        msg = self.send_receive_command(self.msg_command[3])
        self.prev_sample_size = -1
        self.current_sample_size = 0
        return update_sdata, update_json, update_logger, update_status, msg, None

    def get_sample_size(self):
        update_sdata, update_json, update_logger, update_status = False, False, False, False
        msg = self.send_receive_command(self.msg_command[4])
        return update_sdata, update_json, update_logger, update_status, msg, None

    def get_sample_text(self, is_30sec = False, data_size_at30sec = 30, sample_stop_time = 30):
        self.is_30sec = is_30sec
        self.data_size_at30sec = data_size_at30sec
        self.sample_stop_time = sample_stop_time
        update_sdata, update_json, update_logger, update_status = True, True, True, True
        msg = self.send_receive_command(self.msg_command[5], True)
        keys = ["do", "init_do", "init_pressure", "pressure", "temp", 'battv', 'batt_status', "do_vals", "temp_vals", "pressure_vals"]
        return update_sdata, update_json, update_logger, update_status, msg, keys
    
    def set_calibration_pressure(self):
        update_sdata, update_json, update_logger, update_status = False, False, False, False
        msg = self.send_receive_command(self.msg_command[6])
        return update_sdata, update_json, update_logger, update_status, msg, None

    def set_calibration_do(self):
        update_sdata, update_json, update_logger, update_status = False, False, False, False
        msg = self.send_receive_command(self.msg_command[7])
        return update_sdata, update_json, update_logger, update_status, msg, None

    def extract_message(self, msg):
        key, value = msg[0], msg[1:]
        # print("key: ", key, len(key))
        # print(value)
        if key == "init_do":
            self.init_do_val = float(value[0].strip())
            self.sdata["init_do"] = self.init_do_val
        elif key == "init_p":
            self.init_p_val = float(value[0].strip())
            self.sdata["init_pressure"] = self.init_p_val
        elif msg[0] == 'v' and len(value) == 3:
            self.batt_v = float(value[0])
            self.batt_status = value[2].strip()
            self.sdata['battv'] = self.batt_v
            self.sdata['batt_status'] = self.batt_status
        elif key == "b'dsize":
            self.prev_sample_size = self.current_sample_size
            cleaned = value[0].split('\\n')[0]
            self.current_sample_size = int(cleaned)
        elif key == "dstart":
            self.prev_sample_size = self.current_sample_size
            self.current_sample_size = int(value[0].strip())
            self.csv_file = self.init_csv_file()
            self.data_counter = 0
            self.do_vals = []
            self.temp_vals = []
            self.pressure_vals = []
        elif "dfinish" in key:
            # print("DO val:")
            # print(self.do_vals)
            # print("Temp val:")
            # print(self.temp_vals)
            # print("Pressure val:")
            # print(self.pressure_vals)

            # arr = np.array(self.do_vals)
            # self.do_val = 100*arr[arr > 0].mean()
            if len(self.do_vals) > 30:
                self.do_vals = self.do_vals[:30]
            y_fit, x_plot, y_at_30, do_vals = self.calculate_do_and_fit(self.do_vals)
            self.do_val = y_at_30
            arr = np.array(self.temp_vals)
            self.temp_val = [float(arr.mean())]
            arr = np.array(self.pressure_vals)
            self.pressure_val = [float(arr.mean())]

            self.sdata["do"] = self.do_val
            self.sdata["init_do"] = self.init_do_val
            self.sdata["init_pressure"] = self.init_p_val
            self.sdata["pressure"] = self.pressure_val
            self.sdata["temp"] = self.temp_val
            self.sdata['battv'] = self.batt_v
            self.sdata['batt_status'] = self.batt_status
            self.do_vals = do_vals
            self.sdata["do_vals"] = self.do_vals
            self.sdata["temp_vals"] = self.temp_vals
            self.sdata["pressure_vals"] = self.pressure_vals

        elif key == "ts":
            do_val = float(value[2])
            temp_val = float(value[4])
            pressure_val = float(value[6])
            if self.csv_file is not None:
                self.writeCSV(self.csv_file, [float(value[0]), do_val, temp_val, pressure_val])

            self.do_vals.append(do_val) # DO
            temp_val = to_fahrenheit(temp_val)
            self.temp_vals.append(round(temp_val, 1))   # tempuerature 
            self.pressure_vals.append(pressure_val) # pressure
            self.data_counter = self.data_counter + 1  

    def send_receive_command(self, msg_command, until_no_str=False):
        self.send_sensor(msg_command)
        time.sleep(0.3)
        if until_no_str:
            summary_msg = []
            msg = self.read_sensor()
            # print(msg)
            msg = msg.split(",")
            self.extract_message(msg)

            while msg != "failed read, no connection":
                msg = self.read_sensor()
                msg = msg.split(",")
                self.extract_message(msg)
                if msg == "failed read, no connection" or "dfinish" in msg[0]:
                    break
                # summary_msg.append(msg)
                
            msg = summary_msg
        else:
            msg = self.read_sensor()
            if len(msg) > 0:
                #print(msg)
                msg = msg.split(",")
                self.extract_message(msg)
                return msg
        return ""

    def read_sensor(self):
        if self.uart_connection:
            uart_service = self.uart_connection[UARTService]
            if self.uart_connection.connected:
                outmsg = uart_service.readline().decode()
                return outmsg
        return "failed read, no connection"

    def send_sensor(self, inmsg):
        if self.uart_connection:
            # self.status_string = "sending: " + inmsg
            uart_service = self.uart_connection[UARTService]
            if self.uart_connection.connected:
                uart_service.write(inmsg.encode())
            else:
                print("failed to send")

    def writeCSV(self, ofile, data):
        with open(ofile,'a',newline='') as csvfile:
            writer = csv.writer(csvfile, delimiter=',')
            writer.writerow(data)

    def init_csv_file(self):
        #global folder
        try:
            header = ['time', 'do', 'temperature', 'pressure']
            filePath = self.do_vals_log
            date = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')

            if not os.path.exists(filePath):
                os.mkdir(filePath)

            csvFile = filePath + date + ".csv"

            with open(csvFile,'w',newline='') as csvfile:
                writer = csv.writer(csvfile, delimiter=',')
                writer.writerow(header)
        except Exception as e:
            print("Failed to create csv file {csvfile}", str(e))
            self.update_logger("warning", f"Failed to create csv file {csvfile} {str(e)}")

        return csvFile

    def exp_func(self, x, a, b, c):
        return a * np.exp(-b * x) + c

    # def calculate_do_and_fit(self, do_vals):
    #     is_30sec = self.is_30sec
    #     data_size_at30sec = self.data_size_at30sec
    #     sample_stop_time = self.sample_stop_time

    #     if is_30sec:
    #         s_vals = np.linspace(0, 30, data_size_at30sec)
    #     else:
    #         s_vals = np.linspace(0, sample_stop_time, len(do_vals))

    #     x_plot = np.linspace(0, 30, 100)
    #     y_fit = np.zeros_like(x_plot)
    #     y_at_30 = None

    #     try:
    #         popt, _ = curve_fit(self.exp_func, s_vals, do_vals)
    #         y_fit = self.exp_func(x_plot, *popt)
    #         y_at_30 = self.exp_func(30, *popt)
    #     except Exception as e:
    #         print("Curve fit failed:", e)
    #         y_fit = np.interp(x_plot, s_vals, do_vals)
    #         if 30 <= s_vals[-1]:
    #             y_at_30 = np.interp(30, s_vals, do_vals)
    #         else:
    #             y_at_30 = np.mean(do_vals)

    #     # print(f"y_fit at x=30s: {y_at_30}")
    #     return y_fit, x_plot, y_at_30, do_vals

    def calculate_do_and_fit(self, do_vals, max_time = 30):
        s_vals = np.arange(len(do_vals)) 

        x_plot = np.linspace(0, 30, 100)

        # default fallback
        y_fit = np.zeros_like(x_plot)
        y_at_30 = None

        try:
            popt, _ = curve_fit(self.exp_func, s_vals, do_vals)

            y_fit = self.exp_func(x_plot, *popt)

            y_at_30 = self.exp_func(30, *popt)

        except Exception as e:
            print("Curve fit failed:", e)

            # fallback: linear interpolation (ถ้ามีข้อมูลน้อย)
            y_fit = np.interp(x_plot, s_vals, do_vals)

            if 30 <= s_vals[-1]:
                y_at_30 = np.interp(30, s_vals, do_vals)
            else:
                y_at_30 = np.mean(do_vals)

        # print(f"y_fit at x=30s: {y_at_30}")
        return y_fit, x_plot, y_at_30, do_vals