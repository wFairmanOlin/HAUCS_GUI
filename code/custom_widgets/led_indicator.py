from PyQt5.QtGui import QPainter, QColor, QRadialGradient, QBrush, QPen
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QWidget, QLabel, QHBoxLayout, QApplication
from PyQt5.QtCore import QSize
import sys

class LEDIndicatorWidget(QWidget):
    def __init__(self, parent=None, status="disconnected"):
        super().__init__(parent)
        self.status = status
        self.setFixedSize(50, 50)

    def set_status(self, status):
        self.status = status
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.status == "disconnected":
            color = QColor(255, 0, 0)
        elif self.status == "connected_not_ready":
            color = QColor(255, 255, 0)
        elif self.status == "connected_ready":
            color = QColor(50, 255, 50)
        else:
            color = QColor(128, 128, 128)

        gradient = QRadialGradient(self.width() / 2, self.height() / 2, self.width() / 2)
        # gradient.setColorAt(0, QColor(255, 255, 255, 200))
        gradient.setColorAt(0.3, color.lighter(150))
        gradient.setColorAt(1, color.darker(180))

        brush = QBrush(gradient)
        painter.setBrush(brush)
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
        # self.label = QLabel()
        # self.label.setStyleSheet(f"font-size: {self.font_size}px; padding-left: 6px; color: white; font-weight: bold;")
        # self.label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)


        layout.addWidget(self.led)
        # layout.addWidget(self.label)
        self.setLayout(layout)

        self.set_status(status)

    def set_status(self, status):
        self.led.set_status(status)

        # if status == "disconnected":
        #     self.label.setText("Disconnected")
        # elif status == "connected_not_ready":
        #     self.label.setText("Connected (Not Ready)")
        # elif status == "connected_ready":
        #     self.label.setText("Ready")
        # else:
        #     self.label.setText("Unknown")
        # self.label.adjustSize()

    def sizeHint(self):
        return QSize(50, 50)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LEDStatusWidget()
    window.show()
    window.set_status('connected_ready')
    sys.exit(app.exec_())