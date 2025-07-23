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
from converter import convert_mgl_to_percent, convert_percent_to_mgl, to_celcius
from shutdown_dialog import ShutdownDialog
from history_window import HistoryLogWindow
from setting_dialog import SettingDialog
from custom_yesno_dialog import CustomYesNoDialog

class DOApp(QWidget):
    def __init__(self):
        super().__init__()

        # QApplication.setOverrideCursor(Qt.WaitCursor)

        self.current_time = datetime.now()

        self.setWindowTitle("DO Monitor")
        self.setStyleSheet("background-color: #4D4D4D; color: white;")

        # ?????????????
        screen_size = QApplication.primaryScreen().size()
        self.base_font_size = int(screen_size.height() * 0.03)  # ~3% ????????????
        self.label_font_size = int(screen_size.height() * 0.05)
        self.label_font_size_large = int(screen_size.height() * 0.07)

        # ???? QLabel ??? value
        self.data_labels = {
            "PID": QLabel("-1"),
            "SID": QLabel("-1"),
            "SCS": QLabel("connecting..."),
            "SB": QLabel("Reading Batt..."),
            "SDL": QLabel("-"),
            "YSI": QLabel("-"),
            "Time S": QLabel("00:00"),
            "Date Time": QLabel("N/A"),
            "GPS": QLabel("-1, -1"),
        }

        self.is_first = True
        self.check_conn_first = True
        self.load_settings()
        self.setup_ui()
        self.showFullScreen()
        self.setup_thread()
        self.setup_timer()

    def load_settings(self, filename="setting.setting"):
        self.settings = {}
        if os.path.exists(filename):
            with open(filename, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    key = row['param']
                    value = row['value']
                    self.settings[key] = value
        else:
            print(f"Settings file '{filename}' not found.")

        self.fb_key = self.settings.get("fb_key", "fb_key.json") #
        self.do_vals_log = self.settings.get("do_vals", "DO_data/") #
        self.log_folder = self.settings.get("log_folder", "log") #
        self.database_folder = self.settings.get("database_folder", "database_truck") #
        self.upload_firebase_max_counter = int(self.settings.get("upload_firebase_max_counter", 30)) #
        self.truck_id = self.settings.get("truck_id", "truck") #
        self.unsaved_json = self.settings.get("unsaved_json", "unsaved_json/")

        self.unit = self.settings.get("unit", "mgl")
        self.auto_close_time = int(self.settings.get("autoclose_sec", 10)) #
        self.underwater_time = int(self.settings.get("underwater_counter", 30)) #
        self.batt_full = float(self.settings.get("max_battv", 4.2)) #
        self.batt_empty = float(self.settings.get("min_battv", 3.2)) #
        self.batt_low_v = 3.42
        self.YSI_folder = self.settings.get("ysi_vals", "YSI_data/")

        self.min_do = float(self.settings.get("min_do", 4))
        self.good_do = float(self.settings.get("good_do", 4))

        self.last_calibration = self.settings.get("last_calibration", "N/A")

    def update_setting(self, key, value):
        self.settings[key] = str(value)

    def save_settings(self, filename="setting.setting"):
        try:
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=["param", "value"])
                writer.writeheader()
                for key, value in self.settings.items():
                    writer.writerow({"param": key, "value": value})
            print(f"Settings saved to {filename}")
        except Exception as e:
            print(f"Failed to save settings: {e}")

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

        top_bar.addWidget(self.lbl_unit)
        top_bar.addSpacing(10)
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
            ("Sensor ID:", "SID"),
            # ("Sensor Connection Status:", "SCS"),
            # ("Sensor Battery:", "SB"),
            ("Sensor DO Live:", "SDL"),
            ("YSI DO Live:", "YSI"),
            ("Timer:", "Time S"),
            # ("GPS:", "GPS"),
            ("Last Calibration:", "Date Time"),
        ]
        for i, (key_text, key_id) in enumerate(labels):
            key_label = QLabel(key_text)
            val_label = self.data_labels[key_id]

            if key_id == "PID" or key_id == "SDL" or key_id == "YSI":
                key_label.setStyleSheet(f"font-size: {self.label_font_size_large}px; padding-right: 20px;")
                val_label.setStyleSheet(f"font-size: {self.label_font_size_large}px; font-weight: bold; padding-left: 20px;")
            else:
                key_label.setStyleSheet(f"font-size: {self.label_font_size}px; padding-right: 20px;")
                val_label.setStyleSheet(f"font-size: {self.label_font_size}px; font-weight: bold; padding-left: 20px;")

            info_grid.addWidget(key_label, i, 0, Qt.AlignRight)
            info_grid.addWidget(val_label, i, 1, Qt.AlignLeft)

        main_layout.addLayout(info_grid)

        # ==== Bottom Buttons ====
        btn_layout = QHBoxLayout()
        # ????: [Label, Handler function]
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
            btn.clicked.connect(handler)  # ? ?????? handler ?????????
            if label in ["Manual/Auto\nPond ID", "Set\nPond ID"]:
                btn.setVisible(False)  # 👈 ซ่อนไว้ก่อน
            btn_layout.addWidget(btn)

        main_layout.addLayout(btn_layout)
        self.setLayout(main_layout)

        # ==== Log Display (Below Buttons) ====
        log_layout = QHBoxLayout()
        log_layout.setContentsMargins(0, 0, 0, 0)  # ลบขอบ
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

        self.update_value("Date Time", self.last_calibration)

    def setup_timer(self):
        self.timer_active = False
        self.counter_time = 0

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_counter)
        self.timer.start(1000)

    def setup_thread(self):
        self.thread = TruckSensor()

        self.thread.truck_id = self.truck_id
        self.thread.fb_key = self.fb_key
        self.thread.max_fail = self.upload_firebase_max_counter
        self.thread.do_vals_log = self.do_vals_log
        self.thread.log_folder = self.log_folder
        self.thread.database_folder = self.database_folder
        self.thread.unsaved_json = self.unsaved_json
        self.thread.unit = self.unit
        self.thread.YSI_folder = self.YSI_folder

        self.thread.initialize()
        self.thread.update_data.connect(self.on_data_update)
        self.thread.finished.connect(self.on_thread_finished)
        self.thread.status_data.connect(self.on_status_update)
        self.thread.update_pond_data.connect(self.on_update_pond_data)
        self.thread.counter_is_running.connect(self.on_counter_running)
        self.thread.start()
        self.ble_running = True

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()

    def on_data_update(self, data_dict):
        if 'battv' in data_dict:
            # if data_dict["battv"] <= self.batt_low_v and "not charging" == data_dict['batt_status'][:12]:
            #     self.update_value("SB", str(data_dict["battv"]) + "V " + "Battery low")
            # else:
            #     self.update_value("SB", str(data_dict["battv"]) + "V " + data_dict['batt_status'])
            batt_percent = int((data_dict["battv"] - self.batt_empty) / (self.batt_full - self.batt_empty) * 100)
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
            # self.update_value("GPS", str(data_dict["lat"]) + ", " + str(data_dict["lng"]))
        if 'do' in data_dict:
            self.update_value("SDL", f"{data_dict['do']:.2f}")
            if self.unit == "percent":
                t = to_celcius(self.thread.sdata["temp"][0])
                p = self.thread.sdata["pressure"][0]
                do_val = convert_percent_to_mgl(data_dict['do'], t, p)
            else:
                do_val = data_dict['do']
            key = "SDL"
            # print("do_val", do_val)
            if do_val < self.min_do:
                self.data_labels[key].setStyleSheet(f"font-size: {self.label_font_size_large}px; font-weight: bold; padding-left: 20px; color: red;")
            elif self.min_do <= do_val < self.good_do:
                self.data_labels[key].setStyleSheet(f"font-size: {self.label_font_size_large}px; font-weight: bold; padding-left: 20px; color: yellow;")
            else:
                self.data_labels[key].setStyleSheet(f"font-size: {self.label_font_size_large}px; font-weight: bold; padding-left: 20px; color: limegreen;")
        if 'mouse' in data_dict:
            if data_dict['mouse'] == 'normal':
                QApplication.restoreOverrideCursor()
            else:
                QApplication.setOverrideCursor(Qt.WaitCursor)
        if 'ysi' in data_dict:
            self.update_value("YSI", f"{data_dict['ysi']:.2f}")
            
            if self.unit == "percent":
                t = to_celcius(self.thread.sdata["temp"][0])
                p = self.thread.sdata["pressure"][0]
                do_val = convert_percent_to_mgl(data_dict['ysi'], t, p)
            else:
                do_val = data_dict['ysi']
            key = "YSI"
            if do_val < self.min_do:
                self.data_labels[key].setStyleSheet(f"font-size: {self.label_font_size_large}px; font-weight: bold; padding-left: 20px; color: red;")
            elif self.min_do <= do_val < self.good_do:
                self.data_labels[key].setStyleSheet(f"font-size: {self.label_font_size_large}px; font-weight: bold; padding-left: 20px; color: yellow;")
            else:
                self.data_labels[key].setStyleSheet(f"font-size: {self.label_font_size_large}px; font-weight: bold; padding-left: 20px; color: limegreen;")
    
    def on_status_update(self, value):
        self.log_label.setText(value)

    def on_counter_running(self, value):
        if value == "True":
            if not self.timer_active:
                self.counter_time = 0
            self.timer_active = True
        elif value == "False":
            self.timer_active = False
            # self.counter_time = 0
        else:
            self.timer_active = False
            self.counter_time = 0

    def update_counter(self):
        if self.timer_active:
            if hasattr(self, 'result_window') and self.result_window is not None:
                if self.result_window.isVisible():
                    self.result_window.close()  # ✅ ปิดเฉพาะถ้ายังเปิดอยู่
                self.result_window = None  # 🔄 reset ตัวแปร เพื่อให้รู้ว่าไม่มีแล้ว

            self.counter_time += 1
            self.thread.sample_stop_time = self.counter_time
            if self.counter_time < self.underwater_time:
                self.update_value("Time S", str(self.counter_time) + " s Collecting data")
            else:
                self.update_value("Time S", str(self.counter_time) + " s Collecting, Ready to pick up")
                self.thread.tricker_30sec()
        else:
            if self.counter_time > 0:
                self.update_value("Time S", str(self.counter_time) + " s Collect data stop")
            else:
                self.update_value("Time S", str(self.counter_time) + " s")

    def on_update_pond_data(self, data_dict):
        self.result_window = ResultWindow(auto_close_sec=self.auto_close_time)
        self.result_window.closed_data.connect(self.on_result_window_closed)
        self.result_window.unit = self.unit
        self.result_window.good_do = self.good_do
        self.result_window.min_do = self.min_do

        # ตั้งค่า
        if 'pid' in data_dict:
            self.result_window.update_value("PID", data_dict["pid"])
            self.result_window.pond_id = data_dict["pid"]
        else:
            self.result_window.update_value("PID", "-1")
        if 'temp' in data_dict:
            self.result_window.temp_c = to_celcius(data_dict['temp'][0])
            self.result_window.update_value("Temp", f"{data_dict['temp'][0]:.2f} °F")
        if 'pressure' in data_dict:
            self.result_window.pressure = data_dict['pressure'][0]
            self.result_window.update_value("Press", f"{data_dict['pressure'][0]:.2f} HPA")
        if 'do' in data_dict:
            self.result_window.do_val_current = data_dict["do"]
            if self.unit == "mgl":
                self.result_window.do_val_current = data_dict["do"]
            else:
                self.result_window.do_val_current = convert_percent_to_mgl(data_dict["do"], self.result_window.temp_c, self.result_window.pressure)
            self.result_window.update_value("HBOI", f"{data_dict['do']:.2f}")
        if 'ysi' in data_dict:
            if self.unit == "mgl":
                self.result_window.ysi_val_current = data_dict["ysi"]
            else:
                self.result_window.ysi_val_current = convert_percent_to_mgl(data_dict["ysi"], self.result_window.temp_c, self.result_window.pressure)

            self.result_window.update_value("YSI", f"{data_dict['ysi']:.2f}")

        self.result_window.update_value("SD", str(self.counter_time))

        now = datetime.now()
        formatted_time = now.strftime("%b %d %I:%M %p")  # <== รูปแบบตามที่คุณต้องการ
        self.result_window.update_value("Date", formatted_time)
        self.result_window.measure_datetime = now

        is_30sec = self.thread.is_30sec
        data_size_at30sec = self.thread.data_size_at30sec
        sample_stop_time = self.thread.sample_stop_time

        self.result_window.set_do_temp_pressure(data_dict['do_vals'], data_dict['temp_vals'], data_dict['pressure_vals'])
        self.result_window.plot_hourly_do_barchart()

    def on_result_window_closed(self, result_data):
        # print("Result window closed. Data received:", result_data)
        self.thread.update_database(result_data)
        self.result_window = None

    def on_thread_finished(self):
        # self.ble_running = False
        # self.log_label.setText("Sensor stop main process")
        # self.thread.update_logger_text("info", "DO Sensor thread aborted.")
        print("Thread Abort")

    def on_toggle_click(self):
        if self.unit_toggle.isChecked() and self.unit != "percent":
            self.lbl_mgl.setStyleSheet(f"font-size: {int(self.base_font_size * 1.2)}px; font-weight: normal;")
            self.lbl_percent.setStyleSheet(f"font-size: {int(self.base_font_size * 1.2)}px; font-weight: bold;")
            self.unit = "percent"
            self.update_setting("unit", "percent")
            self.save_settings()
        elif self.unit == "percent":
            self.lbl_mgl.setStyleSheet(f"font-size: {int(self.base_font_size * 1.2)}px; font-weight: bold;")
            self.lbl_percent.setStyleSheet(f"font-size: {int(self.base_font_size * 1.2)}px; font-weight: normal;")
            self.unit = "mgl"
            self.update_setting("unit", "mgl")
            self.save_settings()
        
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
            self.thread.abort()
            while not self.thread._abort:
                time.sleep(0.2)
            self.thread.calibrate_DO()
            # restart after calibrate done
            self.thread.start()
            # self.ble_running = True
            QApplication.restoreOverrideCursor()

            now = datetime.now()
            formatted_time = now.strftime("%b %d, %Y %I:%M %p")  # <== รูปแบบตามที่คุณต้องการ
            self.last_calibration = formatted_time

            self.update_value("Date Time", self.last_calibration)
            self.update_setting("last_calibration", self.last_calibration)
            self.save_settings()
        else:
            print("User clicked No")
        
    def on_manual_auto_click(self):
        print("?? Manual/Auto Pond ID clicked")
        print("try to read msg")

    def on_set_pond_click(self):
        print("?? Set Pond ID clicked")

    def on_history_log_click(self):
        print("?? History Log clicked")
        window = HistoryLogWindow(self.unit, self.database_folder, self.min_do, self.good_do, parent=self)
        window.exec_()  # ถ้าอยากให้เป็น modal dialog

    def open_settings_dialog(self):
        dialog = SettingDialog(min_do=self.min_do, good_do=self.good_do, autoclose_sec=self.auto_close_time)
        if dialog.exec_():
            new_values = dialog.get_values()
            self.min_do = new_values["min_do"]
            self.good_do = new_values["good_do"]
            self.auto_close_time = new_values["autoclose_sec"]
            self.update_setting("min_do", self.min_do)
            self.update_setting("good_do", self.good_do)
            self.update_setting("autoclose_sec", self.auto_close_time)
            self.save_settings()
            # print("Updated:", new_values)

    # def closeEvent(self, event):
    #     self.thread.stop_ysi()
    #     self.thread.abort()
    #     self.thread.stop_firebase()
    #     if hasattr(self, 'result_window') and self.result_window is not None:
    #         if self.result_window.isVisible():
    #             self.result_window.close()  # ✅ ปิดเฉพาะถ้ายังเปิดอยู่
    #         self.result_window = None  # 🔄 reset ตัวแปร เพื่อให้รู้ว่าไม่มีแล้ว
    #     self.thread.update_logger_text("info", "Program close.")
    #     print("Program close")
    #     super().closeEvent(event)

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
