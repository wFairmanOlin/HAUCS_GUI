import os
from PyQt5.QtCore import QThread, pyqtSignal, QObject
from datetime import datetime
import numpy as np
import shutil
import ADS1x15
from gpiozero.pins.pigpio import PiGPIOFactory
import csv
import time
from converter import *

class YSIReader(QThread):
    logger_data = pyqtSignal(str, str)
    ysi_data = pyqtSignal(float)

    adc = None
    adc_connected = False
    reconnect_period = 5
    reconnect_timer = 0
    recording = False
    data_record = []

    FULL_SCALE = 10500
    ZERO_SCALE = 0
    FULL_MGL = 15
    time_pass = 0
    ysi_do_mgl = 0

    sampling_period = 1000
    sampling_start = 0

    YSI_folder = "YSI_data/"
    csv_file = ""

    def __init__(self):
        super().__init__()
        self._abort = False

    def abort(self):
        self.logger_data.emit("info", "Stop YSI normal process")
        self._abort = True

    def initialize(self):
        try:
            self.adc = ADS1x15.ADS1115(1)
            self.adc.setGain(16)
            self.logger_data.emit("info", f'YSI ADC initialize finish. YSI ADC version: {ADS1x15.__version__}')
            self.adc_connected = True
        except Exception as error:
            self.logger_data.emit("warning", f'YSI ADC initialize failed {str(error)}')
            self.adc_connected = False

    def set_record(self):
        self.recording = True

    def run(self):
        self._abort = False
        csv_file = None

        while not self._abort:
            # try to initialize and sleep
            if not self.adc_connected:
                if time.time() - self.reconnect_timer > self.reconnect_period:
                    self.reconnect_timer = time.time()
                    self.initialize()

            # try to read, default to 0
            try:
                val = self.adc.readADC_Differential_0_1()
            except:
                val = 0
                self.adc_connected = False

            # perform voltage to mgl conversion
            self.ysi_do_mgl = self.FULL_MGL * (val - self.ZERO_SCALE) / (self.FULL_SCALE - self.ZERO_SCALE)
            # set to zero if less than zero
            self.ysi_do_mgl = 0 if self.ysi_do_mgl < 0 else self.ysi_do_mgl
            # publish YSI data
            self.ysi_data.emit(self.ysi_do_mgl)

            # set to record
            if self.recording:
                if csv_file is None:
                    csv_file = self.init_csv_file()
                    self.sampling_start = time.time()
                # append data to csv file
                self.data_record.append(self.ysi_do_mgl)
                self.writeCSV(csv_file, [time.time() - self.sampling_start, self.ysi_do_mgl, val])
                self.csv_file = csv_file
            else:
                csv_file = None

            if self._abort:
                break
            # sleep for sampling period
            self.msleep(1000)

    def get_record(self, stop=True, reset=False):
        self.recording = not stop
        data_mgl = self.data_record.copy()

        if reset:
            self.data_record = []

        return data_mgl


    def writeCSV(self, ofile, data):
        with open(ofile,'a',newline='') as csvfile:
            writer = csv.writer(csvfile, delimiter=',')
            writer.writerow(data)

    def init_csv_file(self):
        #global folder
        try:
            header = ['Num', 'ysi_do', 'ysi_read']
            filePath = self.YSI_folder
            #filePath = "data/"
            date = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')

            if not os.path.exists(filePath):
                os.mkdir(filePath)

            csvFile = filePath + date + ".csv"

            with open(csvFile,'w',newline='') as csvfile:
                writer = csv.writer(csvfile, delimiter=',')
                writer.writerow(header)
        except Exception as e:
            print("YSI: Failed to create csv file {csvfile}", str(e))
            self.logger_data.emit("warning", f"YSI: Failed to create csv file {csvfile} {str(e)}")

        return csvFile