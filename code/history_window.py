from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QLabel, QPushButton, QHBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
import os, csv, re
from datetime import datetime, timedelta
from converter import convert_percent_to_mgl, to_celcius

class HistoryLogWindow(QDialog):
    unit = "percent"
    min_do = 4
    good_do = 5

    def __init__(self, unit, foldername, min_do, good_do, parent=None):
        super().__init__(parent)
        self.setWindowTitle("History Log")
        self.setWindowState(Qt.WindowMaximized)

        self.unit = unit
        self.min_do = min_do
        self.good_do = good_do

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Date", "Time", "Pond ID", "HBOI DO", "YSI DO","Temperature", "Pressure"])
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet("""
            QTableWidget {
                font-size: 32px;
            }
            QHeaderView::section {
                font-size: 32px;
                color: black;
                background-color: #dddddd;
            }
        """)

        layout = QVBoxLayout()
        layout.addWidget(self.table)

        close_button = QPushButton("Close")
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #bbbbbb;
                color: black;
                font-size: 32px;
                border-radius: 10px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #777777;
            }
        """)
        close_button.setFixedSize(180, 60)
        close_button.clicked.connect(self.close)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

        self.load_data(foldername)
        self.table.resizeColumnsToContents()
        for col in range(self.table.columnCount()):
            current_width = self.table.columnWidth(col)
            self.table.setColumnWidth(col, current_width + 30)
        self.table.verticalHeader().setDefaultSectionSize(60)

    def get_target_files(self, foldername):
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        target_dates = {today.isoformat(), yesterday.isoformat()}
        filenames = []

        pattern = re.compile(r".+_(\d{4}-\d{2}-\d{2})\.csv$")

        if not os.path.exists(foldername):
            os.makedirs(foldername)

        for fname in os.listdir(foldername):
            match = pattern.match(fname)
            if match:
                date_str = match.group(1)
                if date_str in target_dates:
                    filenames.append(os.path.join(foldername, fname))
        return filenames

    def is_number(self, val):
        try:
            float(val)
            return True
        except:
            return False

    def load_data(self, foldername):
        rows = []

        for fpath in self.get_target_files(foldername):
            basename = os.path.basename(fpath)
            date_str = basename.split("_")[-1].split(".")[0]
            with open(fpath, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    if row.get("time") and row.get("HBOI DO") and row.get("YSI DO"):
                        time_str = row["time"]
                        pond_id = row["Pond ID"]
                        hboi = row["HBOI DO"]
                        ysi = row["YSI DO"]
                        temp_f = float(row["Temperature"])
                        temp = to_celcius(temp_f)
                        press = float(row["Pressure"])

                        if self.is_number(hboi):
                            hboi_mgl = convert_percent_to_mgl(float(hboi), temp, press)
                            hboi_mgl = round(hboi_mgl, 2)
                        else:
                            hboi_mgl = None

                        if self.is_number(ysi):
                            ysi_mgl = convert_percent_to_mgl(float(ysi), temp, press)
                            ysi_mgl = round(ysi_mgl, 2)
                        else:
                            ysi_mgl = None

                        if self.unit == "mgl":
                            hboi_display = hboi_mgl
                            ysi_display = ysi_mgl
                        else:
                            hboi_display = round(float(hboi), 2) if self.is_number(hboi) else hboi
                            ysi_display = round(float(ysi), 2) if self.is_number(ysi) else ysi

                        rows.append((date_str, time_str, pond_id, hboi_display, ysi_display, hboi_mgl, ysi_mgl, temp_f, press))

        rows.sort(key=lambda x: (x[0], x[1]), reverse=True)
        self.table.setRowCount(len(rows))

        for r, (date, time, pond_id, do1, do2, mgl1, mgl2, temp, press) in enumerate(rows):
            row_color = QColor("#444444") if r % 2 == 0 else QColor("#222222")
            for c, val in enumerate([date, time, pond_id, do1, do2, temp, press]):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignCenter)
                item.setBackground(row_color)

                # สีเฉพาะ HBOI DO (col=3) และ YSI DO (col=4)
                if c == 3 and self.is_number(mgl1):
                    if mgl1 < self.min_do:
                        item.setForeground(QColor("red"))
                    elif self.min_do <= mgl1 < self.good_do:
                        item.setForeground(QColor("orange"))
                    else:
                        item.setForeground(QColor("limegreen"))
                elif c == 4 and self.is_number(mgl2):
                    if mgl2 < self.min_do:
                        item.setForeground(QColor("red"))
                    elif self.min_do <= mgl2 < self.good_do:
                        item.setForeground(QColor("orange"))
                    else:
                        item.setForeground(QColor("limegreen"))

                self.table.setItem(r, c, item)
