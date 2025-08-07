from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QPushButton, QVBoxLayout
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QIcon
from PyQt5.QtCore import Qt, QPointF, QSize
import math

def draw_square_teeth_gear_icon(size=50, teeth=8, tooth_width=10, tooth_height=8) -> QPixmap:
    pixmap = QPixmap(size + 10, size + 10)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    center = QPointF(size / 2 + 5, size / 2 + 5)
    outer_radius = (size - tooth_height) // 2
    hole_radius = outer_radius * 0.4

    painter.translate(center)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(Qt.white))

    # === Draw gear body ===
    painter.drawEllipse(QPointF(0, 0), outer_radius, outer_radius)

    # === Draw square teeth ===
    angle_step = 360 // teeth
    for i in range(teeth):
        angle = math.radians(i * angle_step)
        # Tooth center point
        x = (outer_radius - 1 + tooth_width // 2) * math.cos(angle)
        y = (outer_radius - 1 + tooth_height // 2) * math.sin(angle)

        painter.save()
        painter.translate(x, y)
        painter.rotate(i * angle_step)
        painter.drawRect(-tooth_height // 2, -tooth_width // 2, tooth_height, tooth_width)
        painter.restore()

    # === Draw center hole ===
    painter.setBrush(Qt.black)
    painter.drawEllipse(QPointF(0, 0), hole_radius, hole_radius)
    painter.end()
    return pixmap

# === Example usage ===
if __name__ == "__main__":
    app = QApplication([])

    window = QWidget()
    layout = QVBoxLayout(window)
    icon_size = 50
    btn = QPushButton()
    btn.setIcon(QIcon(draw_square_teeth_gear_icon(size=icon_size)))
    btn.setIconSize(QSize(icon_size, icon_size))
    btn.setFixedSize(icon_size + 10, icon_size + 10)  # Add padding
    btn.setStyleSheet("background-color: black; border: none;")  # Optional styling
    layout.addWidget(btn)

    window.setStyleSheet("background-color: #222;")  # To show the white gear clearly
    window.show()

    app.exec_()
