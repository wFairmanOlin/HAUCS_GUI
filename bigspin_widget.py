from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLineEdit
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDoubleValidator, QIntValidator

class BigSpinBox(QWidget):
    def __init__(self, val=50, min_val=0, max_val=100, step=1, digits=0, parent=None):
        super().__init__(parent)
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self.digits = digits
        self.value = val

        # ---- Layout ----
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(30)  # ระยะห่างระหว่าง textbox กับปุ่ม up/down

        # ---- Line Edit ----
        self.line_edit = QLineEdit(str(self.value))
        self.line_edit.setFixedHeight(55)
        self.line_edit.setFixedWidth(160)
        self.line_edit.setAlignment(Qt.AlignCenter)
        self.line_edit.setStyleSheet("""
            QLineEdit {
                font-size: 32px;
                border: 2px solid black;
                background-color: white;
                color: black;
            }
        """)

        if digits == 0:
            self.line_edit.setValidator(QIntValidator(min_val, max_val, self))
        else:
            validator = QDoubleValidator(min_val, max_val, digits, self)
            validator.setNotation(QDoubleValidator.StandardNotation)
            self.line_edit.setValidator(validator)

        self.line_edit.editingFinished.connect(self.on_edit_finished)

        # ---- Buttons ----
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)

        self.up_btn = QPushButton("▲")
        self.down_btn = QPushButton("▼")

        for btn in [self.up_btn, self.down_btn]:
            btn.setFixedSize(45, 45)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #cccccc;
                    font-size: 28px;
                    border-radius: 6px;
                    color: #33ff33
                }
                QPushButton:hover {
                    background-color: #99e699;
                    color: #33ff33
                }
                QPushButton:pressed {
                    background-color: #55cc55;
                    color: #33ff33
                }
            """)

        self.up_btn.clicked.connect(self.increment)
        self.down_btn.clicked.connect(self.decrement)

        btn_layout.addWidget(self.up_btn)
        btn_layout.addWidget(self.down_btn)

        layout.addWidget(self.line_edit)
        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self.setFixedSize(250, 110)  # ควบคุมขนาด widget โดยรวม

    def increment(self):
        new_val = round(self.value + self.step, self.digits)
        if new_val <= self.max_val:
            self.set_value(new_val)

    def decrement(self):
        new_val = round(self.value - self.step, self.digits)
        if new_val >= self.min_val:
            self.set_value(new_val)

    def on_edit_finished(self):
        try:
            val = float(self.line_edit.text())
            if self.digits == 0:
                val = int(val)
            if self.min_val <= val <= self.max_val:
                self.set_value(val)
            else:
                self.set_value(self.value)
        except ValueError:
            self.set_value(self.value)

    def set_value(self, val):
        self.value = round(val, self.digits)
        text = str(int(self.value)) if self.digits == 0 else f"{self.value:.{self.digits}f}"
        self.line_edit.setText(text)

    def get_value(self):
        return self.value
