from PyQt5.QtGui import QPainter, QColor, QRadialGradient, QBrush, QPen
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QWidget, QLabel, QHBoxLayout
from PyQt5.QtCore import QSize


class LEDIndicatorWidget(QWidget):
    def __init__(self, parent=None, status="disconnected"):
        super().__init__(parent)
        self.status = status  # "disconnected", "connected_not_ready", "connected_ready"
        self.setFixedSize(50, 50)  # ขนาดกลมเท่าปุ่ม X

    def set_status(self, status):
        self.status = status
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # สีตามสถานะ
        if self.status == "disconnected":
            color = QColor(255, 0, 0)  # แดง
        elif self.status == "connected_not_ready":
            color = QColor(255, 255, 0)  # เหลือง
        elif self.status == "connected_ready":
            color = QColor(50, 255, 50)  # เขียว lime
        else:
            color = QColor(128, 128, 128)  # สีเทากลางกรณีไม่รู้

        # สร้าง gradient มีมิติ
        gradient = QRadialGradient(self.width() / 2, self.height() / 2, self.width() / 2)
        gradient.setColorAt(0, QColor(255, 255, 255, 200))  # จุดกลาง
        gradient.setColorAt(0.3, color.lighter(150))  # ขอบใน
        gradient.setColorAt(1, color.darker(180))  # ขอบนอก

        # วาดวงกลม
        brush = QBrush(gradient)
        painter.setBrush(brush)
        pen = QPen(Qt.black)
        pen.setWidth(2)
        painter.setPen(pen)
        diameter = min(self.width(), self.height()) - 4
        painter.drawEllipse(2, 2, diameter, diameter)

    def sizeHint(self):
        return QSize(50, 50)


class LEDStatusWidget(QWidget):
    def __init__(self, parent=None, status="disconnected", font_size=24):
        super().__init__(parent)
        self.font_size = font_size
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.led = LEDIndicatorWidget(status=status)
        self.label = QLabel()
        self.label.setStyleSheet(f"font-size: {self.font_size}px; padding-left: 6px; color: white; font-weight: bold;")


        layout.addWidget(self.led)
        layout.addWidget(self.label)
        self.setLayout(layout)

        self.set_status(status)

    def set_status(self, status):
        self.led.set_status(status)

        if status == "disconnected":
            self.label.setText("Disconnected")
        elif status == "connected_not_ready":
            self.label.setText("Connected (Not Ready)")
        elif status == "connected_ready":
            self.label.setText("Ready")
        else:
            self.label.setText("Unknown")
        self.label.adjustSize()

    def sizeHint(self):
        return QSize(140, 40)  # ปรับตาม text
