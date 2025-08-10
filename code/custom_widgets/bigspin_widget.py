from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import  QPixmap, QPainter, QPolygon, QColor, QIcon

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

        self.up_btn = QPushButton()
        self.down_btn = QPushButton()

        up_pix = self.make_arrow_icon(direction="up", size=70)
        down_pix = self.make_arrow_icon(direction="down", size=70)

        self.up_btn.setIcon(QIcon(up_pix))
        self.up_btn.setIconSize(up_pix.size())
        self.down_btn.setIcon(QIcon(down_pix))
        self.down_btn.setIconSize(down_pix.size())

        self.up_btn.setFixedSize(60, 60)
        self.up_btn.setStyleSheet("""
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

        self.down_btn.setFixedSize(60, 60)
        self.down_btn.setStyleSheet("""
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

    def make_arrow_icon(self, direction="up", size=40):
        """Return a QPixmap containing an arrow pointing up or down."""
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)

        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor('black'))
        p.setPen(Qt.NoPen)

        if direction == "up":
            points = [
                QPoint(size // 2, size // 5),          # top
                QPoint(size - size // 5, size - size // 5),  # bottom right
                QPoint(size // 5, size - size // 5)    # bottom left
            ]
        elif direction == "down":
            points = [
                QPoint(size // 5, size // 5),          # top left
                QPoint(size - size // 5, size // 5),   # top right
                QPoint(size // 2, size - size // 5)    # bottom
            ]
        else:
            raise ValueError("direction must be 'up' or 'down'")

        p.drawPolygon(QPolygon(points))
        p.end()
        return pix

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
