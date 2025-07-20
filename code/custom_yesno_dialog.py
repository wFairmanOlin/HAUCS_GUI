from PyQt5.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout
from PyQt5.QtCore import Qt

class CustomYesNoDialog(QDialog):
    def __init__(self, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirm Action")
        self.setModal(True)
        self.setStyleSheet("background-color: #444444; color: white;")

        # ----- Label -----
        label = QLabel(message)
        label.setStyleSheet("font-size: 40px;")
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignCenter)

        # ----- Buttons -----
        yes_btn = QPushButton("Yes")
        no_btn = QPushButton("No")
        for btn in (yes_btn, no_btn):
            btn.setFixedSize(240, 100)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #cccccc;
                    color: black;
                    font-size: 36px;
                    border-radius: 10px;
                }
                QPushButton:hover {
                    background-color: #dddddd;
                }
            """)

        yes_btn.clicked.connect(lambda: self.done(QDialog.Accepted))
        no_btn.clicked.connect(lambda: self.done(QDialog.Rejected))

        # ----- Layout -----
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(no_btn)
        button_layout.addSpacing(40)
        button_layout.addWidget(yes_btn)
        button_layout.addStretch()

        layout = QVBoxLayout()
        layout.addSpacing(30)
        layout.addWidget(label)
        layout.addSpacing(30)
        layout.addLayout(button_layout)
        layout.addSpacing(20)

        self.setLayout(layout)
        self.resize(700, 300)
        self.move_to_center()

    def move_to_center(self):
        screen = self.screen().geometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2
        )
