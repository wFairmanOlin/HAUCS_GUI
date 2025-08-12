from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QCheckBox, QGridLayout, QSizePolicy, QDialog
)

from PyQt5.QtGui import QImage, QPixmap, QCursor
from PyQt5.QtCore import Qt, QTimer, QSize
import os
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QInputDialog
from custom_widgets.numpad_dialog import NumpadDialog
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import numpy as np
import io
import pandas as pd
from datetime import datetime, timedelta
from converter import *
import logging

#init logger
logger = logging.getLogger(__name__)


class ResultWindow(QWidget):
    closed_data = pyqtSignal(dict)
    image_path=None
    measure_datetime = None
    pond_id = "unk"
 
    def __init__(self, data, unit, min_do, good_do, auto_close_sec=10):
        super().__init__()
        self.setAttribute(Qt.WA_DeleteOnClose)
        # self.setFocusPolicy(Qt.ClickFocus)
        self.remaining_time = auto_close_sec
        self.timer_active = True

        self.unit = unit
        self.min_do = min_do
        self.good_do = good_do
        self.data = data

        # Set DO Colors
        self.hboi_color = 'limegreen'
        if self.data['do_mgl'] < self.min_do:
             self.hboi_color = 'red'
        elif self.min_do <= self.data['do_mgl'] < self.good_do:
             self.hboi_color = 'yellow'

        self.ysi_color = 'limegreen'
        if self.data['do_mgl'] < self.min_do:
             self.ysi_color = 'red'
        elif self.min_do <= self.data['do_mgl'] < self.good_do:
             self.ysi_color = 'yellow'

        self.setWindowTitle("Result Summary")
        self.setup_ui(self.image_path)
        self.setup_timer()
        self.setCursor(QCursor(Qt.BlankCursor))
        self.showFullScreen()


    def setup_ui(self, image_path):
        screen = self.screen().size()
        w = screen.width()
        h = screen.height()
        font_size = int(h * 0.05)
        self.font_size = font_size
        self.large_font = int(h * 0.08)
        btn_font_size = int(h * 0.03)
        self.unit_font = int(h * 0.05)

        # self.setGeometry(
        #     # int((screen.width() - w) / 2),
        #     # int((screen.height() - h) / 3),
        #     0, 0,
        #     w, h
        # )
        self.setStyleSheet("background-color: black; color: white;")

        layout_main = QVBoxLayout()

        # === Top Layout ===
        layout_top = QHBoxLayout()

        # === Left Layout (40%) ===
        layout_left = QVBoxLayout()
        info_grid = QGridLayout()

        pid_label   = QLabel('Pond')
        hboi_label  = QLabel('BLE DO')
        ysi_label   = QLabel('YSI DO')
        dur_label   = QLabel('Length')
        temp_label  = QLabel('WT')
        date_label  = QLabel('Time')
        depth_label = QLabel('Depth')

        dur_unit   = QLabel('s')
        temp_unit  = QLabel(f'\N{DEGREE FAHRENHEIT}')
        depth_unit = QLabel('in')

        self.pid_val = QLabel(self.data['pid']) #modifiable
        temp_val     = QLabel(f"{to_fahrenheit(self.data['water_temp']):.1f}")
        depth_val    = QLabel(f"{self.data['sample_depth']:.1f}")
        dur_val      = QLabel(f"{self.data['sample_duration']}")

        # Handle DO Data
        if self.unit == "percent":
            hboi_val  = QLabel(f"{100 * self.data['do']:.1f}")
            ysi_val   = QLabel(f"{100 * self.data['ysi_do']:.1f}")
            hboi_unit = QLabel('%')
            ysi_unit  = QLabel('%')
        else:
            hboi_val  = QLabel(f"{self.data['do_mgl']:.1f}")
            ysi_val   = QLabel(f"{self.data['ysi_do_mgl']:.1f}")
            hboi_unit = QLabel('mg/l')
            ysi_unit  = QLabel('mg/l')
        
        # Handle Date
        now = datetime.now()
        formatted_time = now.strftime("%I:%M %p")
        date_val = QLabel(formatted_time)
        
        pid_label.setStyleSheet(f"font-size: {self.large_font}px; padding-left:10px;") 
        hboi_label.setStyleSheet(f"font-size: {self.large_font}px; padding-left:10px;") 
        ysi_label.setStyleSheet(f"font-size: {self.large_font}px; padding-left:10px;")
        dur_label.setStyleSheet(f"font-size: {self.large_font}px; padding-left:10px;")  
        temp_label.setStyleSheet(f"font-size: {self.large_font}px; padding-left:10px;") 
        date_label.setStyleSheet(f"font-size: {self.large_font}px; padding-left:10px;")  
        depth_label.setStyleSheet(f"font-size: {self.large_font}px; padding-left:10px;")

        self.pid_val.setStyleSheet(f"font-size: {self.large_font}px; font-weight: bold;") 
        hboi_val.setStyleSheet(f"font-size: {self.large_font}px; font-weight: bold; color: {self.hboi_color};") 
        ysi_val.setStyleSheet(f"font-size: {self.large_font}px; font-weight: bold; color: {self.ysi_color};")
        dur_val.setStyleSheet(f"font-size: {self.large_font}px; font-weight: bold;")  
        temp_val.setStyleSheet(f"font-size: {self.large_font}px; font-weight: bold;") 
        date_val.setStyleSheet(f"font-size: {self.large_font}px; font-weight: bold;")  
        depth_val.setStyleSheet(f"font-size: {self.large_font}px; font-weight: bold;")

        hboi_unit.setStyleSheet(f"font-size: {self.unit_font}px; font-weight: bold;")
        ysi_unit.setStyleSheet(f"font-size: {self.unit_font}px; font-weight: bold;")
        dur_unit.setStyleSheet(f"font-size: {self.unit_font}px; font-weight: bold;")
        temp_unit.setStyleSheet(f"font-size: {self.unit_font}px; font-weight: bold;")
        depth_unit.setStyleSheet(f"font-size: {self.unit_font}px; font-weight: bold;")

        # ADD PID LAYOUT
        pid_layout = QHBoxLayout()
        pid_layout.setSpacing(int(font_size * 0.8))
        btn_edit = QPushButton("Edit")
        btn_edit.setStyleSheet(f"font-size: {int(self.large_font*0.6)}px; padding: 0px; color: black;")
        btn_edit.setFixedHeight(int(self.large_font * 1.2))
        btn_edit.setFixedWidth(int(self.large_font * 2.4))
        btn_edit.clicked.connect(self.edit_pid_dialog)
        pid_layout.addWidget(self.pid_val)
        pid_layout.addWidget(btn_edit)
        pid_widget = QWidget()
        pid_widget.setLayout(pid_layout)

        # Setup INFO GRID
        info_grid.addWidget(pid_label, 0, 0, Qt.AlignLeft)
        info_grid.addWidget(pid_widget, 0, 1, 1, 2, Qt.AlignRight)

        info_grid.addWidget(hboi_label,  1, 0, Qt.AlignLeft)
        info_grid.addWidget(hboi_val,    1, 1, Qt.AlignRight)
        info_grid.addWidget(hboi_unit,   1, 2, Qt.AlignLeft)
        info_grid.addWidget(ysi_label,   2, 0, Qt.AlignLeft)
        info_grid.addWidget(ysi_val,     2, 1, Qt.AlignRight)
        info_grid.addWidget(ysi_unit,    2, 2, Qt.AlignLeft)
        info_grid.addWidget(dur_label,   3, 0, Qt.AlignLeft)
        info_grid.addWidget(dur_val,     3, 1, Qt.AlignRight)
        info_grid.addWidget(dur_unit,    3, 2, Qt.AlignLeft)
        info_grid.addWidget(temp_label,  4, 0, Qt.AlignLeft)
        info_grid.addWidget(temp_val,    4, 1, Qt.AlignRight)
        info_grid.addWidget(temp_unit,   4, 2, Qt.AlignLeft)
        info_grid.addWidget(depth_label, 5, 0, Qt.AlignLeft)
        info_grid.addWidget(depth_val,   5, 1, Qt.AlignRight)
        info_grid.addWidget(depth_unit,  5, 2, Qt.AlignLeft)
        info_grid.addWidget(date_label,  6, 0, Qt.AlignLeft)
        info_grid.addWidget(date_val,    6, 1, Qt.AlignRight)

        layout_left.addStretch()
        layout_left.addLayout(info_grid)
        layout_left.addStretch()
        layout_top.addLayout(layout_left, stretch=5)

        # === Right Layout (60%) ===
        layout_right = QVBoxLayout()
        self.img_label = QLabel()
        img_width = int(w * 0.5)   # 0.9 * 60%
        img_height = int(h * 0.2)   # 60%

        self.img_label.setFixedSize(img_width, img_height)
        self.img_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setStyleSheet("background-color: navy blue; color: black; border: 1px solid black;")
        # TODO: TEMPORARY PLACEHOLDER FOR PREDICTION GRAPH
        self.img_label.clear()
        self.img_label.setStyleSheet("""
            background-color: black;
            color: white;
            font-size: 32px;
            font-weight: bold;
        """)
        self.img_label.setText("")
        self.img_label.setAlignment(Qt.AlignCenter)
        # END TODO: END OF TEMPORARY PLACEHOLDER FOR PREDICTION GRAPH

        layout_right.addStretch()
        layout_right.addWidget(self.img_label, alignment=Qt.AlignCenter)
        layout_right.addStretch()

        # image 2
        self.img_label2 = QLabel()
        self.img_label2.setFixedSize(img_width, int(h * 0.6))
        self.img_label2.setAlignment(Qt.AlignCenter)
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

    def closeEvent(self, event):
        self.data['pid'] = self.pid_val.text()
        self.closed_data.emit(self.data)
        super().closeEvent(event)

    def edit_pid_dialog(self):
        self.timer_active = False
        self.checkbox_pause.setChecked(True)
        self.checkbox_pause.setEnabled(False)
        self.btn_close.setText(f"Close")
        dialog = NumpadDialog(init_value=self.pid_val.text(), parent=self)
        if dialog.exec_() == QDialog.Accepted:
            new_value = dialog.get_value()
            if new_value.strip():
                self.pid_val.setText(new_value.strip())
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
        try:
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

            # IDEAL RECORD TIME FOR DATA
            record_time = 30 #TODO: this should be in setting.setting
            x_plot = np.linspace(0, sample_stop_time, 5 * sample_stop_time)

            # generate time array for hboi
            time_hboi = np.arange(len(self.data['do_vals'])) / self.data['sample_hz']
            time_hboi = time_hboi[time_hboi <= sample_stop_time]

            # generate time array for ysi sensor
            time_ysi = np.arange(len(self.data['do_vals'])) / self.data['sample_hz']
            time_ysi = time_ysi[time_ysi <= sample_stop_time]
            
            # fit for HBOI SENSOR
            p, f = calculate_do_fit(do_arr, record_time, self.data['sample_hz'])
            y_fit = generate_do(x_plot, p, f)
            y_fit = [scale * i for i in y_fit]
            y_scatter = do_arr[:len(time_hboi)]
            y_scatter = [scale * i for i in y_scatter]
            
            # fit for YSI SENSOR
            p, f = calculate_do_fit(ysi_do_arr, record_time, self.data['sample_hz'])
            y_fit_ysi = generate_do(x_plot, p, f)
            y_fit_ysi = [scale * i for i in y_fit_ysi]
            y_scatter_ysi = ysi_do_arr[:len(time_ysi)]
            y_scatter_ysi = [scale * i for i in y_scatter_ysi]

            fig = Figure(figsize=(((self.img_label2.width())/ 100.0), self.img_label2.height() / 100.0), dpi=100)
            ax = fig.add_subplot(111)
            accent_color = 'white'
            ax.tick_params(axis='x', colors=accent_color, labelsize=14)
            ax.tick_params(axis='y', colors=accent_color, labelsize=14)
            ax.spines['bottom'].set_color(accent_color)
            ax.spines['top'].set_color(accent_color)
            ax.spines['left'].set_color(accent_color)
            ax.spines['right'].set_color(accent_color)
            ax.set_xlabel("Seconds", color=accent_color, fontsize=16)
            ax.set_ylabel("% Saturation" if self.unit == 'percent' else "mg/l", color=accent_color, fontsize=16)
            
            ax.scatter(time_hboi, y_scatter, s=150, color='tab:cyan', alpha=0.7, label='BLE')
            ax.scatter(time_ysi, y_scatter_ysi, s=150, color='tab:orange', alpha=0.7, label='YSI')
            ax.plot(x_plot, y_fit, color='tab:cyan', linewidth=5, alpha=1)
            ax.plot(x_plot, y_fit_ysi, color='tab:orange', linewidth=5, alpha=1)
            ax.legend(fontsize=16, labelcolor=accent_color, framealpha=0.2)
            
            # Convert plot to QPixmap
            buf = io.BytesIO()
            fig.savefig(buf, format='png', bbox_inches='tight', transparent=True)
            buf.seek(0)
            img = QImage()
            img.loadFromData(buf.getvalue())
            pixmap = QPixmap.fromImage(img)
            scaled = pixmap.scaled(self.img_label2.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.img_label2.setPixmap(scaled)
        except Exception as e:
            logger.error("curve-fitting plot failed %s \n %s", e, self.data)
            self.img_label2.setText("ERROR IN PLOT GENERATION")
            self.img_label2.setAlignment(Qt.AlignCenter)

    def focusOutEvent(self, event):
        self.close()

