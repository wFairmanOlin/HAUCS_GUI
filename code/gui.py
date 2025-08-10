ENABLE_DEBUG = False # set true to print logs to console and collect debug level logs

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QGridLayout, QCheckBox, QMessageBox, QDialog
)
from PyQt5.QtCore import Qt, QTimer, QSize, pyqtSignal, QObject, QMutex, QMutexLocker
from PyQt5.QtGui import QIcon, QCursor
from custom_widgets.toggle_switch import ToggleSwitch
import sys
from result_window import ResultWindow
import os
import time
import csv
from truck_sensor import TruckSensor, Mode
from datetime import datetime
from custom_widgets.battery_widget import BatteryWidget
from custom_widgets.led_indicator import LEDStatusWidget
from custom_widgets.custom_yesno_dialog import CustomYesNoDialog
from custom_widgets.gear import *
from converter import *
from shutdown_dialog import ShutdownDialog
from history_window import HistoryLogWindow
from setting_dialog import SettingDialog

from ysi_calibration import YsiCalibrationWindow
import pickle
import logging
from logging.handlers import RotatingFileHandler
import queue
import argparse
import sensor
import truck_sensor
from gps_sensor import degToCompass

import faulthandler
faulthandler.enable()

logger = logging.getLogger(__name__)
# if os.environ.get('DISPLAY','') == '':
#     print('no display found. Using :0.0')
#     os.environ.__setitem__('DISPLAY', ':0.0')

