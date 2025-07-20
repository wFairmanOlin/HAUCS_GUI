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

class YSIReader(QThread):
    logger_data = pyqtSignal(str, str)

    adc = None
    start_record = False
    data_record = []

    FULL_SCALE = 10500
    ZERO_SCALE = 0
    FULL_MGL = 15
    time_pass = 0

    YSI_folder = "/home/haucs/Desktop/HAUCS_GUI/YSI_data/"
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
                        start_time = time.time()  # ✅ จับเวลาตอนเริ่ม record
                    now = time.time()
                    delta_sec = now - start_time
                    # print(delta_sec)

                    if delta_sec <= 30:
                        ysi = self.FULL_MGL * (val - self.ZERO_SCALE) / (self.FULL_SCALE - self.ZERO_SCALE)
                        self.data_record.append(ysi)
                        self.time_pass = delta_sec
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
        send_data = self.calculate_do_and_fit(self.data_record, time_stop, self.time_pass)
        self.data_record = []
        return send_data

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

    def exp_func(self, x, a, b, c):
        return a * np.exp(-b * x) + c

    def calculate_do_and_fit(self, do_vals, time_stop, time_pass):
        do_size = len(do_vals)
        scale_data = do_size / time_pass

        # time_stop is the real time sec which underwater, normally less than time_pass
        if time_stop < time_pass:
            do_size = int(scale_data * time_stop)
            do_vals = do_vals[:do_size]
        else:
            time_stop = time_pass

        s_vals = np.arange(len(do_vals)) / scale_data  # x จริงตามเวลาจริง (เช่น 0,1,...)

        # สร้างแกน x_plot ที่ครอบคลุมถึง 30 วินาที (เสมอ)
        x_plot = np.linspace(0, 30, 100)

        # default fallback
        y_fit = np.zeros_like(x_plot)
        y_at_30 = None

        try:
            # ✅ Fit exponential curve กับเท่าที่มีข้อมูล
            popt, _ = curve_fit(self.exp_func, s_vals, do_vals)

            # ✅ สร้าง y_fit ให้มีค่าครอบคลุม x_plot ถึง 30s
            y_fit = self.exp_func(x_plot, *popt)

            # ✅ คำนวณ y ที่ x=30 วินาที (แม้ข้อมูลจริงจะน้อยกว่านั้น)
            y_at_30 = self.exp_func(30, *popt)

        except Exception as e:
            print("Curve fit failed:", e)

            # fallback: linear interpolation (ถ้ามีข้อมูลน้อย)
            y_fit = np.interp(x_plot, s_vals, do_vals)

            # คำนวณ y_at_30 เฉพาะกรณีที่ข้อมูลถึง 30 วิ
            if 30 <= s_vals[-1]:
                y_at_30 = np.interp(30, s_vals, do_vals)
            else:
                y_at_30 = np.mean(do_vals)

        # print(f"y_fit at x=30s: {y_at_30}")
        return y_at_30