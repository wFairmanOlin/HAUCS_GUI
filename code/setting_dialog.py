from PyQt5.QtWidgets import (
    QDialog, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QWidget, QGridLayout, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QCursor
from custom_widgets.bigspin_widget import BigSpinBox
import sys

class SettingDialog(QWidget):
    setting_complete = pyqtSignal(dict, bool)
    def __init__(self, settings):
        self.save = False # flag to save settings on self.close
        super().__init__()
        self.setWindowTitle("Setting")
        self.setStyleSheet("background-color: black; color: white;")
        # self.setFocusPolicy(Qt.ClickFocus)

        self.min_do = BigSpinBox(settings['min_do'], min_val=0.5, max_val=15, step=0.5, sig_digits=1)
        self.good_do = BigSpinBox(settings['good_do'], min_val=0.5, max_val=15, step=0.5, sig_digits=1)
        self.auto_close = BigSpinBox(settings['autoclose_sec'], min_val=5, max_val=100, step=1, sig_digits=0)
        self.p_threshold = BigSpinBox(settings['depth_threshold'], min_val=1, max_val=50, step=0.5, sig_digits=1)

        font_style = "font-size: 32px;"
        label1 = QLabel("low DO level (mg/l)")
        label1.setStyleSheet(font_style)
        label2 = QLabel("good DO level (mg/l)")
        label2.setStyleSheet(font_style)
        label3 = QLabel("auto-close results (sec)")
        label3.setStyleSheet(font_style)
        label4 = QLabel("sample threshold (in)")
        label4.setStyleSheet(font_style)

        grid = QGridLayout()
        # grid.setContentsMargins(10,0,0,0)
        grid.addWidget(label1, 0, 0, alignment=Qt.AlignLeft)
        grid.addWidget(label2, 0, 1, alignment=Qt.AlignLeft)
        grid.addWidget(self.min_do, 1, 0, alignment=Qt.AlignLeft)
        grid.addWidget(self.good_do, 1, 1, alignment=Qt.AlignLeft)
        grid.addWidget(label3, 2, 0, alignment=Qt.AlignLeft)
        grid.addWidget(label4, 2, 1, alignment=Qt.AlignLeft)
        grid.addWidget(self.auto_close, 3, 0, alignment=Qt.AlignLeft)
        grid.addWidget(self.p_threshold, 3, 1, alignment=Qt.AlignLeft)

        ok_btn = QPushButton("save")
        cancel_btn = QPushButton("cancel")
        for btn in (ok_btn, cancel_btn):
            btn.setFixedSize(150, 60)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #aaaaaa;
                    font-size: 28px;
                    border-radius: 10px;
                    color: black;
                }
            """)

        ok_btn.clicked.connect(self.on_save)
        cancel_btn.clicked.connect(self.close)

        bottom_buttons = QHBoxLayout()
        bottom_buttons.addWidget(ok_btn)
        bottom_buttons.addStretch()
        bottom_buttons.addWidget(cancel_btn)

        layout = QVBoxLayout()
        layout.addLayout(grid)
        layout.addSpacing(30)
        layout.addLayout(bottom_buttons)

        self.setLayout(layout)
        self.setCursor(QCursor(Qt.BlankCursor))
        self.showFullScreen()

    def on_save(self):
        self.save = True
        self.close()


    def closeEvent(self, event):
        '''
        Return dictionary with values from display and success flag.
        '''
        self.setting_complete.emit({'min_do':self.min_do.get_value(),
                                    'good_do':self.good_do.get_value(),
                                    'autoclose_sec':self.auto_close.get_value(),
                                    'depth_threshold':self.p_threshold.get_value(),
                                    }, self.save)
        super().closeEvent(event)

    # def focusOutEvent(self, event):
    #     self.close()

if __name__ == "__main__":
    settings = {'min_do':0, 'good_do':1, 'autoclose_sec':3, 'depth_threshold':4}
    app = QApplication(sys.argv)
    window = SettingDialog(settings)
    sys.exit(app.exec_())