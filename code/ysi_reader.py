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
from scipy.optimize import curve_fit
from converter import calculate_do_and_fit, convert_mgl_to_raw

class YSIReader(QThread):
    logger_data = pyqtSignal(str, str)

    adc = None
    start_record = False
    data_record = []

    FULL_SCALE = 10500
    ZERO_SCALE = 0
    FULL_MGL = 15
    time_pass = 0

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
        except Exception as error:
            self.logger_data.emit("warning", f'YSI ADC initialize failed {str(error)}')

    def set_record(self):
        self.start_record = True

    def run(self):
        self._abort = False

        if self.adc is None:
            self.logger_data.emit("warning", f'YSI ADC cannot be initialize, cannot start')
            return

        csv_file = None
        start_time = None  # ✅ กำหนดไว้ก่อน

        while not self._abort:
            try:
                val = self.adc.readADC_Differential_0_1()
                if self.start_record:
                    if csv_file is None:
                        csv_file = self.init_csv_file()
                        start_time = time.time()
                    now = time.time()
                    delta_sec = now - start_time
                    # print(delta_sec)

                    if delta_sec <= 30:
                        ysi = self.FULL_MGL * (val - self.ZERO_SCALE) / (self.FULL_SCALE - self.ZERO_SCALE)
                        self.data_record.append(ysi)
                        self.writeCSV(csv_file, [len(self.data_record), ysi, val])
                    self.csv_file = csv_file
                else:
                    csv_file = None
            except Exception as error:
                self.logger_data.emit("warning", f'YSI ADC Read Error {str(error)}')

            if self._abort:
                break
            self.msleep(100)  # 0.1 วินาที

    def stop_record(self, reset=False):
        self.start_record = False
        if reset:
            self.data_record = []

    def get_record(self, time_stop):
        self.start_record = False
        data_mgl = self.data_record
        print(f"in ysi_reader, do_mgl:{self.data_record[-1]}") 

        return data_mgl[-1]

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