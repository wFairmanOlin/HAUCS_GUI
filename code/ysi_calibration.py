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
import custom_widgets.gear

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
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 80);
            }
            QPushButton:checked {
                background-color: limegreen;
            }
        """
#init logger
logger = logging.getLogger(__name__)

# Global Parameters
alpha = 0.1

class YsiCalibrationWindow(QWidget):
    ysi_calibration_complete = pyqtSignal(dict, bool)
    
    def __init__(self, ysi_raw_data=None):
        super().__init__()
        self.save = False #sets whether or not calibration is saved on close()
        # self.setFocusPolicy(Qt.ClickFocus)
        if ysi_raw_data:
            ysi_raw_data.connect(self.on_raw_data)
        self.setWindowTitle("YSI Calibration Routine")
        self.setup_ui()
        self.showFullScreen()

    def setup_ui(self):
        screen = self.screen().size()
        w = screen.width()
        h = screen.height()
        self.font = int(h * 0.05)
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
        zero_txt.setStyleSheet(f"font-size: {self.font}px; padding-left: 5px; padding-right: 5px;")
        max_txt.setStyleSheet(f"font-size: {self.font}px; padding-left: 5px; padding-right: 5px;") 
        zero_txt.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        max_txt.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        zero_txt.setWordWrap(True)
        max_txt.setWordWrap(True)
        

        # calibration values
        self.zero_val = QLabel("0")
        self.max_val  = QLabel("0")
        self.zero_val.setStyleSheet(f"font-size: {self.large_font}px;")
        self.max_val.setStyleSheet(f"font-size: {self.large_font}px;") 

        # calibration buttons
        self.zero_btn = QPushButton("ZERO")
        self.zero_btn.setStyleSheet(btn_style)
        self.zero_btn.setFixedSize(360, 60)
        self.zero_btn.setCheckable(True)
        self.zero_btn.setChecked(False)
        self.zero_btn.clicked.connect(self.on_zero_btn_press)
        self.max_btn = QPushButton("FULL SCALE")
        self.max_btn.setStyleSheet(btn_style)
        self.max_btn.setFixedSize(360, 60)
        self.max_btn.setCheckable(True)
        self.max_btn.setChecked(False)
        self.max_btn.clicked.connect(self.on_max_btn_press)

        info_grid = QGridLayout()
        info_grid.addWidget(zero_txt, 0, 0)
        info_grid.addWidget(max_txt,  0, 1)
        info_grid.addWidget(self.zero_val, 1, 0, Qt.AlignCenter)
        info_grid.addWidget(self.max_val,  1, 1, Qt.AlignCenter)
        info_grid.addWidget(self.zero_btn, 2, 0, Qt.AlignCenter)
        info_grid.addWidget(self.max_btn,  2, 1, Qt.AlignCenter)        
        layout_main.addLayout(info_grid)
        

        
        # save button
        save_button = QPushButton("save")
        save_button.setStyleSheet(btn_style)
        save_button.setFixedSize(180, 60)
        save_button.clicked.connect(self.on_save_press)
        
        # close button
        close_button = QPushButton("close")
        close_button.setStyleSheet(btn_style)
        close_button.setFixedSize(180, 60)
        close_button.clicked.connect(self.close)

        button_layout = QHBoxLayout()
        button_layout.addWidget(save_button)
        button_layout.addStretch()
        button_layout.addWidget(close_button)

        layout_main.addLayout(button_layout)
        
        self.setLayout(layout_main)

    def on_raw_data(self, val, *args):
        zero_btn = self.zero_btn.isChecked()
        max_btn = self.max_btn.isChecked()
        old_data = 0
        if zero_btn:
            if self.zero_val.text().isnumeric():
                old_data = int(self.zero_val.text())
        elif max_btn:
            if self.max_val.text().isnumeric():
                old_data = int(self.max_val.text())
        data = alpha * val + (1 - alpha) * old_data
        if zero_btn:
            self.zero_val.setText(f"{data:.0f}")
        elif max_btn:
            self.max_val.setText(f"{data:.0f}")

    def on_save_press(self):
        self.save = True
        self.close()

    def on_zero_btn_press(self):
        if self.max_btn.isChecked():
            self.max_btn.setChecked(False)
    
    def on_max_btn_press(self):
        if self.zero_btn.isChecked():
            self.zero_btn.setChecked(False)

    def closeEvent(self, event):
        '''
        Return dictionary with values from display and success flag.
        '''
        success = True
        try:
            zero = float(self.zero_val.text())
            full_scale = float(self.max_val.text())
        except:
            zero = 0
            full_scale = 0
            success = False

        success &= (zero < full_scale) # return false if zero is less than full scale
        success &= self.save # return false if save parameter is false

        self.ysi_calibration_complete.emit({'zero':zero, 'full_scale':full_scale}, success)
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()

    # def focusOutEvent(self, event):
    #     self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YsiCalibrationWindow()
    sys.exit(app.exec_())