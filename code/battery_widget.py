from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QFont, QPen, QBrush
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPolygonF, QPainterPath
from PyQt5.QtCore import QPointF

class BatteryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.percent = 0
        self.charging = False
        self.setFixedSize(80, 40)  # ขนาดแบต

    def set_battery_status(self, percent, charging=False):
        self.percent = max(0, min(100, percent))
        self.charging = charging
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # กำหนดสีตามสถานะแบต
        if self.percent > 50:
            color = QColor("lime")
        elif self.percent > 20:
            color = QColor("orange")
        else:
            color = QColor("red")

        # วาดกรอบแบตเตอรี่
        body_rect = self.rect().adjusted(0, 5, -10, -5)
        painter.setPen(QPen(Qt.black, 2))
        painter.drawRect(body_rect)

        # วาดหัวแบตเล็ก
        head_rect = body_rect.adjusted(body_rect.width(), body_rect.height()//3, 10, -body_rect.height()//3)
        painter.setBrush(Qt.black)
        painter.drawRect(head_rect)

        # วาดด้านหลังแบต
        fill_width = int((body_rect.width()-4))
        fill_rect = body_rect.adjusted(2, 2, -body_rect.width()+fill_width, -2)
        painter.setBrush(Qt.white)
        painter.setPen(Qt.NoPen)
        painter.drawRect(fill_rect)

        # วาดเปอร์เซ็นต์แถบในแบต
        fill_width = int((body_rect.width()-4) * self.percent / 100)
        fill_rect = body_rect.adjusted(2, 2, -body_rect.width()+fill_width, -2)
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawRect(fill_rect)

        # วาดรูปสายฟ้า (ตอนชาร์จ)
        if self.charging:
            # ⚡ สร้างเส้นสายฟ้าแบบ polygon
            center_x = body_rect.center().x()
            center_y = body_rect.center().y()

            lightning_points = QPolygonF([
                QPointF(center_x + 2, center_y - 15),
                QPointF(center_x - 6, center_y + 2),
                QPointF(center_x + 0, center_y + 2),
                QPointF(center_x - 4, center_y + 15),
                QPointF(center_x + 8, center_y - 2),
                QPointF(center_x + 0, center_y - 2),
            ])

            # สร้าง path จาก polygon
            path = QPainterPath()
            path.moveTo(lightning_points[0])
            for pt in lightning_points[1:]:
                path.lineTo(pt)
            path.closeSubpath()

            # วาด fill สีเหลือง
            painter.setBrush(QBrush(QColor("yellow")))
            painter.setPen(QPen(Qt.black, 1))  # ขอบดำบาง
            painter.drawPath(path)

        # วาดตัวเลข % ด้านใน
        painter.setPen(Qt.black)
        font = QFont("Arial", 12)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(body_rect, Qt.AlignCenter, f"{self.percent}")
