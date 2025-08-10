from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QPushButton, QLineEdit, QHBoxLayout, QApplication
)
from PyQt5.QtCore import Qt

class NumpadDialog(QDialog):
    def __init__(self, title="Enter Pond ID", init_value="", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(title)
        self.setStyleSheet("background-color: #333; color: white; font-size: 24px;")
        self.value = init_value
        self.first_input = True

        # ดึงขนาดหน้าจอ
        screen = QApplication.primaryScreen().size()
        btn_w = screen.width() // 4
        btn_h = screen.height() // 7
        font_size = int(btn_h * 0.6)

        # Input field
        self.input_field = QLineEdit()
        self.input_field.setText(init_value)
        self.input_field.selectAll()
        self.input_field.setReadOnly(True)
        self.input_field.setAlignment(Qt.AlignRight)
        self.input_field.setStyleSheet(f"background-color: white; color: black; font-size: {font_size}px; font-weight: bold;")
        self.input_field.setFixedHeight(btn_h)

        layout_main = QVBoxLayout()
        layout_main.addWidget(self.input_field)

        # === Numpad ===
        grid = QGridLayout()
        buttons = [
            ("1", 0, 0), ("2", 0, 1), ("3", 0, 2),
            ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
            ("7", 2, 0), ("8", 2, 1), ("9", 2, 2),
            ("Clear", 3, 0), ("0", 3, 1), ("Del", 3, 2),
        ]
        for text, row, col in buttons:
            btn = QPushButton(text)
            btn.setFixedSize(btn_w, btn_h)
            btn.setStyleSheet(f"font-size: {font_size}px; background-color: #555; color: black;")
            btn.clicked.connect(lambda _, t=text: self.on_button_click(t))
            grid.addWidget(btn, row, col)
        layout_main.addLayout(grid)

        # === OK / Cancel ===
        layout_ok = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        for b in [btn_ok, btn_cancel]:
            b.setFixedSize(btn_w, btn_h)
            b.setStyleSheet(f"font-size: {font_size}px; background-color: #2a7f62; color: black;")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        layout_ok.addStretch()
        layout_ok.addWidget(btn_ok)
        layout_ok.addWidget(btn_cancel)
        layout_ok.addStretch()
        layout_main.addLayout(layout_ok)

        self.setLayout(layout_main)
        self.resize(int(screen.width() * 0.8), int(screen.height() * 0.8))

    def on_button_click(self, text):
        if text == "Del":
            self.value = self.value[:-1]
        elif text == "Clear":
            self.value = ""
        else:
            if self.first_input:
                self.first_input = False
                self.value = ""
            self.value += text
        self.input_field.setText(self.value)

    def get_value(self):
        return self.value
