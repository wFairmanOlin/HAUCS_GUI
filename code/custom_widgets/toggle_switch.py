from PyQt5.QtWidgets import QWidget, QVBoxLayout, QApplication
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPainter, QColor, QBrush
from PyQt5.QtCore import pyqtSignal

class ToggleSwitch(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, parent=None, checked=False):
        super().__init__(parent)
        self.setFixedSize(QSize(80, 40))
        self._checked = checked
        self._thumb_pos = 30 if checked else 2
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Track
        track_color = QColor("#2ecc71") if self._checked else QColor("#cccccc")
        painter.setBrush(QBrush(track_color))
        painter.drawRoundedRect(0, 0, 73, 40, 20, 20)

        # Thumb
        painter.setBrush(QBrush(QColor("white")))
        thumb_x = 35 if self._checked else 2
        painter.drawEllipse(thumb_x, 2, 36, 36)

    def mousePressEvent(self, event):
        self._checked = not self._checked
        self.update()
        self.toggled.emit(self._checked)

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        self._checked = checked
        self.update()

if __name__ == "__main__":
    app = QApplication([])
    window = QWidget()
    layout = QVBoxLayout(window)

    btn = ToggleSwitch(checked=False)

    layout.addWidget(btn)
    window.show()

    app.exec_()