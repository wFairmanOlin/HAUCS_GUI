from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDoubleValidator, QIntValidator

class BigSpinBox(QWidget):
    def __init__(self, val=50, min_val=0, max_val=100, step=1, sig_digits=0):
        super().__init__()
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self.sig_digits = sig_digits
        self.value = val

        # ---- Layout ----
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(30)

        # ---- Line Edit ----
        self.line_edit = QLabel(str(self.value))
        self.line_edit.setFixedHeight(55)
        self.line_edit.setFixedWidth(160)
        self.line_edit.setAlignment(Qt.AlignCenter)
        self.line_edit.setStyleSheet("""
            QLabel {
                font-size: 32px;
                border: 2px solid black;
                background-color: white;
                color: black;
            }
        """)

        # ---- Buttons ----
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)

        self.up_btn = QPushButton(f'\N{BLACK UP-POINTING TRIANGLE}')
        self.down_btn = QPushButton(f'\N{BLACK DOWN-POINTING TRIANGLE}')

        for btn in [self.up_btn, self.down_btn]:
            btn.setFixedSize(60, 60)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #cccccc;
                    font-size: 35px;
                    border-radius: 6px;
                    color: black;
                    text-align: center;
                }
                QPushButton:pressed {
                    background-color: #55cc55;
                    color: black;
                }
            """)

        self.up_btn.clicked.connect(self.increment)
        self.down_btn.clicked.connect(self.decrement)

        btn_layout.addWidget(self.up_btn)
        btn_layout.addWidget(self.down_btn)

        layout.addWidget(self.line_edit)
        layout.addLayout(btn_layout)

        self.setLayout(layout)
        # self.showFullScreen()

    def increment(self):
        new_val = round(self.value + self.step, self.sig_digits)
        if new_val <= self.max_val:
            self.set_value(new_val)

    def decrement(self):
        new_val = round(self.value - self.step, self.sig_digits)
        if new_val >= self.min_val:
            self.set_value(new_val)

    def set_value(self, val):
        self.value = round(val, self.sig_digits)
        text = str(int(self.value)) if self.sig_digits == 0 else f"{self.value:.{self.sig_digits}f}"
        self.line_edit.setText(text)

    def get_value(self):
        return self.value
