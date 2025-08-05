from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout
from PyQt5.QtCore import Qt

class ShutdownDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirm Exit Action")
        self.setModal(True)
        self.setFixedSize(1200, 400)

        self.setStyleSheet("""
            QDialog {
                background-color: #2c2c2c;
                font-size: 40px;
            }
            QLabel {
                color: white;            
                font-weight: bold;
                font-size: 48px;
            }
            QLineEdit {
                padding: 8px;
                font-size: 48px;
                background-color: #444;
                color: white;
                border: 1px solid #888;
                border-radius: 4px;
            }
            QPushButton {
                padding: 10px 20px;
                font-size: 48px;
                color: black;
                background-color: #dcdcdc; 
                border: 1px solid #aaa;
                border-radius: 6px;
                min-width: 250px; 
                min-height: 100px;
            }
            QPushButton:hover {
                background-color: #e6e6e6;
            }
        """)

        layout = QVBoxLayout()

        self.label = QLabel("Choose an action:")
        layout.addWidget(self.label)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Enter password to close program")
        layout.addWidget(self.password_input)

        btn_layout = QHBoxLayout()

        self.btn_close = QPushButton("Close Program")
        self.btn_shutdown = QPushButton("Shutdown")
        self.btn_restart = QPushButton("Restart")
        self.btn_cancel = QPushButton("Cancel")

        btn_layout.addWidget(self.btn_close)
        btn_layout.addWidget(self.btn_shutdown)
        btn_layout.addWidget(self.btn_restart)
        btn_layout.addWidget(self.btn_cancel)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

        self.btn_shutdown.setVisible(False)

        self.result = None

        self.btn_close.clicked.connect(self.try_close)
        self.btn_shutdown.clicked.connect(self.shutdown)
        self.btn_restart.clicked.connect(self.restart)
        self.btn_cancel.clicked.connect(self.reject)

    def try_close(self):
        #TODO UNCOMMENT WHEN DEPLOYED
        if self.password_input.text() == "test":
            self.result = "test"
            self.accept()
        else:
            self.result = "close"
            self.accept()
        # elif self.password_input.text() == "98765":
        #     self.result = "close"
        #     self.accept()
        # else:
        #     self.label.setText("❌ Incorrect password. Try again or press Cancel.")
        #     self.password_input.clear()

    def shutdown(self):
        self.result = "shutdown"
        self.accept()

    def restart(self):
        self.result = "restart"
        self.accept()
