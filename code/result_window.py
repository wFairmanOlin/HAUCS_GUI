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
import pandas as pd
from datetime import datetime, timedelta
from converter import *

class ResultWindow(QWidget):
    closed_data = pyqtSignal(dict)
    image_path=None

    database_truck = "database_truck"
    measure_datetime = None
    pond_id = "unk"
    min_do = 4
    good_do = 5
    unit = "percent"
 
    def __init__(self, data, auto_close_sec=10):
        super().__init__()
        self.auto_close_sec = auto_close_sec
        self.remaining_time = auto_close_sec
        self.timer_active = True

        self.setWindowTitle("Result Summary")
        self.setup_ui(self.image_path)
        self.setup_timer()

        # set values
        self.data = data
        print(f"RESULTS WINDOW DATA\n{data}")
        self.update_value("PID", self.data["pid"])
        self.update_value("PID", "-1")
        self.update_value("Temp", f"{to_fahrenheit(self.data['water_temp']):.2f} °F")
        self.update_value("Press", f"{self.data['sample_depth']:.2f} in")
        
        # HANDLE DO CONVERSIONS
        if self.unit == "percent":
            self.update_value("HBOI", f"{100 * self.data['do']:.2f}")
            self.update_value("YSI", f"{100 * self.data['ysi_do']:.2f}")
        else:
            self.update_value("HBOI", f"{self.data['do_mgl']:.2f}")
            self.update_value("YSI", f"{self.data['ysi_do_mgl']:.2f}")

        self.update_value("SD", f"{self.data['sample_duration']}s")

        now = datetime.now()
        formatted_time = now.strftime("%I:%M %p")
        self.update_value("Date", formatted_time)
        self.show()

    def setup_ui(self, image_path):
        screen = self.screen().size()
        w = int(screen.width() * 0.98)
        h = int(screen.height() * 0.98)
        font_size = int(h * 0.05)
        self.font_size = font_size
        large_font_size = int(h * 0.09)
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
            ("Pond ID", "PID"),
            ("HBOI DO", "HBOI"),
            ("YSI DO", "YSI"),
            ("Duration", "SD"),
            ("Water Temp", "Temp"),
            ("Time", "Date"),
            ("Depth", "Press"),
        ]

        for i, (text, key) in enumerate(labels):
            label = QLabel(text)
            label.setStyleSheet(f"font-size: {large_font_size}px; padding-right: 5px;")

            if key == "PID":
                pid_layout = QHBoxLayout()
                pid_layout.setSpacing(int(font_size * 1.0))
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
                value.setStyleSheet(f"font-size: {large_font_size}px; font-weight: bold; padding-left: 5px;")                
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
        img_width = int(w * 0.5)   # 0.9 * 60%
        img_height = int(h * 0.4)   # 60%

        self.img_label.setFixedSize(img_width, img_height)
        self.img_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setStyleSheet("background-color: navy blue; color: black; border: 1px solid black;")
        # TODO: TEMPORARY PLACEHOLDER FOR PREDICTION GRAPH
        self.img_label.clear()
        self.img_label.setStyleSheet("""
            background-color: #444444;
            color: white;
            font-size: 32px;
            font-weight: bold;
            border: 1px solid white;
        """)
        self.img_label.setText("Pond DO Prediction Here\nIn Development :(")
        self.img_label.setAlignment(Qt.AlignCenter)
        
        # END TODO: END OF TEMPORARY PLACEHOLDER FOR PREDICTION GRAPH

        layout_right.addStretch()
        layout_right.addWidget(self.img_label, alignment=Qt.AlignCenter)
        layout_right.addStretch()

        # image 2
        self.img_label2 = QLabel()
        self.img_label2.setFixedSize(img_width, img_height)
        self.img_label2.setAlignment(Qt.AlignCenter)
        self.img_label2.setStyleSheet("background-color: #c1c1c1; border: 1px solid white;")
        self.img_label2.setText("Engineering Image")
        self.img_label2.setVisible(True) #TODO: was FALSE
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

        if clicked_widget != self.btn_close:
            if self.timer_active:
                self.timer_active = False
                self.checkbox_pause.setChecked(True)
                self.checkbox_pause.setEnabled(False)
                self.btn_close.setText("Close")

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
                if self.data['do_mgl'] < self.min_do:
                    self.data_labels[key].setStyleSheet(f"font-size: {self.large_font_size}px; font-weight: bold; padding-left: 5px; color: red;")
                elif self.min_do <= self.data['do_mgl'] < self.good_do:
                    self.data_labels[key].setStyleSheet(f"font-size: {self.large_font_size}px; font-weight: bold; padding-left: 5px; color: yellow;")
                else:
                    self.data_labels[key].setStyleSheet(f"font-size: {self.large_font_size}px; font-weight: bold; padding-left: 5px; color: limegreen;")

            elif key == "YSI":
                if self.data['ysi_do_mgl'] < self.min_do:
                    self.data_labels[key].setStyleSheet(f"font-size: {self.large_font_size}px; font-weight: bold; padding-left: 5px; color: red;")
                elif self.min_do <= self.data['ysi_do_mgl'] < self.good_do:
                    self.data_labels[key].setStyleSheet(f"font-size: {self.large_font_size}px; font-weight: bold; padding-left: 5px; color: yellow;")
                else:
                    self.data_labels[key].setStyleSheet(f"font-size: {self.large_font_size}px; font-weight: bold; padding-left: 5px; color: limegreen;")


    def closeEvent(self, event):
        self.data['pid'] = self.data_labels['PID'].text()
        self.closed_data.emit(self.data)
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




    def set_do_temp_pressure(self, sample_stop_time=30):

        if len(self.data['do_vals']) < 5:
            self.img_label2.setText("Insufficient DO data")
            return

        if self.unit == "percent":
            do_arr = self.data['do_vals']
            ysi_do_arr = self.data['ysi_do_arr']
            scale = 100
        else:
            do_arr = self.data['do_mgl_arr']
            ysi_do_arr = self.data['ysi_do_mgl_arr']
            scale = 1

        print(do_arr)
        # IDEAL RECORD TIME FOR DATA
        record_time = 30 #TODO: this should be in setting.setting
        x_plot = np.linspace(0, sample_stop_time, 10 * sample_stop_time)

        # generate time array
        time = np.arange(len(self.data['do_vals'])) / self.data['sample_hz']
        time = time[time <= sample_stop_time]

        # fit for HBOI SENSOR
        p, f = calculate_do_fit(do_arr, record_time, self.data['sample_hz'])
        y_fit = generate_do(x_plot, p, f)
        y_fit = [scale * i for i in y_fit]
        y_scatter = do_arr[:len(time)]
        y_scatter = [scale * i for i in y_scatter]
        
        # fit for YSI SENSOR
        p, f = calculate_do_fit(ysi_do_arr, record_time, self.data['sample_hz'])
        y_fit_ysi = generate_do(x_plot, p, f)
        y_fit_ysi = [scale * i for i in y_fit_ysi]
        y_scatter_ysi = ysi_do_arr[:len(time)]
        y_scatter_ysi = [scale * i for i in y_scatter_ysi]

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
        ax.set_ylabel("% Saturation" if self.unit == 'percent' else "mg/l", color='red', fontsize=16)

        ax.scatter(time, y_scatter, color='red', alpha=1)
        ax.plot(x_plot, y_fit, color='red', linewidth=2, alpha=0.7)
        ax.annotate(
            f"{y_fit[-1]:.1f}{'%' if self.unit == 'percent' else 'mg/l'}",
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



