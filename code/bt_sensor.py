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
from converter import convert_mgl_to_raw, convert_raw_to_mgl, to_fahrenheit, to_celcius

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
    prev_sample_size = 0
    do_vals = []
    temp_vals = []
    pressure_vals = []
    do = 0
    temp_val = 0
    pressure_val = 0
    csv_file = None

    do_vals_log = "DO_data/"

   # dictionary of commands (tx) and expected retunrs (rx)
    commands = {
        'init_do': {'tx':'get init_do', 'rx':'init_do'},
        'init_ps': {'tx':'get init_p', 'rx':'init_p'},
        'battery': {'tx':'batt', 'rx':'v'},
        's_reset': {'tx':'sample reset', 'rx':''},
        's_size' : {'tx':'sample size', 'rx':'dsize'},
        's_print': {'tx':'sample print', 'rx':'dstart', 'end':'dfinish'},
        'cal_do' : {'tx':'cal do', 'rx':'init do'},
        'cal_ps' : {'tx':'cal ps', 'rx':'init p'},
        'xmas'   : {'tx':'set light xmas', 'rx':''},
        's_rate' : {'tx':'get sample_hz', 'rx':'sample_hz'},
    }

    ################## logger #########################
    logger_status = "normal"
    logger_string = ""

    def update_logger(self, logger_status, logger_string):
        self.logger_status = logger_status
        self.logger_string = logger_string

    def call_logger(self):
        return self.logger_status, self.logger_string
    ################ end logger #######################

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
                print(f"found sensor with UART service {adv.complete_name}")
                self.uart_connection = self.ble.connect(adv)
                if self.uart_connection.connected:
                    self.status_string = "connected to: " + adv.complete_name
                    self.sensor_name = adv.complete_name
                    self.sdata['name'] = adv.complete_name[9:]
                    return True   
        self.ble.stop_scan()
        return False

    def run_connection_first(self):
        # os.popen('sudo hciconfig hci0 reset')
        # self.status_string = "doing hciconfig hci0 reset"
        # time.sleep(5)
        if self.connect():
            self.send_receive_command(self.commands['xmas'])
            self.connection_status = "connected"
            self.sdata['connection'] = self.connection_status
            self.update_logger("info", 'first time connected to the payload (boot up)')
            update_json, msg = True, True
            return update_json, msg, ['name', 'connection']
        else:
            self.update_logger("warning", "BLE connect failed")
            #fails['ble'] += 1
            self.status_string = "BLE connect failed"
            self.connection_status = "not connected"
            self.sdata['connection'] = self.connection_status
        update_json, msg = False, False
        return update_json, msg, None

    def check_connection_status(self):
        # prioritize status from uart connection 
        connected = False
        if not (self.uart_connection and self.uart_connection.connected):
            self.update_logger("warning", "BLE connect failed - maybe underwater")
            self.connection_status = "not connected"
            self.sdata['connection'] = self.connection_status
            self.previous_connect = False
        # use timeouts to predict disconnect
        elif self.transmission_timeouts > 0:
            self.update_logger("warning", "BLE transmission timeout - maybe disconnected")
            self.connection_status = "not connected"
            self.sdata['connection'] = self.connection_status
            self.previous_connect = False
        # sensor is connected
        else:
            connected = True
        return connected

    def reconnect(self):
        if not (self.uart_connection and self.uart_connection.connected):
            update_json = False
            if self.sdata.get('connection') != "not connected":
                self.connection_status = "not connected"
                self.sdata['connection'] = self.connection_status
                self.previous_connect = False
                update_json = True
                
            self.status_string = "trying to reconnect"
            if self.connect():
                self.connection_status = "connected"
                self.sdata['connection'] = self.connection_status
                update_json = True
                if not self.previous_connect:
                    self.update_logger("info", 'reconnect after disconnect - finished sampling and re-emerge')
                    self.previous_connect = True
                # self.check_size = 1
                msg = True
                return update_json, msg, ['connection']
            else:
                self.update_logger("warning", "BLE connect failed - maybe underwater")
                #fails['ble'] += 1
                self.status_string = "BLE connect failed - maybe underwater"
                msg = False
                return update_json, msg, ['connection']

        else: # do nothing
            update_json, msg = None, None
            return update_json, msg, None

    def get_init_do(self):
        self.sdata["init_do"] = 0
        update_json = False
        msg = self.send_receive_command(self.commands['init_do'])
        return update_json, msg, ["init_do"]

    def get_init_pressure(self):
        self.sdata["init_pressure"] = 0
        update_json = False
        msg = self.send_receive_command(self.commands['init_ps'])
        return update_json, msg, ["init_pressure"]
    
    def get_sampling_rate(self):
        self.sdata["sample_hz"] = 1
        update_json = False
        msg = self.send_receive_command(self.commands['s_rate'])
        return update_json, msg, ["sample_hz"]

    def get_battery(self):
        update_json = True
        msg = self.send_receive_command(self.commands['battery'])
        return update_json, msg, ['battv', 'batt_status']

    def set_sample_reset(self):
        update_json = False
        msg = self.send_receive_command(self.commands['s_reset'])
        self.prev_sample_size = 0
        self.current_sample_size = 0
        return update_json, msg, None

    def get_sample_size(self):
        return self.send_receive_command(self.commands['s_size'])

    def get_sample_text(self):
        update_json = True
        msg = self.send_receive_command(self.commands['s_print'], timeout=5)
        keys = ["init_do", "init_pressure", 'battv', 'batt_status', "do_vals", "temp_vals", "pressure_vals", "sample_hz", 'name']
        return update_json, msg, keys
    
    def set_calibration_pressure(self):
        return self.send_receive_command(self.commands['cal_ps']) 

    def set_calibration_do(self):
        return self.send_receive_command(self.commands['cal_do'])
    
    def set_threshold(self, hpa):
        command = {'tx':f"set threshold {int(hpa)}", 'rx':'threshold'}
        self.send_receive_command(command)


    def extract_message(self, msg):
        #TODO: break this into individual callbacks for each message
        # print(f"extract: {msg}")
        key, value = msg[0], msg[1:]
        if key == "init_do":
            self.init_do_val = float(value[0].strip())
            self.sdata["init_do"] = self.init_do_val
        elif key == "init_p":
            self.init_p_val = float(value[0].strip())
            self.sdata["init_pressure"] = self.init_p_val

        elif key == 'v' and len(value) == 3:
            self.batt_v = float(value[0])
            self.batt_status = value[2].strip()
            self.sdata['battv'] = self.batt_v
            self.sdata['batt_status'] = self.batt_status
        elif key == 'sample_hz':
            self.sdata['sample_hz'] = float(value[0])
        elif key == "dsize":
            self.prev_sample_size = self.current_sample_size
            try:
                self.current_sample_size = int(value[0])
            except:
                print(f"failed to get sample size, msg: {value[0]}")
        elif key == "dstart":
            self.prev_sample_size = self.current_sample_size
            self.current_sample_size = int(value[0].strip())
            self.csv_file = self.init_csv_file()
            self.data_counter = 0
            self.do_vals = []
            self.temp_vals = []
            self.pressure_vals = []

        elif key == "ts":
            try:
                do = float(value[2])
                temp_val = float(value[4])
                pressure_val = float(value[6])
            except:
                do = 0
                temp_val = 0
                pressure_val = 0
                
            if self.csv_file is not None:
                self.writeCSV(self.csv_file, [float(value[0]), do, temp_val, pressure_val])

            self.do_vals.append(do) # DO
            self.temp_vals.append(temp_val)   # tempuerature 
            self.pressure_vals.append(pressure_val) # pressure
            self.data_counter = self.data_counter + 1  

        elif "dfinish" in key:

            self.sdata["init_do"] = self.init_do_val
            self.sdata['battv'] = self.batt_v
            self.sdata['batt_status'] = self.batt_status
            self.sdata["do_vals"] = self.do_vals
            self.sdata["temp_vals"] = self.temp_vals
            self.sdata["pressure_vals"] = self.pressure_vals

    def send_receive_command(self, command, timeout=1):
        '''
        Returns imediately if not connected
        '''
        start_time = time.time()
        if not self.uart_connection:
            return ""
        if not self.uart_connection.connected:
            return ""
        
        #handle commands with multiple responses expected
        multiple_outputs = "end" in command
        receiving_array = False

        uart_service = self.uart_connection[UARTService]
        msg = "" # return nothing if tx only
        uart_service.write((command['tx'] + "\n").encode())
        while len(command['rx']) > 0:
            # check timeout
            if (time.time() - start_time > timeout):
                self.transmission_timeouts += 1
                return ""
            # wait till buffer has something
            if not uart_service.in_waiting:
                continue
            msg = uart_service.readline().decode()
            msg = msg.replace("\n","")
            msg = msg.lower()
            msg = msg.split(",")
            if len(msg) >= 1:
                # handle first response
                if msg[0] == command['rx']:
                    receiving_array = True
                    self.extract_message(msg)
                    # break if only one output
                    if not multiple_outputs:
                        break
                # handle other responses
                elif receiving_array:
                    self.extract_message(msg)
                    if msg[0] == command.get("end"):
                        break
        # reset transmission timeouts on successfull transmission 
        self.transmission_timeouts = 0
        return msg

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