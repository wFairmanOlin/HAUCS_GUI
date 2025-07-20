from PyQt5.QtWidgets import (
    QDialog, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QWidget, QGridLayout
)
from PyQt5.QtCore import Qt
from bigspin_widget import BigSpinBox  # สมมุติว่าคุณมีไฟล์นี้แยกไว้แล้ว

class SettingDialog(QDialog):
    def __init__(self, min_do, good_do, autoclose_sec, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Setting")
        self.setStyleSheet("background-color: #666666; color: white;")
        self.setModal(True)

        self.min_do_box = BigSpinBox(min_do, min_val=0.5, max_val=15, step=0.1, digits=1)
        self.good_do_box = BigSpinBox(good_do, min_val=0.5, max_val=15, step=0.1, digits=1)
        self.auto_close_box = BigSpinBox(autoclose_sec, min_val=5, max_val=100, step=1, digits=0)

        font_style = "font-size: 32px;"
        label1 = QLabel("Minimum Safe DO (mg/l)")
        label1.setStyleSheet(font_style)
        label2 = QLabel("Optimal DO for Growth (mg/l)")
        label2.setStyleSheet(font_style)
        label3 = QLabel("Time to show results before auto-close (sec)")
        label3.setStyleSheet(font_style)

        # ===== Grid Layout สำหรับ Labels + Spinboxes =====
        grid = QGridLayout()
        grid.setHorizontalSpacing(80)
        grid.setVerticalSpacing(25)

        # แถว 0: Label บรรทัดแรก
        grid.addWidget(label1, 0, 0, alignment=Qt.AlignLeft)
        grid.addWidget(label2, 0, 1, alignment=Qt.AlignLeft)

        # แถว 1: Spinbox DO
        grid.addWidget(self.min_do_box, 1, 0, alignment=Qt.AlignLeft)
        grid.addWidget(self.good_do_box, 1, 1, alignment=Qt.AlignLeft)

        # แถว 2: Label auto-close (เต็มบรรทัด)
        grid.addWidget(label3, 2, 0, 1, 2, alignment=Qt.AlignLeft)

        # แถว 3: Spinbox auto-close
        grid.addWidget(self.auto_close_box, 3, 0, 1, 2, alignment=Qt.AlignLeft)

        # ปุ่มล่าง
        self.engineer_btn = QPushButton("Engineer")
        self.engineer_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 2px solid white;
                border-radius: 8px;
                font-size: 28px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #888888;
            }
        """)
        self.engineer_btn.setVisible(False)

        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        for btn in (ok_btn, cancel_btn):
            btn.setFixedSize(150, 60)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #aaaaaa;
                    font-size: 28px;
                    border-radius: 10px;
                }
                QPushButton:hover {
                    background-color: #bbbbbb;
                }
            """)

        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

        bottom_buttons = QHBoxLayout()
        bottom_buttons.addWidget(self.engineer_btn)
        bottom_buttons.addStretch()
        bottom_buttons.addWidget(ok_btn)
        bottom_buttons.addWidget(cancel_btn)

        # Layout หลัก
        layout = QVBoxLayout()
        layout.addLayout(grid)
        layout.addSpacing(30)
        layout.addLayout(bottom_buttons)

        self.setLayout(layout)
        self.adjustSize()
        self.move_to_center()

    def move_to_center(self):
        screen = self.screen().geometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2
        )

    def get_values(self):
        return {
            "min_do": self.min_do_box.get_value(),
            "good_do": self.good_do_box.get_value(),
            "autoclose_sec": self.auto_close_box.get_value()
        }