class DOApp(QWidget):
    def __init__(self):
        super().__init__()
        # global mutexes
        self.database_mutex  = QMutex() # control access to datbase folder
        self.csv_mutex = QMutex() # control access to setting/calibration.csv 
        self.ble_mutex = QMutex()

        #status message queue
        self.status_q = queue.Queue()
        #status message timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.on_status_timer)
        self.status_timer.setInterval(5000)
        self.status = None # create status in case send_status called too soon
        
        #### LOGGING ####
        # formatter for all handlers
        fileFormatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s: %(message)s')
        # rotating log file
        fileHandler = RotatingFileHandler('log.log', mode='a', maxBytes=5*1024*1024, 
                                 backupCount=3, encoding=None, delay=False)
        fileHandler.setFormatter(fileFormatter)
        fileHandler.setLevel((logging.DEBUG if ENABLE_DEBUG else logging.INFO))
        # custom logger to print messages to terminal/status widget
        logPrinter = customLogHandler()
        logPrinter.setFormatter(fileFormatter)
        logPrinter.setLevel((logging.DEBUG if ENABLE_DEBUG else logging.INFO))
        # connect logPrinter Handler to status widget
        logPrinter.log_message.connect(self.send_status)
        # local filter to ignore low level library DEBUG messages
        localFilter = localOnlyFilter()
        logging.getLogger().addHandler(fileHandler)
        logging.getLogger().addHandler(logPrinter)
        for handler in logging.root.handlers:
            handler.addFilter(localFilter)
        # set log level for overall logger
        logging.getLogger().setLevel((logging.DEBUG if ENABLE_DEBUG else logging.INFO))
        
        logger.info('\nSTARTING APPLICATION')
        self.current_time = datetime.now()

        self.setWindowTitle("DO Monitor")
        self.setStyleSheet("background-color: black; color: white;")

        screen_size = QApplication.primaryScreen().size()
        self.base_font_size = int(screen_size.height() * 0.04)
        self.label_font_size = int(screen_size.height() * 0.06)
        self.label_font_large = int(screen_size.height() * 0.1)
        self.label_font_xlarge = int(screen_size.height() * 0.14)
        self.status_font = int(screen_size.height() * 0.08)
        self.unit_font = int(screen_size.height() * 0.05)

        # retrieve and apply settings
        self.settings = self.load_local_csv("settings.csv")
        self.unit = self.settings.get("unit", "mgl")
        self.min_do = self.settings.get("min_do", 4)
        self.good_do = self.settings.get("good_do", 4)

        # retrieve and apply calibration info
        self.calibration = self.load_local_csv("calibration.csv")
        self.last_calibration = self.calibration.get("last_calibration", "-")

        self.setup_ui()
        self.showFullScreen()
        self.setup_thread()

        # setup timer for timer Qlabel
        self.counter_time = 0
        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_counter)
        # self.timer.start()

    def setup_thread(self):
        self.thread = TruckSensor(self.calibration, self.settings, self.database_mutex, self.ble_mutex)
        self.thread.unit = self.unit
        self.thread.update_data.connect(self.on_data_update)
        self.thread.update_pond_data.connect(self.on_update_pond_data)
        self.thread.sensor_underwater.connect(self.on_underwater_signal)
        self.thread.ysi_data.connect(self.on_ysi_update)
        self.thread.calibration_data.connect(self.on_calibration_available)
        self.thread.start()

    def setup_ui(self):
        os.popen('sudo hciconfig hci0 reset')
        main_layout = QVBoxLayout()

        # ==== Top Bar ====
        top_bar = QHBoxLayout()

        self.lbl_mgl = QLabel("mg/l")
        self.lbl_percent = QLabel("%")
        
        if self.unit == "percent":
            self.unit_toggle = ToggleSwitch(checked=True)
            self.lbl_mgl.setStyleSheet(f"font-size: {int(self.base_font_size)}px;")
            self.lbl_percent.setStyleSheet(f"font-size: {int(self.base_font_size)}px; font-weight: bold;")
        else:
            self.unit_toggle = ToggleSwitch(checked=False)
            self.lbl_mgl.setStyleSheet(f"font-size: {int(self.base_font_size)}px; font-weight: bold;")
            self.lbl_percent.setStyleSheet(f"font-size: {int(self.base_font_size)}px;")
        self.unit_toggle.toggled.connect(self.on_toggle_click)
            
        top_bar.addSpacing(5)
        top_bar.addWidget(self.lbl_mgl)
        top_bar.addSpacing(5)
        top_bar.addWidget(self.unit_toggle)
        top_bar.addSpacing(5)
        top_bar.addWidget(self.lbl_percent)
        top_bar.addStretch()
        settings_btn = QPushButton()
        settings_btn.setIcon(QIcon(draw_square_teeth_gear_icon(size=50)))
        # settings_btn.setIcon(QIcon("settings.png"))
        settings_btn.setIconSize(QSize(50, 50)) 
        settings_btn.setFixedSize(60, 60)
        settings_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
            }
        """)
        settings_btn.clicked.connect(self.open_settings_dialog)
        top_bar.addWidget(settings_btn)
        top_bar.addSpacing(5)
        self.led_status = LEDStatusWidget(status="disconnected")
        top_bar.addWidget(self.led_status)
        top_bar.addSpacing(5)
        self.sid_val   = QLabel('')
        self.sid_val.setStyleSheet(f"font-size: {self.base_font_size}px; font-weight: bold; padding-right: 10px;")
        top_bar.addWidget(self.sid_val)
        top_bar.addSpacing(5)
        self.battery_widget = BatteryWidget()
        top_bar.addWidget(self.battery_widget)
        top_bar.addSpacing(10)

        # Exit Button (red X)
        exit_btn = QPushButton("X")
        exit_btn.setFixedSize(50, 50)
        exit_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #e74c3c;
                color: white;
                font-size: {int(self.base_font_size * 1.3)}px;
                font-style: bold;
                border: none;
                border-radius: 25px;
            }}
        """)
        exit_btn.clicked.connect(self.close)
        top_bar.addWidget(exit_btn)

        main_layout.addLayout(top_bar)

        # ==== Info Grid ====
        info_grid = QGridLayout()

        pid_label   = QLabel('Pond')
        ysi_label   = QLabel('YSI DO')
        hboi_label  = QLabel('BLE DO')
        timer_label = QLabel('TIMER')
        

        self.pid_val   = QLabel('-')
        self.ysi_val   = QLabel('0')
        self.hboi_val  = QLabel('0')
        self.timer_val = QLabel('0')
        self.status   = QLabel('')
        self.status.setWordWrap(True) #allow multiple lines
        self.status.setFixedWidth(500)

        self.hboi_unit = QLabel('%' if self.unit == 'percent' else 'mg/l')
        self.ysi_unit  = QLabel('%' if self.unit == 'percent' else 'mg/l')
        self.timer_unit = QLabel('s')
        

        pid_label.setStyleSheet(f"font-size: {self.label_font_large}px;")
        ysi_label.setStyleSheet(f"font-size: {self.label_font_large}px; padding-left: 10px;")
        hboi_label.setStyleSheet(f"font-size: {self.label_font_large}px; padding-left: 10px;")
        timer_label.setStyleSheet(f"font-size: {self.label_font_large}px; padding-left: 10px;") 

        self.pid_val.setStyleSheet(f"font-size: {self.label_font_xlarge}px; font-weight: bold; padding-right: 10px;")
        self.ysi_val.setStyleSheet(f"font-size: {self.label_font_xlarge}px; font-weight: bold;")
        self.hboi_val.setStyleSheet(f"font-size: {self.label_font_xlarge}px; font-weight: bold;")
        self.timer_val.setStyleSheet(f"font-size: {self.label_font_xlarge}px; font-weight: bold;")
        self.status.setStyleSheet(f"font-size: {self.status_font}px; font-weight: bold;")

        self.hboi_unit.setStyleSheet(f"font-size: {self.unit_font}px; font-weight: bold;")
        self.ysi_unit.setStyleSheet(f"font-size: {self.unit_font}px; font-weight: bold;")
        self.timer_unit.setStyleSheet(f"font-size: {self.unit_font}px; font-weight: bold;")

        # HEADING/GPS WIDGETS
        self.hdg_crd = QLabel("")
        self.hdg_crd.setStyleSheet(f"font-size: {self.label_font_large}px; font-weight: bold;")
        self.hdg_deg = QLabel("")
        self.hdg_deg.setStyleSheet(f"font-size: {self.base_font_size}px; font-weight: bold;")
        hdg_layout = QVBoxLayout()
        hdg_crd_layout = QHBoxLayout()
        hdg_crd_layout.addStretch()
        hdg_crd_layout.addWidget(self.hdg_crd)
        hdg_crd_layout.addStretch()
        hdg_crd_widget = QWidget()
        hdg_crd_widget.setLayout(hdg_crd_layout)
        hdg_layout.addWidget(hdg_crd_widget)
        hdg_deg_layout = QHBoxLayout()
        hdg_deg_layout.addStretch()
        hdg_deg_layout.addWidget(self.hdg_deg)
        hdg_deg_layout.addStretch()
        hdg_deg_widget = QWidget()
        hdg_deg_widget.setLayout(hdg_deg_layout)
        hdg_layout.addWidget(hdg_deg_widget)
        hdg_widget = QWidget()
        hdg_widget.setLayout(hdg_layout)

        nsat_label = QLabel("NSAT")
        nsat_label.setStyleSheet(f"font-size: {self.base_font_size}px; font-weight;")
        self.nsat_val = QLabel("0")
        self.nsat_val.setStyleSheet(f"font-size: {self.base_font_size}px; font-weight: bold;")
        lat_label = QLabel("LAT")
        lat_label.setStyleSheet(f"font-size: {self.base_font_size}px; font-weight; padding-left: 5px")
        lng_label = QLabel("LNG")
        lng_label.setStyleSheet(f"font-size: {self.base_font_size}px; font-weight; padding-left: 5px")
        self.lat_val = QLabel("0.0")
        self.lng_val = QLabel("0.0")
        self.lat_val.setStyleSheet(f"font-size: {self.base_font_size}px;")
        self.lng_val.setStyleSheet(f"font-size: {self.base_font_size}px;")

        gps_layout = QGridLayout()
        gps_layout.addWidget(nsat_label,   0, 0, Qt.AlignCenter | Qt.AlignBottom)
        gps_layout.addWidget(self.nsat_val,1, 0, Qt.AlignCenter | Qt.AlignTop)
        gps_layout.addWidget(lat_label,    0, 1, Qt.AlignLeft | Qt.AlignBottom)
        gps_layout.addWidget(lng_label,    1, 1, Qt.AlignLeft | Qt.AlignTop)
        gps_layout.addWidget(self.lat_val, 0, 2, Qt.AlignRight | Qt.AlignBottom)
        gps_layout.addWidget(self.lng_val, 1, 2, Qt.AlignRight | Qt.AlignTop)
        gps_widget = QWidget()
        gps_widget.setLayout(gps_layout)

        info_grid.addWidget(hboi_label,     0, 0, Qt.AlignLeft)
        info_grid.addWidget(self.hboi_val,  0, 1, Qt.AlignRight)
        info_grid.addWidget(self.hboi_unit, 0, 2, Qt.AlignLeft)
        info_grid.addWidget(pid_label,      0, 3, Qt.AlignLeft)
        info_grid.addWidget(self.pid_val,   0, 4, Qt.AlignRight)
        info_grid.addWidget(ysi_label,      1, 0, Qt.AlignLeft)
        info_grid.addWidget(self.ysi_val,   1, 1, Qt.AlignRight)
        info_grid.addWidget(self.ysi_unit , 1, 2, Qt.AlignLeft)
        info_grid.addWidget(hdg_widget,     1, 3, Qt.AlignCenter)
        info_grid.addWidget(gps_widget,     1, 4, Qt.AlignLeft)
        info_grid.addWidget(timer_label,    2, 0, Qt.AlignLeft)
        info_grid.addWidget(self.timer_val, 2, 1, Qt.AlignRight)
        info_grid.addWidget(self.timer_unit,2, 2, Qt.AlignLeft)
        info_grid.addWidget(self.status,    2, 3, 1, 2, Qt.AlignLeft)
        
        main_layout.addLayout(info_grid)

        # ==== Bottom Buttons ====
        btn_layout = QHBoxLayout()
        buttons = [
            ("Calibrate BLE", self.on_calibrate_do_click),
            ("Calibrate YSI", self.on_calibrate_ysi_click),
            ("History Log", self.on_history_log_click),
        ]

        for label, handler in buttons:
            btn = QPushButton(label)
            btn.setFixedHeight(self.base_font_size * 4)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #333;
                    border: 1px solid white;
                    color: white;
                    font-size: {int(self.base_font_size * 2)}px;
                    padding: 10px;                         
                }}
                QPushButton:hover {{
                    background-color: #555;
                }}
                QPushButton:pressed {{
                    background-color: #2ecc71;
                }}
            """)
            btn.clicked.connect(handler)
            btn_layout.addWidget(btn)

        main_layout.addLayout(btn_layout)
        self.setLayout(main_layout)
        self.setCursor(QCursor(Qt.BlankCursor))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()

    def on_calibration_available(self, data):
        for key in data:
            self.calibration[key] = data[key]
        self.save_local_csv(self.calibration, "calibration.csv")

    def on_data_update(self, data_dict):
        if 'battv' in data_dict:
            batt_percent = int((data_dict["battv"] - self.settings['min_battv']) / (self.settings['max_battv'] - self.settings['min_battv']) * 100)
            if batt_percent > 100:
                batt_percent = 100
            batt_charge = ("not charging" != data_dict['batt_status'][:12])
            self.battery_widget.set_battery_status(batt_percent, batt_charge)
        if 'connection' in data_dict:
            if data_dict['connection']:
                self.led_status.set_status("connected_ready")
            else:
                self.led_status.set_status("disconnected")
        if 'name' in data_dict:
            self.sid_val.setText(str(data_dict['name']))
        if 'pid' in data_dict:
            self.pid_val.setText(str(data_dict['pid']))
        if 'do' in data_dict:
            if self.unit == "percent":
                self.hboi_val.setText(f"{100 * data_dict['do']:.0f}")
                self.hboi_unit.setText('%')
            else:
                self.hboi_val.setText(f"{data_dict['do_mgl']:.1f}")
                self.hboi_unit.setText('mg/l')
            # update label color based on mgl value in setting.setting
            do_val = data_dict['do_mgl']
            if do_val < self.min_do:
                self.hboi_val.setStyleSheet(f"font-size: {self.label_font_xlarge}px; font-weight: bold; color: red;")
            elif self.min_do <= do_val < self.good_do:
                self.hboi_val.setStyleSheet(f"font-size: {self.label_font_xlarge}px; font-weight: bold; color: yellow;")
            else:
                self.hboi_val.setStyleSheet(f"font-size: {self.label_font_xlarge}px; font-weight: bold; color: limegreen;")
        if 'ysi_do' in data_dict:
            self.on_ysi_update(do_ps=data_dict['ysi_do'], do_mgl=data_dict['ysi_do_mgl'], smooth=False)
        if 'hdg' in data_dict:
            self.hdg_deg.setText(f"{data_dict['hdg']:03.0f}\N{DEGREE SIGN}")
            self.hdg_crd.setText(degToCompass(data_dict['hdg']))
            self.nsat_val.setText(f"{data_dict['nsat']:02d}")
            self.lat_val.setText(f"{data_dict['lat']:.5f}")
            self.lng_val.setText(f"{data_dict['lng']:.5f}")


    def on_underwater_signal(self, value):
        # true if underwater, otherwise false
        if value == "True":
            self.counter_time = 0
            self.timer.start()
            self.timer_val.setText(f"{self.counter_time}")
            self.send_status('collecting data')

        else:
            if self.timer.isActive():
                self.timer.stop()
                self.send_status('collection stopped')

    def on_ysi_update(self, do_ps, do_mgl, smooth=True):
        '''
        smooth applies moving average to live display only.
        '''
        if smooth:
            alpha = 0.5
            if self.ysi_val.text().isnumeric():
                try:
                    old_data = float(self.ysi_val.text())
                    if (self.unit == "percent") and (do_ps != -1):
                        do_ps = alpha * do_ps + (1 - alpha) * old_data / 100
                    else:
                        do_mgl = alpha * do_mgl + (1 - alpha) * old_data
                except Exception as e:
                    logger.warning(f'failed smooth ysi data \n{e}')
        # only update main screen when in normal operations
        if self.thread.mode == truck_sensor.Mode.normal:
            if self.unit == "percent":
                # water temperature and/or pressure have not been recorded
                if do_ps == -1:
                    self.ysi_val.setText('-')
                else:
                    self.ysi_val.setText(f"{100 * do_ps:.0f}")
                self.ysi_unit.setText('%')
            else:
                self.ysi_val.setText(f"{do_mgl:.1f}")
                self.ysi_unit.setText('mg/l')

        # update ysi color
        if do_mgl < self.min_do:
            self.ysi_val.setStyleSheet(f"font-size: {self.label_font_xlarge}px; font-weight: bold; color: red;")
        elif self.min_do <= do_mgl < self.good_do:
           self.ysi_val.setStyleSheet(f"font-size: {self.label_font_xlarge}px; font-weight: bold; color: yellow;")
        else:
            self.ysi_val.setStyleSheet(f"font-size: {self.label_font_xlarge}px; font-weight: bold; color: limegreen;")

    def on_status_timer(self):
        msg = ""
        if self.status_q.qsize() > 0:
            if self.status_q.qsize() > 1:
                self.status_timer.setInterval(1000)
            else:
                self.status_timer.setInterval(5000)
            try:
                msg = self.status_q.get_nowait()
            except:
                pass
        
            if isinstance(msg, dict):
                txt = msg.get('text', 'status error')
                txt = txt[:100] # limit to first 100 characters
                color = msg.get('color', 'white')
                #shrink font size as message size scales
                if len(txt) > 20: 
                    font = int(self.status_font * 0.75)
                elif len(txt) > 40:
                    font = int(self.status_font * 0.45)
                elif len(txt) > 60:
                    font = int(self.status_font * 0.25)
                else:
                    font = self.status_font
                txt = "\u200b".join(txt) # add zero-width spacing to text (allows word wrapping)
                if self.status:
                    self.status.setStyleSheet(f"font-size: {font}px; color: {color}; font-weight: bold;")
                    self.status.setText(txt)
                self.status_timer.start()
        # display nothing
        else:
            self.status.setText("")

    def send_status(self, msg, color="white"):
        '''
        call this function to add a message to the status queue
        parameters:
        '''
        self.status_q.put({'text':msg, 'color':color})
        # not messages currently displayed
        if not self.status_timer.isActive():
            self.on_status_timer()
 

    def update_counter(self):
        self.counter_time += 1
        # close result if open
        if hasattr(self, 'result_window') and self.result_window is not None:
            if self.result_window.isVisible():
                self.result_window.close()
            self.result_window = None
        
        if self.counter_time == 30: # TODO: this should be exposed in settings.csv
            self.send_status('ready to pick up')

        self.timer_val.setText(f"{self.counter_time}")

    def on_update_pond_data(self, data_dict):
        self.result_window = ResultWindow(data_dict, self.unit, self.min_do, self.good_do, int(self.settings['autoclose_sec']))
        self.result_window.closed_data.connect(self.on_result_window_closed)
        self.result_window.set_do_temp_pressure(sample_stop_time=30)

    def on_result_window_closed(self, result_data):
        # print("Result window closed. Data received:", result_data)
        self.result_window = None
        self.thread.update_database(result_data)
        

    def on_toggle_click(self):
        if self.unit_toggle.isChecked() and self.unit != "percent":
            self.lbl_mgl.setStyleSheet(f"font-size: {int(self.base_font_size)}px; font-weight: normal;")
            self.lbl_percent.setStyleSheet(f"font-size: {int(self.base_font_size)}px; font-weight: bold;")
            self.unit = "percent"
        elif self.unit == "percent":
            self.lbl_mgl.setStyleSheet(f"font-size: {int(self.base_font_size)}px; font-weight: bold;")
            self.lbl_percent.setStyleSheet(f"font-size: {int(self.base_font_size)}px; font-weight: normal;")
            self.unit = "mgl"
        # save unit permanently
        self.settings['unit'] = self.unit
        self.save_local_csv(self.settings, "settings.csv")
        self.thread.toggle_unit(self.unit)

    def on_calibrate_do_click(self):
        msg = "1) Ensure sensor is not underwater\n2) Press Yes to start calibration\n\nAre you sure you want to\nCALIBRATE?"
        dialog = CustomYesNoDialog(msg, self.last_calibration, self)
        if dialog.exec_() == QDialog.Accepted:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            success = self.thread.calibrate_DO()
            QApplication.restoreOverrideCursor()
            self.thread.mode = Mode.normal
            if success:
                now = datetime.now()
                formatted_time = now.strftime("%m/%d/%y %I:%M %p") 
                self.last_calibration = formatted_time
                self.calibration['last_calibration'] = self.last_calibration
                self.save_local_csv(self.calibration, "calibration.csv")
        else:
            # user clicked no
            pass
    
    def on_history_log_click(self):
        self.history_window = HistoryLogWindow(self.unit, self.min_do, self.good_do, self.database_mutex)

    def on_calibrate_ysi_click(self):
        logger.debug('starting ysi calibration')
        self.thread.start_ysi_calibration(5)
        self.ysi_window = YsiCalibrationWindow(self.thread.ysi_data)
        self.ysi_window.ysi_calibration_complete.connect(self.ysi_calibration_complete)

    def ysi_calibration_complete(self, data, save):
        logger.debug(f"setting page closed save? {save} \n{data}")
        self.ysi_window = None
        self.thread.stop_ysi_calibration()
        if save:
            self.calibration['ysi_zero_scale'] = data['zero']
            self.calibration['ysi_full_scale'] = data['full_scale']
            self.save_local_csv(self.calibration, "calibration.csv")
            self.thread.calibration = self.calibration
            self.thread.set_ysi_calibration(data['zero'], data['full_scale'])
            logger.info(f"ysi calibration complete saved new values {data['zero']} {data['full_scale']}")
            self.send_status('ysi calibration success', 'limegreen')
        else:
            logger.info("ysi calibration not saved")
            self.send_status('ysi calibration not saved')

    def open_settings_dialog(self):
        logger.debug('opening settings page')
        self.settings_window = SettingDialog(self.settings)
        self.settings_window.setting_complete.connect(self.setting_complete)

    def setting_complete(self, data, save):
        logger.debug(f"setting page closed save? {save} \n{data}")
        if save:
            for i in data:
                self.settings[i] = data[i]
            self.save_local_csv(self.settings, "settings.csv")
            self.thread.settings = self.settings
            self.thread.set_pressure_threshold(data['depth_threshold'])
            logger.info(f"settings successfully saved {data}")
            self.send_status('settings saved', 'limegreen')
        else:
            logger.info("settings not saved")
            self.send_status('settings not saved')

    def save_local_csv(self, data_dict, filename):
        with QMutexLocker(self.csv_mutex):
            try:
                with open(filename, 'w', newline='') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=["param", "value"])
                    writer.writeheader()
                    for key, value in data_dict.items():
                        if isinstance(value, list):
                            output = "$".join([str(i) for i in value])
                        else:
                            output = str(value)
                        writer.writerow({"param": key, "value": output})
                logger.info(f"saved to {filename}")
            except Exception as e:
                logger.warning(f"Failed to save: {e}")

    def load_local_csv(self, filename):
        '''
        Loads data from local csv files containing setting and calibration info. Files
        nested in folders not supported. 

        setting.csv:      settings for gui
        calibration.csv:  calibration information  
        '''
        data_dict = {}
        if os.path.exists(filename):
            with QMutexLocker(self.csv_mutex):
                with open(filename, newline='') as csvfile:
                    reader = csv.DictReader(csvfile)
                    for row in reader:
                        key = row['param']
                        # split into mutliple values
                        value = row['value']
                        value = value.split('$')
                        # process single values
                        if len(value) == 1:
                            try:
                                value = float(value[0])
                            except:
                                data_dict[key] = value[0]
                        # process multiple values
                        elif len(value) > 1:
                            value_arr = []
                            for val in value:
                                try:
                                    value_arr.append(float(val))
                                except:
                                    value_arr.append(val)
                            data_dict[key] = value_arr
                        try:
                            value = float(row['value'])
                        except:
                            value = row['value']
                        data_dict[key] = value
        else:
            logger.warning("could not load %s", filename)

        return data_dict

    def closeEvent(self, event):
        dialog = ShutdownDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            if dialog.result == "close":
                logger.info("user closed program")
                self.thread.abort()
                if hasattr(self, 'result_window') and self.result_window is not None:
                    if self.result_window.isVisible():
                        self.result_window.close()
                    self.result_window = None
                super().closeEvent(event)

            elif dialog.result == "shutdown":
                logger.info("user triggered shutdown")
                self.thread.abort()
                if hasattr(self, 'result_window') and self.result_window is not None:
                    if self.result_window.isVisible():
                        self.result_window.close()
                    self.result_window = None
                os.system("sudo shutdown now")
                event.ignore()

            elif dialog.result == "restart":
                logger.info("user triggered restart")
                self.thread.abort()
                if hasattr(self, 'result_window') and self.result_window is not None:
                    if self.result_window.isVisible():
                        self.result_window.close()
                    self.result_window = None
                os.system("sudo reboot")
                event.ignore()

            elif dialog.result == "test":
                logger.info("sending test data to bring up results page")
                with open('test.pickle', 'rb') as file:
                    fake_data = pickle.load(file)
                    
                fake_data['sample_duration'] = len(fake_data['do_vals']) / fake_data['sample_hz']
                self.thread.update_pond_data.emit(fake_data)
                event.ignore()
            else:
                event.ignore()
        else:
            # User pressed Cancel or closed dialog
            event.ignore()

class localOnlyFilter(logging.Filter):
    names = ['__main__', 'bt_sensor', 'converter', 'firebase_worker', 'gps_sensor', 'history_window', 'sensor', 'truck_sensor']
    def filter(self, record):
        return record.name in self.names

class customLogHandler(logging.Handler, QObject):
    log_message = pyqtSignal(str, str)

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)

    def emit(self, record):
        self.format(record)
        if ENABLE_DEBUG:
            print(f"{record.relativeCreated/1000:.2f}: {record.levelname} {record.message}")
        # if from truck sensor code .INFO or level greater than info
        if (record.name == "truck_sensor" and record.levelno > 10) or record.levelno > 20:
            
            if record.levelno > 30:
                color = "red"
            elif record.levelno > 20:
                color = "orange"
            else:
                color = "white"
            self.log_message.emit(record.msg, color)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="gui")
    parser.add_argument('-debug', '-d', '-D', action='store_true')

    args = parser.parse_args()
    ENABLE_DEBUG = args.debug

    app = QApplication(sys.argv)
    window = DOApp()
    sys.exit(app.exec_())



