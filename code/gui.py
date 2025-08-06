ENABLE_DEBUG = False # set true to print logs to console and collect debug level logs

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QGridLayout, QCheckBox, QMessageBox, QDialog
)
from PyQt5.QtCore import Qt, QTimer, QSize, pyqtSignal, QObject
from PyQt5.QtGui import QIcon
from toggle_switch import ToggleSwitch
import sys
from result_window import ResultWindow
import os
import time
import csv
from truck_sensor import TruckSensor
from datetime import datetime
from battery_widget import BatteryWidget
from led_indicator import LEDStatusWidget
from converter import *
from shutdown_dialog import ShutdownDialog
from history_window import HistoryLogWindow
from setting_dialog import SettingDialog
from custom_yesno_dialog import CustomYesNoDialog
import pickle
import logging
import queue
import argparse

logger = logging.getLogger(__name__)

# if os.environ.get('DISPLAY','') == '':
#     print('no display found. Using :0.0')
#     os.environ.__setitem__('DISPLAY', ':0.0')

class DOApp(QWidget):
    def __init__(self):
        super().__init__()

        #status message queue
        self.status_q = queue.Queue()
        #status message timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.on_status_timer)
        self.status_timer.setInterval(5000)

        ##### LOGGING #####
        logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s: %(message)s', filename='log.log', encoding='utf-8',
                            level=(logging.DEBUG if ENABLE_DEBUG else logging.INFO),)
        logger.info('\nSTARTING APPLICATION')
        # custom logger to display status
        logPrinter = customLogHandler()
        localFilter = localOnlyFilter()
        logPrinter.setLevel((logging.DEBUG if ENABLE_DEBUG else logging.INFO))
        logging.getLogger().addHandler(logPrinter)
        for handler in logging.root.handlers:
            handler.addFilter(localFilter)
        logPrinter.log_message.connect(self.send_status)

        self.current_time = datetime.now()

        self.setWindowTitle("DO Monitor")
        self.setStyleSheet("background-color: black; color: white;")

        screen_size = QApplication.primaryScreen().size()
        self.base_font_size = int(screen_size.height() * 0.03)
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

    def setup_ui(self):
        os.popen('sudo hciconfig hci0 reset')
        main_layout = QVBoxLayout()

        # ==== Top Bar ====
        top_bar = QHBoxLayout()

        self.lbl_mgl = QLabel("mg/l")
        self.lbl_percent = QLabel("%")
        
        if self.unit == "percent":
            self.unit_toggle = ToggleSwitch(checked=True)
            self.lbl_mgl.setStyleSheet(f"font-size: {int(self.base_font_size * 1.4)}px;")
            self.lbl_percent.setStyleSheet(f"font-size: {int(self.base_font_size * 1.4)}px; font-weight: bold;")
        else:
            self.unit_toggle = ToggleSwitch(checked=False)
            self.lbl_mgl.setStyleSheet(f"font-size: {int(self.base_font_size * 1.4)}px; font-weight: bold;")
            self.lbl_percent.setStyleSheet(f"font-size: {int(self.base_font_size * 1.4)}px;")
        self.unit_toggle.toggled.connect(self.on_toggle_click)
            
        top_bar.addSpacing(5)
        top_bar.addWidget(self.lbl_mgl)
        top_bar.addSpacing(5)
        top_bar.addWidget(self.unit_toggle)
        top_bar.addSpacing(5)
        top_bar.addWidget(self.lbl_percent)

        top_bar.addStretch()

        self.led_status = LEDStatusWidget(status="disconnected", font_size=int(self.base_font_size * 1.2))
        top_bar.addWidget(self.led_status)
        top_bar.addSpacing(30)

        settings_btn = QPushButton()
        settings_btn.setIcon(QIcon("settings.png"))
        settings_btn.setIconSize(QSize(40, 40)) 
        settings_btn.setFixedSize(44, 44)
        settings_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 40);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 80);
            }
        """)
        settings_btn.clicked.connect(self.open_settings_dialog)

        top_bar.addWidget(settings_btn)
        top_bar.addSpacing(30)

        self.battery_widget = BatteryWidget()
        top_bar.addWidget(self.battery_widget)
        top_bar.addSpacing(30)

        # Exit Button (red X)
        exit_btn = QPushButton("X")
        exit_btn.setFixedSize(40, 40)
        exit_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #e74c3c;
                color: white;
                font-size: {int(self.base_font_size * 0.9)}px;
                border: none;
                border-radius: 20px;
            }}
            QPushButton:hover {{
                background-color: #ff6f61;
            }}
            QPushButton:pressed {{
                background-color: #c0392b;
            }}
        """)
        exit_btn.clicked.connect(self.close)
        top_bar.addWidget(exit_btn)

        main_layout.addLayout(top_bar)

        # ==== Info Grid ====
        info_grid = QGridLayout()

        pid_label   = QLabel('Pond ID')
        sid_label   = QLabel('HBOI ID')
        ysi_label   = QLabel('YSI DO')
        hboi_label  = QLabel('HBOI DO')
        timer_label = QLabel('TIMER')
        

        self.pid_val   = QLabel('-')
        self.sid_val   = QLabel('-')
        self.ysi_val   = QLabel('-')
        self.hboi_val  = QLabel('-')
        self.timer_val = QLabel('-')
        self.status   = QLabel('')
        self.status.setWordWrap(True) #allow multiple lines

        self.hboi_unit = QLabel('%' if self.unit == 'percent' else 'mg/l')
        self.ysi_unit  = QLabel('%' if self.unit == 'percent' else 'mg/l')
        self.timer_unit = QLabel('s')
        

        pid_label.setStyleSheet(f"font-size: {self.label_font_large}px;")
        sid_label.setStyleSheet(f"font-size: {self.label_font_large}px;")
        ysi_label.setStyleSheet(f"font-size: {self.label_font_large}px; padding-left: 10px;")
        hboi_label.setStyleSheet(f"font-size: {self.label_font_large}px; padding-left: 10px;")
        timer_label.setStyleSheet(f"font-size: {self.label_font_large}px; padding-left: 10px;") 
        

        self.pid_val.setStyleSheet(f"font-size: {self.label_font_large}px; font-weight: bold; padding-right: 10px;")
        self.sid_val.setStyleSheet(f"font-size: {self.label_font_large}px; font-weight: bold; padding-right: 10px;")
        self.ysi_val.setStyleSheet(f"font-size: {self.label_font_xlarge}px; font-weight: bold;")
        self.hboi_val.setStyleSheet(f"font-size: {self.label_font_xlarge}px; font-weight: bold;")
        self.timer_val.setStyleSheet(f"font-size: {self.label_font_xlarge}px; font-weight: bold;")
        self.status.setStyleSheet(f"font-size: {self.status_font}px; font-weight: bold;")

        self.hboi_unit.setStyleSheet(f"font-size: {self.unit_font}px; font-weight: bold;")
        self.ysi_unit.setStyleSheet(f"font-size: {self.unit_font}px; font-weight: bold;")
        self.timer_unit.setStyleSheet(f"font-size: {self.unit_font}px; font-weight: bold;")
        

        info_grid.addWidget(hboi_label,     0, 0, Qt.AlignLeft)
        info_grid.addWidget(self.hboi_val,  0, 1, Qt.AlignRight)
        info_grid.addWidget(self.hboi_unit, 0, 2, Qt.AlignLeft)
        info_grid.addWidget(pid_label,      0, 3, Qt.AlignLeft)
        info_grid.addWidget(self.pid_val,   0, 4, Qt.AlignRight)
        info_grid.addWidget(ysi_label,      1, 0, Qt.AlignLeft)
        info_grid.addWidget(self.ysi_val,   1, 1, Qt.AlignRight)
        info_grid.addWidget(self.ysi_unit , 1, 2, Qt.AlignLeft)
        info_grid.addWidget(sid_label,      1, 3, Qt.AlignLeft)
        info_grid.addWidget(self.sid_val,   1, 4, Qt.AlignRight)
        info_grid.addWidget(timer_label,    2, 0, Qt.AlignLeft)
        info_grid.addWidget(self.timer_val, 2, 1, Qt.AlignRight)
        info_grid.addWidget(self.timer_unit,2, 2, Qt.AlignLeft)
        info_grid.addWidget(self.status,    2, 3, 1, 2, Qt.AlignLeft)
        
        main_layout.addLayout(info_grid)

        # ==== Bottom Buttons ====
        btn_layout = QHBoxLayout()
        buttons = [
            ("Calibrate HBOI", self.on_calibrate_do_click),
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

    def setup_thread(self):
        self.thread = TruckSensor()

        self.thread.max_fail = int(self.settings['upload_firebase_max_counter'])
        self.thread.do_vals_log = self.settings['do_vals']
        self.thread.log_folder = self.settings['log_folder']
        self.thread.unit = self.unit

        self.thread.initialize()
        self.thread.update_data.connect(self.on_data_update)
        self.thread.update_pond_data.connect(self.on_update_pond_data)
        self.thread.sensor_underwater.connect(self.on_underwater_signal)
        self.thread.ysi_data.connect(self.on_ysi_update)
        self.thread.start()
        self.ble_running = True

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()

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
        if 'mouse' in data_dict:
            if data_dict['mouse'] == 'normal':
                QApplication.restoreOverrideCursor()
            else:
                QApplication.setOverrideCursor(Qt.WaitCursor)

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
                self.status.setStyleSheet(f"font-size: {font}px; color: {color}; font-weight: bold;")
                self.status.setText(txt)
                self.status_timer.start()

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
        self.thread.update_database(result_data)
        self.result_window = None

    def on_toggle_click(self):
        if self.unit_toggle.isChecked() and self.unit != "percent":
            self.lbl_mgl.setStyleSheet(f"font-size: {int(self.base_font_size * 1.2)}px; font-weight: normal;")
            self.lbl_percent.setStyleSheet(f"font-size: {int(self.base_font_size * 1.2)}px; font-weight: bold;")
            self.unit = "percent"
        elif self.unit == "percent":
            self.lbl_mgl.setStyleSheet(f"font-size: {int(self.base_font_size * 1.2)}px; font-weight: bold;")
            self.lbl_percent.setStyleSheet(f"font-size: {int(self.base_font_size * 1.2)}px; font-weight: normal;")
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
            self.thread.messaging_active = False
            success = self.thread.calibrate_DO()
            QApplication.restoreOverrideCursor()
            self.thread.messaging_active = True
            if success:
                now = datetime.now()
                formatted_time = now.strftime("%m/%d/%y %I:%M %p") 
                self.last_calibration = formatted_time
                self.calibration['last_calibration'] = self.last_calibration
                self.save_local_csv(self.calibration, "calibration.csv")
        else:
            # user clicked no
            pass
        
    def on_calibrate_ysi_click(self):
        dialog = CustomYesNoDialog(
            "this page is in development\nstay tuned...",
            self
        )
        if dialog.exec_() == QDialog.Accepted:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            # user clicked yes
        else:
            # user clicked no
            pass

    def on_history_log_click(self):
        window = HistoryLogWindow(self.unit, self.min_do, self.good_do, parent=self)
        window.exec_() 

    def open_settings_dialog(self):
        dialog = SettingDialog(min_do=self.min_do, good_do=self.good_do, autoclose_sec=int(self.settings['autoclose_sec']))
        if dialog.exec_():
            new_values = dialog.get_values()
            self.min_do = new_values["min_do"]
            self.good_do = new_values["good_do"]
            self.settings['autoclose_sec'] = new_values["autoclose_sec"]
            self.settings['min_do'] = self.min_do
            self.settings['good_do'] = self.good_do
            self.save_local_csv(self.settings, "settings.csv")
            logger.info('user updated settings')

    def save_local_csv(self, data_dict, filename):
        try:
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=["param", "value"])
                writer.writeheader()
                for key, value in data_dict.items():
                    writer.writerow({"param": key, "value": str(value)})
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
            with open(filename, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    key = row['param']
                    # convert to float if possible
                    try:
                        value = float(row['value'])
                    except:
                        value = row['value']
                    data_dict[key] = value
        else:
            logger.info(f"created file for {filename}")
            with open(filename, 'a', newline='') as csvfile:
                pass
        
        return data_dict

    def closeEvent(self, event):
        dialog = ShutdownDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            if dialog.result == "close":
                logger.info("user closed program")
                self.thread.abort()
                self.thread.stop_firebase()
                if hasattr(self, 'result_window') and self.result_window is not None:
                    if self.result_window.isVisible():
                        self.result_window.close()
                    self.result_window = None
                super().closeEvent(event)

            elif dialog.result == "shutdown":
                logger.info("user triggered shutdown")
                self.thread.abort()
                self.thread.stop_firebase()
                if hasattr(self, 'result_window') and self.result_window is not None:
                    if self.result_window.isVisible():
                        self.result_window.close()
                    self.result_window = None
                os.system("sudo shutdown now")
                event.ignore()

            elif dialog.result == "restart":
                logger.info("user triggered restart")
                self.thread.abort()
                self.thread.stop_firebase()
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
        # print logs
        if ENABLE_DEBUG:
            print(f"{record.relativeCreated/100:.2f}: {record.levelname} {record.message}")
        # if from truck sensor code or level greater than info
        if record.name == "truck_sensor" or record.levelno > 20:
            
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

    app = QApplication()
    window = DOApp()
    sys.exit(app.exec_())



