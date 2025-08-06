from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QCheckBox, QGridLayout, QSizePolicy, QDialog
)
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QInputDialog
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import numpy as np
import io
from converter import *
import logging
import sys
from enum import Enum

zero_msg = """Turn the main knob to ZERO. Adjust the smaller ZERO knob until the gauge aligns with 0 mg/l. Press ZERO button, wait for the value to reach steady-state, press ZERO button again.""" 

max_msg = """Turn the main knob to FULL SCALE. Adjust the smaller FULL SCALE knob until the gauge aligns with 15 mg/l. Press FULL SCALE button, wait for the value to reach steady-state, press FULL SCALE again."""

btn_style = """
            QPushButton {
                background-color: #bbbbbb;
                color: black;
                font-size: 32px;
                border-radius: 10px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #777777;
            }
        """
#init logger
logger = logging.getLogger(__name__)

# Global Parameters
alpha = 0.1

class State(Enum):
    normal = 0
    zero = 1
    full_scale = 2 

class YsiCalibrationWindow(QWidget):
    ysi_calibration_complete = pyqtSignal(dict)
    image_path=None

 
    def __init__(self, ysi_raw_data=None):
        super().__init__()
        if ysi_raw_data:
            ysi_raw_data.connect(self.on_raw_data)
        self.state = State.normal
        self.setWindowTitle("YSI Calibration Routine")
        self.setup_ui()
        self.showFullScreen()

    def setup_ui(self):
        screen = self.screen().size()
        w = screen.width()
        h = screen.height()
        self.font = int(h * 0.03)
        self.large_font = int(h * 0.08)

        self.setStyleSheet("background-color: black; color: white;")

        layout_main = QVBoxLayout()
        
        # title layout
        top_layout = QHBoxLayout()
        title = QLabel('YSI CALIBRATION')
        title.setStyleSheet(f"font-size: {self.large_font}px;")
        title.setFixedHeight(int(self.large_font * 1.2))
        top_layout.addStretch()
        top_layout.addWidget(title)
        top_layout.addStretch()
        layout_main.addLayout(top_layout)

        # main info grid
        # descriptions
        zero_txt = QLabel(zero_msg)
        max_txt  = QLabel(max_msg)
        zero_txt.setStyleSheet(f"font-size: {self.font}px;")
        max_txt.setStyleSheet(f"font-size: {self.font}px;") 
        zero_txt.setWordWrap(True)
        max_txt.setWordWrap(True)

        # calibration values
        self.zero_val = QLabel("0")
        self.max_val  = QLabel("0")
        self.zero_val.setStyleSheet(f"font-size: {self.large_font}px;")
        self.max_val.setStyleSheet(f"font-size: {self.large_font}px;") 

        # calibration buttons
        zero_btn = QPushButton("ZERO")
        zero_btn.setStyleSheet(btn_style)
        zero_btn.setFixedSize(360, 60)
        zero_btn.clicked.connect(self.on_zero_btn_press)
        max_btn = QPushButton("FULL SCALE")
        max_btn.setStyleSheet(btn_style)
        max_btn.setFixedSize(360, 60)
        max_btn.clicked.connect(self.on_max_btn_press)

        info_grid = QGridLayout()
        info_grid.addWidget(zero_txt, 0, 0, Qt.AlignCenter)
        info_grid.addWidget(max_txt,  0, 1, Qt.AlignCenter)
        info_grid.addWidget(self.zero_val, 1, 0, Qt.AlignCenter)
        info_grid.addWidget(self.max_val,  1, 1, Qt.AlignCenter)
        info_grid.addWidget(zero_btn, 2, 0, Qt.AlignCenter)
        info_grid.addWidget(max_btn,  2, 1, Qt.AlignCenter)        
        layout_main.addLayout(info_grid)
        
        # close button
        close_button = QPushButton("close")
        close_button.setStyleSheet(btn_style)
        close_button.setFixedSize(180, 60)
        close_button.clicked.connect(self.close)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        layout_main.addLayout(button_layout)
        
        self.setLayout(layout_main)

    def on_raw_data(self, val, *args):
        print(f"raw data received: {val}")
        old_data = 0
        if self.state == State.zero:
            if self.zero_val.text().isnumeric():
                old_data = float(self.zero_val.text())
        elif self.state == State.full_scale:
            if self.max_val.text().isnumeric():
                old_data = float(self.max_val.text())
        
        data = alpha * val + (1 - alpha) * old_data

        if self.state == State.zero:
            self.zero_val.setText(f"{data:.1f}")
        elif self.state == State.full_scale:
            self.max_val.setText(f"{data:.1f}")

    
    def on_zero_btn_press(self):
        if self.state == State.zero:
            self.state = State.normal
        else:
            self.state = State.zero
    
    def on_max_btn_press(self):
        if self.state == State.full_scale:
            self.state = State.normal
        else:
            self.state = State.full_scale

    def closeEvent(self, event):
        '''
        Return dictionary with values from display and success flag.
        '''
        success = True
        try:
            zero = float(self.zero_val.text())
            full_scale = float(self.zero_val.text())
        except:
            zero = 0
            full_scale = 0
            success = False
        
        if zero >= full_scale:
            success = False

        self.ysi_calibration_complete.emit({'zero':zero, 'full_scale':full_scale, 'success':success})
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YsiCalibrationWindow()
    sys.exit(app.exec_())