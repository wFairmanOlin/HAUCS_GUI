from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService

import random
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

#init logger
logger = logging.getLogger(__name__)

class BluetoothReader(QObject):
    data_updated = pyqtSignal(dict)
    uart_connection = None
    sdata = {'connection':False, 'name':'generic', 'sample_hz':1}
    current_sample_size = 0
    prev_sample_size = 0


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

    def __init__(self, *args):
        super().__init__()
        self.ble = BLERadio()
        self._abort = False

    def connect(self):
        logger.debug('starting ble scan')
        for adv in self.ble.start_scan(ProvideServicesAdvertisement):
            if UARTService in adv.services:
                logger.debug(f"found sensor with UART service {adv.complete_name}")
                try:
                    self.uart_connection = self.ble.connect(adv)
                    if self.uart_connection.connected:
                        self.sensor_name = adv.complete_name
                        self.sdata['name'] = adv.complete_name[9:]
                        self.sdata['connection'] = True
                        logger.debug(f"successfully connected to {adv}")
                        return True   
                except:
                    logger.error(f'failed to connect to {adv}')

        self.ble.stop_scan()
        self.sdata['connection'] = False
        return False

    def check_connection_status(self):
        connected = False
        if not (self.uart_connection and self.uart_connection.connected):
            if self.sdata['connection']:
                logger.debug("uart_connection.connected triggered not connected status in check_connection_status")
        # use timeouts to predict disconnect
        elif self.transmission_timeouts > 0:
            if self.sdata['connection']:
                logger.debug("send_receive timeout triggered not connected status")
        # sensor is connected
        else:
            if self.sdata['connection'] == False:
                logger.info('sdata reported disconnected but uart_connection.connected is true')
            connected = True
        self.sdata['connection'] = connected
        return connected

    def reconnect(self):
        if not (self.uart_connection and self.uart_connection.connected):
            if self.sdata['connection'] != False:
                logger.info('sdata reported connected while uart_connection.connected is false')
                self.sdata['connection'] = False
            return self.connect()
        
        logger.debug('reconnect attempted, already connected, do nothing')
        return True

    def get_init_do(self):
        self.sdata["init_do"] = 0
        self.send_receive_command(self.commands['init_do'])
        return self.sdata['init_do']

    def get_init_pressure(self):
        self.sdata["init_pressure"] = 0
        self.send_receive_command(self.commands['init_ps'])
        return self.sdata['init_pressure']
    
    def get_sampling_rate(self):
        self.sdata["sample_hz"] = 1
        self.send_receive_command(self.commands['s_rate'])
        return self.sdata['sample_hz']
    
    def get_battery(self):
        self.send_receive_command(self.commands['battery'])
        return self.sdata['battv'], self.sdata['batt_status']
    
    def get_sample_size(self):
        return self.send_receive_command(self.commands['s_size'])
    
    def set_sample_reset(self):
        self.send_receive_command(self.commands['s_reset'])
        self.prev_sample_size = 0
        self.current_sample_size = 0



    def get_sample_data(self):
        msg = self.send_receive_command(self.commands['s_print'], timeout=5)
        return msg == 'dfinish'
    
    def set_calibration_pressure(self):
        return self.send_receive_command(self.commands['cal_ps']) 

    def set_calibration_do(self):
        msg = self.send_receive_command(self.commands['cal_do'])
        if len(msg) > 0:
            if msg[0] == self.commands['cal_do']['rx']:
                return True
        return False
    
    def set_threshold(self, hpa):
        command = {'tx':f"set threshold {int(hpa)}", 'rx':'threshold'}
        msg = self.send_receive_command(command)
        try:
            received_p = float(msg[1])
        except:
            received_p = 0
        if msg[0] == command['rx'] and received_p == int(hpa):
            return True
        return False

    def set_lights(self, pattern):
        command = {'tx':f"set light {pattern}", 'rx':''}
        self.send_receive_command(command)


    def extract_message(self, msg):
        #TODO: break this into individual callbacks for each message
        key, value = msg[0], msg[1:]
        try:
            if key == "init_do":
                self.sdata["init_do"] = float(value[0].strip())

            elif key == "init_p":
                self.sdata["init_pressure"] = float(value[0].strip())

            elif key == 'v' and len(value) == 3:
                self.sdata['battv'] = float(value[0])
                self.sdata['batt_status'] = value[2].strip()

            elif key == 'sample_hz':
                self.sdata['sample_hz'] = float(value[0])

            elif key == "dsize":
                self.prev_sample_size = self.current_sample_size
                self.current_sample_size = int(value[0])         

            elif key == "dstart":
                self.prev_sample_size = self.current_sample_size
                self.current_sample_size = int(value[0].strip())
                self.data_counter = 0
                self.sdata["do_vals"] = []
                self.sdata["temp_vals"] = []
                self.sdata["pressure_vals"] = []

            elif key == "ts":
                try:
                    do = float(value[2])
                    temp_val = float(value[4])
                    pressure_val = float(value[6])
                except:
                    logger.warning(f'data corrupted in ble transfer {key, value}')
                    do = 0
                    temp_val = 0
                    pressure_val = 0

                self.sdata['do_vals'].append(do)
                self.sdata["temp_vals"].append(temp_val)
                self.sdata["pressure_vals"].append(pressure_val)
                self.data_counter = self.data_counter + 1  

            elif "dfinish" in key:
                # compare data counter to current sample size
                if self.data_counter != self.current_sample_size:
                    logger.warning(f"size mismatch between data collected on sensor and data received: {self.current_sample_size} vs. {self.data_counter}")
        except:
            logger.warning(f'failed to parse {key} message, received: {value}')

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
                logger.debug('timeout triggered')
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
        logger.debug(f"sent {command}, received {msg}")
        return msg