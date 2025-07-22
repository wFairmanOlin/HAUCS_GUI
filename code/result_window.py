from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QCheckBox, QGridLayout, QSizePolicy, QDialog
)

from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import Qt, QTimer, QSize
import os
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QInputDialog
from numpad_dialog import NumpadDialog
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import numpy as np
from scipy.optimize import curve_fit
import io
import re
import pandas as pd
from datetime import datetime, timedelta
from converter import convert_percent_to_mgl, to_celcius, convert_mgl_to_percent

class ResultWindow(QWidget):
    closed_data = pyqtSignal(dict)
    image_path=None
    do_vals = []
    temp_vals = []
    pressure_vals = []
    database_truck = "database_truck"
    do_val_current = 0.0
    measure_datetime = None
    pond_id = "unk"
    min_do = 4
    good_do = 5
    ysi_val_current = 0.0
    unit = "percent"
    temp_c = 0
    pressure = 0

    def __init__(self, auto_close_sec=10):
        super().__init__()
        self.auto_close_sec = auto_close_sec
        self.remaining_time = auto_close_sec
        self.timer_active = True

        self.setWindowTitle("Result Summary")
        self.setup_ui(self.image_path)
        self.setup_timer()
        self.show()

    def setup_ui(self, image_path):
        screen = self.screen().size()
        w = int(screen.width() * 0.98)
        h = int(screen.height() * 0.90)
        font_size = int(h * 0.05)
        self.font_size = font_size
        large_font_size = int(h * 0.08)
        self.large_font_size = large_font_size
        btn_font_size = int(h * 0.03)

        self.setGeometry(
            # int((screen.width() - w) / 2),
            # int((screen.height() - h) / 3),
            10, 0,
            w, h
        )
        self.setStyleSheet("background-color: #4D4D4D; color: white;")

        layout_main = QVBoxLayout()

        # === Top Layout ===
        layout_top = QHBoxLayout()

        # === Left Layout (40%) ===
        layout_left = QVBoxLayout()
        info_grid = QGridLayout()
        self.data_labels = {}

        labels = [
            ("Pond ID:", "PID"),
            ("Duration:", "SD"),
            ("Water temp:", "Temp"),
            ("Last Time:", "Date"),
            ("HBOI DO:", "HBOI"),
            ("YSI DO:", "YSI"),
            ("Pressure:", "Press"),
        ]

        for i, (text, key) in enumerate(labels):
            label = QLabel(text)
            if text == "Pond ID:" or text == "HBOI DO:":
                label.setStyleSheet(f"font-size: {large_font_size}px; padding-right: 5px;")
            else:
                label.setStyleSheet(f"font-size: {font_size}px; padding-right: 5px;")

            if key == "PID":
                # → widget แบบ HBox สำหรับ PID + ปุ่ม
                pid_layout = QHBoxLayout()
                pid_layout.setSpacing(int(font_size * 1.0))  # เพิ่มระยะห่างระหว่าง label กับปุ่ม
                value = QLabel("-")
                value.setStyleSheet(f"font-size: {large_font_size}px; font-weight: bold; padding-left: 5px;")
                self.data_labels[key] = value

                btn_edit = QPushButton("Edit")
                btn_edit.setStyleSheet(f"font-size: {int(large_font_size*0.6)}px; padding: 0px; color: black;")
                btn_edit.setFixedHeight(int(large_font_size * 1.2))
                btn_edit.setFixedWidth(int(large_font_size * 2.4))
                btn_edit.clicked.connect(self.edit_pid_dialog)

                pid_layout.addWidget(value)
                pid_layout.addWidget(btn_edit)
                pid_widget = QWidget()
                pid_widget.setLayout(pid_layout)
                info_grid.addWidget(label, i, 0, Qt.AlignRight)
                info_grid.addWidget(pid_widget, i, 1, Qt.AlignLeft)
            else:
                value = QLabel("-")
                if text == "Pond ID:" or text == "HBOI DO:":
                    value.setStyleSheet(f"font-size: {large_font_size}px; font-weight: bold; padding-left: 5px;")
                else:
                    value.setStyleSheet(f"font-size: {font_size}px; font-weight: bold; padding-left: 5px;")
                
                info_grid.addWidget(label, i, 0, Qt.AlignRight)
                info_grid.addWidget(value, i, 1, Qt.AlignLeft)
                self.data_labels[key] = value

        layout_left.addStretch()
        layout_left.addLayout(info_grid)
        layout_left.addStretch()
        layout_top.addLayout(layout_left, stretch=5)

        # === Right Layout (60%) ===
        layout_right = QVBoxLayout()
        self.img_label = QLabel()
        # ปรับขนาดให้ประมาณ 90% ของ layout_right (60% ของหน้าจอ)
        img_width = int(w * 0.5)   # 0.9 * 60%
        img_height = int(h * 0.4)   # 60% ของความสูงหน้าจอ

        self.img_label.setFixedSize(img_width, img_height)
        self.img_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setStyleSheet("background-color: navy blue; color: black; border: 1px solid black;")

        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path).scaled(
                self.img_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.img_label.setPixmap(pixmap)
        else:
            self.img_label.setText("DO Chart")

        layout_right.addStretch()
        layout_right.addWidget(self.img_label, alignment=Qt.AlignCenter)
        layout_right.addStretch()

        # image 2 (อยู่ด้านล่าง แต่ซ่อนก่อน)
        self.img_label2 = QLabel()
        self.img_label2.setFixedSize(img_width, img_height)
        self.img_label2.setAlignment(Qt.AlignCenter)
        self.img_label2.setStyleSheet("background-color: #c1c1c1; border: 1px solid white;")
        self.img_label2.setText("Engineering Image")
        self.img_label2.setVisible(False)  # ซ่อนก่อน
        layout_right.addStretch()
        layout_right.addWidget(self.img_label2, alignment=Qt.AlignCenter)
        layout_top.addLayout(layout_right, stretch=5)

        layout_main.addLayout(layout_top)

        # === Bottom Layout ===
        layout_bottom = QHBoxLayout()

        # Button Engineering
        self.btn_engineering = QPushButton("Engineering\nAnalysis")
        self.set_btn_style(self.btn_engineering, btn_font_size)
        self.btn_engineering.clicked.connect(self.on_engineering_click)

        # Button Close
        self.btn_close = QPushButton(f"Auto Close in {self.remaining_time} sec...")
        self.set_btn_style(self.btn_close, btn_font_size)
        self.btn_close.clicked.connect(self.close)

        btn_width = int(w / 6)
        btn_height = int(h * 0.09)
        self.btn_engineering.setFixedSize(btn_width, btn_height)
        self.btn_close.setFixedSize(btn_width, btn_height)

        layout_bottom.addWidget(self.btn_engineering, alignment=Qt.AlignLeft)

        # Checkbox + Close Button (stacked)
        layout_close = QVBoxLayout()
        self.checkbox_pause = QCheckBox("Pause Auto Close")
        self.checkbox_pause.setStyleSheet(f"font-size: {btn_font_size}px;")
        self.checkbox_pause.setChecked(False)
        self.checkbox_pause.stateChanged.connect(self.on_pause_toggle)
        layout_close.addWidget(self.checkbox_pause, alignment=Qt.AlignRight)
        layout_close.addWidget(self.btn_close, alignment=Qt.AlignRight)

        layout_bottom.addStretch()
        layout_bottom.addLayout(layout_close)

        layout_main.addLayout(layout_bottom)

        self.setLayout(layout_main)

    def setup_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_countdown)
        self.timer.start(1000)

    def update_countdown(self):
        if self.timer_active:
            self.remaining_time -= 1
            if self.remaining_time <= 0:
                self.close()
            else:
                self.btn_close.setText(f"Auto Close in {self.remaining_time} sec...")

    def on_pause_toggle(self, state):
        self.timer_active = not bool(state)
        self.checkbox_pause.setEnabled(False)
        self.btn_close.setText(f"Close")

    def on_engineering_click(self):
        self.timer_active = False
        self.checkbox_pause.setChecked(True)
        self.checkbox_pause.setEnabled(False)
        self.btn_close.setText(f"Close")
        self.img_label2.setVisible(True)
        print("Engineering Analysis clicked")

    def mousePressEvent(self, event):
        clicked_widget = self.childAt(event.pos())

        # ถ้าไม่ได้คลิกที่ปุ่ม Close
        if clicked_widget != self.btn_close:
            if self.timer_active:
                self.timer_active = False
                self.checkbox_pause.setChecked(True)
                self.checkbox_pause.setEnabled(False)
                self.btn_close.setText("Close")

        # อย่าลืม call ฟังก์ชันของ superclass ด้วย
        super().mousePressEvent(event)

    def set_btn_style(self, btn, font_size=14):
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #333;
                border: 1px solid white;
                color: white;
                font-size: {font_size}px;
            }}
            QPushButton:hover {{
                background-color: #555;
            }}
            QPushButton:pressed {{
                background-color: #2ecc71;
            }}
        """)

    def update_value(self, key, value):
        if key in self.data_labels:
            self.data_labels[key].setText(str(value))
            if key == "HBOI":
                if self.do_val_current < self.min_do:
                    self.data_labels[key].setStyleSheet(f"font-size: {self.large_font_size}px; font-weight: bold; padding-left: 5px; color: red;")
                elif self.min_do <= self.do_val_current < self.good_do:
                    self.data_labels[key].setStyleSheet(f"font-size: {self.large_font_size}px; font-weight: bold; padding-left: 5px; color: yellow;")
                else:
                    self.data_labels[key].setStyleSheet(f"font-size: {self.large_font_size}px; font-weight: bold; padding-left: 5px; color: limegreen;")

            elif key == "YSI":
                if self.ysi_val_current < self.min_do:
                    self.data_labels[key].setStyleSheet(f"font-size: {self.font_size}px; font-weight: bold; padding-left: 5px; color: red;")
                elif self.min_do <= self.ysi_val_current < self.good_do:
                    self.data_labels[key].setStyleSheet(f"font-size: {self.font_size}px; font-weight: bold; padding-left: 5px; color: yellow;")
                else:
                    self.data_labels[key].setStyleSheet(f"font-size: {self.font_size}px; font-weight: bold; padding-left: 5px; color: limegreen;")


    def closeEvent(self, event):
        raw_text = self.data_labels["Press"].text()  # เช่น "1000 hPa" หรือ "1013.25 hPa"
        pressure_val = re.findall(r"[\d.]+", raw_text)[0]  # ดึงเฉพาะเลข เช่น "1013.25"
        raw_text = self.data_labels["Temp"].text()  # เช่น "1000 hPa" หรือ "1013.25 hPa"
        temperature_val = re.findall(r"[\d.]+", raw_text)[0]  # ดึงเฉพาะเลข เช่น "1013.25"
        data_send = {
            "status": "completed",
            "pid": self.data_labels["PID"].text(),
            "temp": temperature_val,
            "pressure": pressure_val,
            "do": self.data_labels["HBOI"].text(),
            "YSI": self.data_labels["YSI"].text(),
        }

        self.closed_data.emit(data_send)
        super().closeEvent(event)

    def edit_pid_dialog(self):
        self.timer_active = False
        self.checkbox_pause.setChecked(True)
        self.checkbox_pause.setEnabled(False)
        self.btn_close.setText(f"Close")
        dialog = NumpadDialog(init_value=self.data_labels["PID"].text(), parent=self)
        if dialog.exec_() == QDialog.Accepted:
            new_value = dialog.get_value()
            if new_value.strip():
                self.data_labels["PID"].setText(new_value.strip())
                # ✅ แสดงข้อความแทนกราฟ ด้วยพื้นหลังสีเทาเข้ม และข้อความตรงกลาง
                self.img_label.clear()
                self.img_label.setStyleSheet("""
                    background-color: #444444;
                    color: white;
                    font-size: 32px;
                    font-weight: bold;
                    border: 1px solid white;
                """)
                self.img_label.setText("Cannot be calculated\nPond ID has been changed")
                self.img_label.setAlignment(Qt.AlignCenter)

    def exp_func(self, x, a, b, c):
        return a * np.exp(-b * x) + c

    # def calculate_do_and_fit(self, do_vals):
    #     is_30sec = self.is_30sec
    #     data_size_at30sec = self.data_size_at30sec
    #     sample_stop_time = self.sample_stop_time

    #     # ✅ ปรับ scale ของ s_vals ตามกรณี
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
    #     return y_fit, x_plot, y_at_30, do_vals, s_vals

    def calculate_do_and_fit(self, do_vals, max_time = 30):
        s_vals = np.arange(len(do_vals))  # x จริงตามเวลาจริง (เช่น 0,1,...)

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
        return y_fit, x_plot, y_at_30, do_vals, s_vals

    def set_do_temp_pressure(self, do_vals, temp_vals, pressure_vals, is_30sec = False, data_size_at30sec = 30, sample_stop_time = 30):
        self.do_vals = do_vals
        self.temp_vals = temp_vals
        self.pressure_vals = pressure_vals

        self.is_30sec = is_30sec
        self.data_size_at30sec = data_size_at30sec
        self.sample_stop_time = sample_stop_time

        # เตรียมข้อมูล x,y
        if len(do_vals) < 5:
            self.img_label2.setText("Insufficient DO data")
            return

        # s_vals = np.arange(len(do_vals))  # สมมุติว่าแต่ละจุดคือ 1 วินาที
        # x_plot = np.linspace(0, len(do_vals)-1, 100)

        # try:
        #     popt, _ = curve_fit(self.exp_func, s_vals, do_vals)
        #     y_fit = self.exp_func(x_plot, *popt)
        # except:
        #     y_fit = np.interp(x_plot, s_vals, do_vals)  # fallback: interpolation

        if len(do_vals) > 30:
            do_vals = do_vals[:30]
        y_fit, x_plot, y_at_30, do_vals, s_vals = self.calculate_do_and_fit(do_vals)

        # วาดภาพบน matplotlib Figure โดยตรง
        fig = Figure(figsize=((self.img_label2.width() + 100) / 100.0, self.img_label2.height() / 100.0), dpi=100, facecolor='white')
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111)
        fig.patch.set_facecolor('white')
        ax.set_facecolor('white')
        ax.tick_params(axis='x', colors='red', labelsize=14)
        ax.tick_params(axis='y', colors='red', labelsize=14)
        ax.spines['bottom'].set_color('red')
        ax.spines['top'].set_color('red')
        ax.spines['left'].set_color('red')
        ax.spines['right'].set_color('red')
        ax.set_xlabel("Seconds", color='red', fontsize=16)
        ax.set_ylabel("% Saturation", color='red', fontsize=16)

        ax.scatter(s_vals, do_vals, color='red', alpha=1)
        ax.plot(x_plot, y_fit, color='red', linewidth=2, alpha=0.7)
        ax.annotate(
            str(round(y_fit[-1])) + '%',
            (x_plot[-1], y_fit[-1]),
            xytext=(x_plot[int(len(x_plot)*0.6)], y_fit[int(len(y_fit)*0.3)]),
            arrowprops={"width": 1, "color": "red", "headwidth": 6},
            color="red", fontsize=16
        )

        # Convert plot to QPixmap
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        img = QImage()
        img.loadFromData(buf.getvalue())
        pixmap = QPixmap.fromImage(img)
        scaled = pixmap.scaled(self.img_label2.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.img_label2.setPixmap(scaled)

    def plot_hourly_do_barchart(self):
        now = datetime.now().replace(minute=0, second=0, microsecond=0)

        # เตรียมช่วงเวลา 24 ชม.ย้อนหลัง + 6 ชม.ล่วงหน้า
        hours_to_pred = 12
        past_hours = [now - timedelta(hours=i) for i in reversed(range(hours_to_pred))]  # 12 ชั่วโมงก่อนหน้า
        future_hours = [now + timedelta(hours=i) for i in range(1, 7)]        # 6 ชั่วโมงล่วงหน้า
        hours = past_hours + future_hours

        do_dict = {h: [] for h in hours}

        # ใช้แค่ไฟล์วันนี้กับเมื่อวาน
        today_str = now.strftime("%Y-%m-%d")
        yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")

        for fname in os.listdir(self.database_truck):
            if not fname.endswith(".csv"):
                continue
            if not (today_str in fname or yesterday_str in fname):
                continue

            try:
                date_part = fname.split("_")[-1].replace(".csv", "")
                file_date = datetime.strptime(date_part, "%Y-%m-%d")
            except:
                continue

            df = pd.read_csv(os.path.join(self.database_truck, fname))
            for _, row in df.iterrows():
                try:
                    if "pond_id" in row and row["pond_id"] != self.pond_id:
                        continue
                    t = datetime.strptime(row["time"], "%H:%M:%S")
                    ts = datetime.combine(file_date.date(), t.time()).replace(minute=0, second=0, microsecond=0)
                    # print(row)
                    if ts in do_dict:
                        # print(f"Current unit: {self.unit}")
                        if self.unit == "percent":
                            try:
                                # print("come to percent")
                                do = row["HBOI DO"]
                                # print(f"DO past: {t}, {do}")
                                do = float(do)
                                do_dict[ts].append(do)
                            except:
                                print("DO value is not float")
                                continue
                        else:
                            try:
                                # print("come to mgl")
                                do = row["HBOI DO"]
                                # print(f"DO past: {t}, {do}")
                                do = float(do)
                                temp = to_celcius(float(row["Temperature"]))
                                p = float(row["Pressure"])
                                do_out = convert_percent_to_mgl(do, temp, p)
                                do_dict[ts].append(do_out)
                            except:
                                print("Something went wrong in DO conversion")
                                continue
                except:
                    continue

        # print(f"do_dict {do_dict}")

        # เติมค่าปัจจุบันลงใน dict
        current_hour = self.measure_datetime.replace(minute=0, second=0, microsecond=0)
        # print(f"current hour: {current_hour}, DO: {self.do_val_current}")
        if current_hour in do_dict:
            do_dict[current_hour].append(self.do_val_current)

        min_do = self.min_do
        good_do = self.good_do

        min_do_percent = convert_mgl_to_percent(min_do, temp_c=25.0)
        good_do_percent = convert_mgl_to_percent(good_do, temp_c=25.0)
        print(f"unit: {self.unit}")
        print(f"DO min-good: {min_do}, {good_do}, {min_do_percent}, {good_do_percent}")
        if self.unit == "percent":
            min_do = min_do_percent
            good_do = good_do_percent

        # คำนวณค่าจากช่วงเวลา 12 ชม.ก่อน now
        y_vals = []
        colors = []
        pred_vals = {}

        for h in past_hours:
            vals = do_dict[h]
            if vals:
                avg = np.mean(vals)
                y_vals.append(avg)
                if avg < min_do:
                    colors.append("#d32f2f") # สีอันตราย
                elif min_do <= avg < good_do:
                    colors.append("#f9a825") # สีเตือน
                else:
                    colors.append("#388e3c") # สีปลอดภัย
            else:
                y_vals.append(0)
                colors.append("#388e3c")

        now = datetime.now()
        pred_vals = {}
        source_for_pred = y_vals[-hours_to_pred:] if len(y_vals) >= hours_to_pred else y_vals.copy()

        for h in future_hours:
            dt = h
            hour = dt.hour
            day_of_year = dt.timetuple().tm_yday

            # วนรอบของเวลา (time-of-day, day-of-year)
            sin_hour = np.sin(2 * np.pi * (hour + 3) / 24)
            cos_hour = np.cos(2 * np.pi * (hour - 15) / 24)
            sin_day = np.sin(2 * np.pi * day_of_year / 365)
            cos_day = np.cos(2 * np.pi * (day_of_year - 182.5) / 365)

            # ฟีเจอร์เวลาอาจไม่ได้ใช้ตรงๆ ใน logic นี้
            # แต่สมมุติเราจะให้ช่วงกลางวัน (เช่น 6:00-18:00) มีน้ำหนักมากขึ้น
            # เราอาจใช้ weighting ได้:
            light_weight = (cos_hour + 1) / 2
            season_weight = (cos_day + 1) / 2

            valid_vals = [v for v in source_for_pred[-12:] if v > 0]

            if len(valid_vals) == 0:
                pred = 0
            else:
                # pred = np.mean(valid_vals) * 0.8 + 0.2 * light_weight * season_weight  # เพิ่มน้ำหนักช่วงกลางวัน
                # pred = np.mean(valid_vals) * (0.6 + 0.4 * season_weight) + 0.4 * light_weight * season_weight
                pred = np.mean(valid_vals) * 0.6 + np.mean(valid_vals) * (0.0 + 0.4 * light_weight * season_weight)


            pred_vals[h] = pred
            y_vals.append(pred)
            source_for_pred.append(pred)
            if pred < min_do:
                colors.append("#ef9a9a") # สีอันตราย
            elif min_do <= pred < good_do:
                colors.append("#ffe082") # สีเตือน
            else:
                colors.append("#a5d6a7") # สีปลอดภัย
            


        x_labels = [h.strftime("%H") + ("P" if h > now else "") for h in hours]

        # วาดกราฟ
        fig = Figure(figsize=((self.img_label.width()+100) / 100.0, (self.img_label.height() - 20) / 100.0), dpi=100)
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111)
        fig.patch.set_facecolor('white')
        ax.set_facecolor('white')
        ax.bar(x_labels, y_vals, color=colors)
        ax.set_xlabel("Hour", fontsize=12)
        ax.set_ylabel("HBOI DO", fontsize=12)
        ax.set_title("Hourly HBOI DO (with 6-hr Prediction)", fontsize=14)
        ax.tick_params(axis='x', labelrotation=45)

        # แปลงเป็น QPixmap และแสดงใน QLabel
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        qimg = QImage()
        qimg.loadFromData(buf.getvalue())
        pix = QPixmap.fromImage(qimg)
        # self.img_label.setPixmap(pix.scaled(self.img_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.img_label.setPixmap(pix)  # ปล่อยให้ label scroll หรือ clip ไปเลย



