from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtGui import QPainter, QColor, QFont, QPen, QBrush
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPolygonF, QPainterPath
from PyQt5.QtCore import QPointF
import sys

class BatteryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.percent = 0
        self.charging = False
        self.setFixedSize(115, 50)

    def set_battery_status(self, percent, charging=False):
        self.percent = max(0, min(100, percent))
        self.charging = charging
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        color_pen = QColor(150,150,150)

        if self.percent > 50:
            color = QColor("lime")
        elif self.percent > 30:
            color = QColor("orange")
        else:
            color = QColor("red")

        body_rect = self.rect().adjusted(5, 5, -35, -5)
        painter.setPen(QPen(color_pen, 2))
        painter.drawRect(body_rect)

        head_rect = body_rect.adjusted(body_rect.width(), body_rect.height()//3, 6, -body_rect.height()//3)
        painter.setBrush(color_pen)
        painter.drawRect(head_rect)

        fill_width = int((body_rect.width()-2) * self.percent / 100)
        if fill_width < 10:
            fill_width = 10
        fill_rect = body_rect.adjusted(2, 2, -body_rect.width()+fill_width, -2)
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawRect(fill_rect)

        if self.charging:
            center_x = body_rect.center().x() + 60
            center_y = body_rect.center().y()

            lightning_points = QPolygonF([
                QPointF(center_x + 1, center_y - 20),
                QPointF(center_x - 10, center_y + 3),
                QPointF(center_x + 0, center_y + 3),
                QPointF(center_x - 1, center_y + 20),
                QPointF(center_x + 10, center_y - 3),
                QPointF(center_x + 0, center_y - 3),
            ])

            path = QPainterPath()
            path.moveTo(lightning_points[0])
            for pt in lightning_points[1:]:
                path.lineTo(pt)
            path.closeSubpath()

            painter.setBrush(QBrush(color_pen))
            painter.drawPath(path)

        painter.setPen(color_pen)
        font = QFont("Arial", 35)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(body_rect, Qt.AlignCenter, f"{self.percent}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BatteryWidget()
    window.show()
    window.charging = True
    window.set_battery_status(int(sys.argv[1]), True)
    sys.exit(app.exec_())