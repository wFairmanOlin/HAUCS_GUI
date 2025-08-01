from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QGridLayout, QCheckBox, QMessageBox, QDialog
)
from PyQt5.QtCore import Qt, QTimer, QSize
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

class DOApp(QWidget):
    def __init__(self):
        super().__init__()

        self.current_time = datetime.now()

        self.setWindowTitle("DO Monitor")
        self.setStyleSheet("background-color: #4D4D4D; color: white;")

        screen_size = QApplication.primaryScreen().size()
        self.base_font_size = int(screen_size.height() * 0.03)
        self.label_font_size = int(screen_size.height() * 0.05)
        self.label_font_size_large = int(screen_size.height() * 0.07)

        self.data_labels = {
            "PID": QLabel("-1"),
            "SID": QLabel("-1"),
            "SCS": QLabel("connecting..."),
            "SB": QLabel("Reading Batt..."),
            "YSI": QLabel("-"),
            "SDL": QLabel("-"),
            "TIMER": QLabel("00:00"),
            "CAL_DT": QLabel("N/A"),
            "GPS": QLabel("-1, -1"),
        }

        # global structures
        self.settings = {} # all gui settings
        self.calibration = {} # all calibration data

        # retrieve and apply settings
        self.load_local_csv(self.settings, "settings.csv")
        self.unit = self.settings.get("unit", "mgl")
        self.min_do = self.settings.get("min_do", 4)
        self.good_do = self.settings.get("good_do", 4)

        # retrieve and apply calibration info
        self.load_local_csv(self.calibration, "calibration.csv")
        self.last_calibration = self.settings.get("last_calibration", "N/A")

        self.is_first = True
        self.check_conn_first = True
        self.setup_ui()
        self.showFullScreen()
        self.setup_thread()
        self.setup_timer()


    def load_local_csv(self, data_dict, filename):
        '''
        Loads data from local csv files containing setting and calibration info. Files
        nested in folders not supported. 

        setting.csv:      settings for gui
        calibration.csv:  calibration information  
        '''
        self.settings = {}
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
            print(f"created file for {filename}")
            with open(filename, 'a', newline='') as csvfile:
                pass

    def save_local_csv(self, data_dict, filename):
        try:
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=["param", "value"])
                writer.writeheader()
                for key, value in data_dict.items():
                    writer.writerow({"param": key, "value": str(value)})
            print(f"saved to {filename}")
        except Exception as e:
            print(f"Failed to save: {e}")

    def setup_ui(self):
        os.popen('sudo hciconfig hci0 reset')
        main_layout = QVBoxLayout()

        # ==== Top Bar ====
        top_bar = QHBoxLayout()

        # Toggle Unit (moved to left)
        self.lbl_unit = QLabel("Unit")
        self.lbl_unit.setStyleSheet(f"font-size: {int(self.base_font_size * 1.2)}px;")

        self.lbl_mgl = QLabel("mg/l")
        
        if self.unit == "percent":
            self.unit_toggle = ToggleSwitch(checked=True)
            self.lbl_mgl.setStyleSheet(f"font-size: {int(self.base_font_size * 1.4)}px;")
        else:
            self.unit_toggle = ToggleSwitch(checked=False)
            self.lbl_mgl.setStyleSheet(f"font-size: {int(self.base_font_size * 1.4)}px; font-weight: bold;")
        self.unit_toggle.toggled.connect(self.on_toggle_click)

        self.lbl_percent = QLabel("%")
        if self.unit == "percent":
            self.lbl_percent.setStyleSheet(f"font-size: {int(self.base_font_size * 1.4)}px; font-weight: bold;")
        else:
            self.lbl_percent.setStyleSheet(f"font-size: {int(self.base_font_size * 1.4)}px;")

        # top_bar.addWidget(self.lbl_unit)
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
                background-color: rgba(255, 255, 255, 40);  /* สีขาวจางๆ ตอน hover */
                border-radius: 5px;
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 80);  /* สีขาวเข้มขึ้นตอนกด */
                border-radius: 5px;
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
        labels = [
            ("Pond ID:", "PID"),
            ("HBOI ID:", "SID"),
            # ("Sensor Connection Status:", "SCS"),
            # ("Sensor Battery:", "SB"),
            ("HBOI DO:", "SDL"),
            ("YSI DO:", "YSI"),
            ("Timer:", "TIMER"),
            # ("GPS:", "GPS"),
            ("Last Calibration:", "CAL_DT"),
        ]
        for i, (key_text, key_id) in enumerate(labels):
            key_label = QLabel(key_text)
            val_label = self.data_labels[key_id]

            key_label.setStyleSheet(f"font-size: {self.label_font_size_large}px; padding-right: 20px;")
            val_label.setStyleSheet(f"font-size: {self.label_font_size_large}px; font-weight: bold; padding-left: 20px;")

            info_grid.addWidget(key_label, i, 0, Qt.AlignRight)
            info_grid.addWidget(val_label, i, 1, Qt.AlignLeft)

        main_layout.addLayout(info_grid)

        # ==== Bottom Buttons ====
        btn_layout = QHBoxLayout()
        buttons = [
            ("Calibrate DO", self.on_calibrate_click),
            ("Manual/Auto\nPond ID", self.on_manual_auto_click),
            ("Set\nPond ID", self.on_set_pond_click),
            ("History\nLog", self.on_history_log_click),
        ]

        for label, handler in buttons:
            btn = QPushButton(label)
            btn.setFixedHeight(self.base_font_size * 3)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #333;
                    border: 1px solid white;
                    color: white;
                    font-size: {int(self.base_font_size * 0.9)}px;
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
            if label in ["Manual/Auto\nPond ID", "Set\nPond ID"]:
                btn.setVisible(False)
            btn_layout.addWidget(btn)

        main_layout.addLayout(btn_layout)
        self.setLayout(main_layout)

        # ==== Log Display (Below Buttons) ====
        log_layout = QHBoxLayout()
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(0)

        # Container widget layout
        log_container = QWidget()
        log_container.setStyleSheet("background-color: #eeeeee;")
        log_container.setMaximumHeight(int(self.base_font_size * 1.2))

        log_inner_layout = QHBoxLayout()
        log_inner_layout.setContentsMargins(10, 2, 10, 2)  # padding

        self.log_label = QLabel("System ready.")
        self.log_label.setStyleSheet(f"""
            color: #000000;
            font-size: {int(self.base_font_size * 0.5)}px;
        """)
        self.log_label.setFixedHeight(int(self.base_font_size * 0.7))  
        log_inner_layout.addWidget(self.log_label)
        log_container.setLayout(log_inner_layout)

        log_layout.addWidget(log_container)
        main_layout.addLayout(log_layout)

        self.update_value("CAL_DT", self.last_calibration)

    def setup_timer(self):
        self.timer_active = False
        self.counter_time = 0

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_counter)
        self.timer.start(1000)

    def setup_thread(self):
        self.thread = TruckSensor()

        self.thread.fb_key = self.settings['fb_key']
        self.thread.max_fail = int(self.settings['upload_firebase_max_counter'])
        self.thread.do_vals_log = self.settings['do_vals']
        self.thread.log_folder = self.settings['log_folder']
        self.thread.database_folder = self.settings['database_folder']
        self.thread.unsaved_json = self.settings['unsaved_json'] #TODO REMOVE THIS
        self.thread.unit = self.unit
        self.thread.YSI_folder = self.settings['ysi_vals']

        self.thread.initialize()
        self.thread.update_data.connect(self.on_data_update)
        self.thread.finished.connect(self.on_thread_finished)
        self.thread.status_data.connect(self.on_status_update)
        self.thread.update_pond_data.connect(self.on_update_pond_data)
        self.thread.counter_is_running.connect(self.on_counter_running)
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
            if self.is_first:
                self.led_status.set_status("connected_ready")
                self.log_label.setText("Sensor is ready to use.")
                self.is_first = False
        if 'connection' in data_dict:
            # self.update_value("SCS", data_dict["connection"])
            if data_dict['connection'] == "connected":
                if self.check_conn_first:
                    self.led_status.set_status("connected_not_ready")
                    self.check_conn_first = False
                else:
                    self.led_status.set_status("connected_ready")
            else:
                self.led_status.set_status("disconnected")
        if 'name' in data_dict:
            self.update_value("SID", data_dict["name"])
        if 'gps' in data_dict:
            self.update_value("PID", data_dict["pid"])
        if 'do' in data_dict:
            if self.unit == "percent":
                self.update_value("SDL", f"{100 * data_dict['do']:.2f}")
            else:
                self.update_value("SDL", f"{data_dict['do_mgl']:.2f}")

            # update label color based on mgl value in setting.setting
            do_val = data_dict['do_mgl']
            if do_val < self.min_do:
                self.data_labels["SDL"].setStyleSheet(f"font-size: {self.label_font_size_large}px; font-weight: bold; padding-left: 20px; color: red;")
            elif self.min_do <= do_val < self.good_do:
                self.data_labels["SDL"].setStyleSheet(f"font-size: {self.label_font_size_large}px; font-weight: bold; padding-left: 20px; color: yellow;")
            else:
                self.data_labels["SDL"].setStyleSheet(f"font-size: {self.label_font_size_large}px; font-weight: bold; padding-left: 20px; color: limegreen;")
        
        if 'ysi_do' in data_dict:
            self.on_ysi_update(do_ps=data_dict['ysi_do'], do_mgl=data_dict['ysi_do_mgl'])

        if 'mouse' in data_dict:
            if data_dict['mouse'] == 'normal':
                QApplication.restoreOverrideCursor()
            else:
                QApplication.setOverrideCursor(Qt.WaitCursor)

    
    def on_status_update(self, value):
        self.log_label.setText(value)

    def on_counter_running(self, value):
        if value == "True":
            if not self.timer_active:
                self.counter_time = 0
            self.timer_active = True
        else:
            self.timer_active = False

    def on_ysi_update(self, do_ps, do_mgl):
        if self.unit == "percent":
            # water temperature and/or pressure have not been recorded
            if do_ps == -1:
                self.update_value("YSI", "N/A")
            else:
                self.update_value("YSI", f"{100 * do_ps:.2f}")
        else:
            self.update_value("YSI", f"{do_mgl:.2f}")

        # update ysi color
        if do_mgl < self.min_do:
            self.data_labels["YSI"].setStyleSheet(f"font-size: {self.label_font_size_large}px; font-weight: bold; padding-left: 20px; color: red;")
        elif self.min_do <= do_mgl < self.good_do:
            self.data_labels["YSI"].setStyleSheet(f"font-size: {self.label_font_size_large}px; font-weight: bold; padding-left: 20px; color: yellow;")
        else:
            self.data_labels["YSI"].setStyleSheet(f"font-size: {self.label_font_size_large}px; font-weight: bold; padding-left: 20px; color: limegreen;")

    def update_counter(self):
        if self.timer_active:
            if hasattr(self, 'result_window') and self.result_window is not None:
                if self.result_window.isVisible():
                    self.result_window.close()
                self.result_window = None

            self.counter_time += 1
            self.thread.sample_stop_time = self.counter_time
            if self.counter_time < self.settings['underwater_counter']:
                self.update_value("TIMER", str(self.counter_time) + " s collecting")
            else:
                self.update_value("TIMER", str(self.counter_time) + " s ready to pick-up")
        else:
            if self.counter_time > 0:
                self.update_value("TIMER", str(self.counter_time) + " s collection stoped")
            else:
                self.update_value("TIMER", str(self.counter_time) + " s")

    def on_update_pond_data(self, data_dict):
        self.result_window = ResultWindow(auto_close_sec=int(self.settings['autoclose_sec']))
        self.result_window.closed_data.connect(self.on_result_window_closed)
        self.result_window.unit = self.unit
        self.result_window.good_do = self.good_do
        self.result_window.min_do = self.min_do

        if 'pid' in data_dict:
            self.result_window.update_value("PID", data_dict["pid"])
            self.result_window.pond_id = data_dict["pid"]
        else:
            self.result_window.update_value("PID", "-1")

        self.result_window.temp_c = data_dict['water_temp']
        self.result_window.update_value("Temp", f"{to_fahrenheit(data_dict['water_temp']):.2f} °F")
        self.result_window.pressure = data_dict['sample_depth']
        self.result_window.update_value("Press", f"{data_dict['sample_depth']:.2f} in")

        # HANDLE DO CONVERSIONS
        if self.unit == "percent":
            self.result_window.update_value("HBOI", f"{100 * data_dict['do']:.2f}")
            self.result_window.update_value("YSI", f"{100 * data_dict['ysi_do']:.2f}")
        else:
            self.result_window.update_value("HBOI", f"{data_dict['do_mgl']:.2f}")
            self.result_window.update_value("YSI", f"{data_dict['ysi_do_mgl']:.2f}")

        self.result_window.update_value("SD", str(self.counter_time))

        now = datetime.now()
        formatted_time = now.strftime("%b %d %I:%M %p")
        self.result_window.update_value("Date", formatted_time)
        self.result_window.measure_datetime = now

        self.result_window.set_do_temp_pressure(data_dict, sample_stop_time=30)
        self.result_window.plot_hourly_do_barchart()

    def on_result_window_closed(self, result_data):
        # print("Result window closed. Data received:", result_data)
        self.thread.update_database(result_data)
        self.result_window = None

    def on_thread_finished(self):
        print("Thread Abort")

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

    def update_value(self, key, value):
        if key in self.data_labels:
            self.data_labels[key].setText(str(value))

    def on_calibrate_click(self):
        dialog = CustomYesNoDialog(
            "Get sensor ready:\n"
            "1) Dip in water\n"
            "2) Shake off water\n"
            "3) Press Yes to start CALIBRATION\n\n"
            "Are you sure you want to\nCALIBRATE DO?",
            self
        )

        if dialog.exec_() == QDialog.Accepted:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            print("ok, calibrate")
            self.thread.messaging_active = False
            self.thread.calibrate_DO()
            QApplication.restoreOverrideCursor()

            self.thread.messaging_active = True
            now = datetime.now()
            formatted_time = now.strftime("%b %d, %Y %I:%M %p") 
            self.last_calibration = formatted_time
            self.calibration['last_calibration'] = self.last_calibration
            self.update_value("CAL_DT", self.last_calibration)
            self.save_local_csv(self.calibration, "calibration.csv")
        else:
            print("User clicked No")
        
    def on_manual_auto_click(self):
        print("?? Manual/Auto Pond ID clicked")
        print("try to read msg")

    def on_set_pond_click(self):
        print("?? Set Pond ID clicked")

    def on_history_log_click(self):
        print("?? History Log clicked")
        window = HistoryLogWindow(self.unit, self.settings['database_folder'], self.min_do, self.good_do, parent=self)
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
            self.save_local_csv(self.settings, "settings.csv")()
            # print("Updated:", new_values)

    def closeEvent(self, event):
        dialog = ShutdownDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            if dialog.result == "close":
                self.thread.stop_ysi()
                self.thread.abort()
                self.thread.stop_firebase()
                if hasattr(self, 'result_window') and self.result_window is not None:
                    if self.result_window.isVisible():
                        self.result_window.close()
                    self.result_window = None
                self.thread.update_logger_text("info", "Program close.")
                print("Program close")
                super().closeEvent(event)

            elif dialog.result == "shutdown":
                print("Shutting down...")
                self.thread.stop_ysi()
                self.thread.abort()
                self.thread.stop_firebase()
                if hasattr(self, 'result_window') and self.result_window is not None:
                    if self.result_window.isVisible():
                        self.result_window.close()
                    self.result_window = None
                self.thread.update_logger_text("info", "Program close.")
                os.system("sudo shutdown now")
                event.ignore()  # ไม่ให้ close ที่นี่ ให้ OS จัดการ

            elif dialog.result == "restart":
                print("Rebooting...")
                self.thread.stop_ysi()
                self.thread.abort()
                self.thread.stop_firebase()
                if hasattr(self, 'result_window') and self.result_window is not None:
                    if self.result_window.isVisible():
                        self.result_window.close()
                    self.result_window = None
                self.thread.update_logger_text("info", "Program close.")
                os.system("sudo reboot")
                event.ignore()

            else:
                event.ignore()

        else:
            # User pressed Cancel or closed dialog
            event.ignore()

        


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DOApp()
    sys.exit(app.exec_())
