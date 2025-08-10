# GLOBAL SETTINGS
MAX_HISTORY = 100
MIN_SPEED = 8
FILE_PATH = "bno055/offset_data.csv"

import adafruit_bno055
import logging
import board
import time
import csv
import os

# init logger
logger = logging.getLogger(__name__)


class Compass:
    def __init__(self, i2c, calibration):
        self.initialized = False
        self.calibration = calibration
        self.offset_history = []
        self.offset = 0
        self.offset_heading = None
        self.heading = None
        self.i2c = i2c
        self.init_bno055()
        if self.initialized:
            self._calibrate()
        self._load_data()

    def init_bno055(self):
        try:
            self.bno055 = adafruit_bno055.BNO055_I2C(self.i2c)
            self.initialized = True
        except Exception as error:
            logger.error("cannot initialize bno055: %s", error)
            self.initialized = False

    def _calibrate(self):
        calibration_keys = [
            "bno055_magnetometer",
            "bno055_gyroscope",
            "bno055_accelerometer",
        ]
        if all([key in self.calibration for key in calibration_keys]):
            try:
                self.bno055.offssets_magnetometer = tuple(
                    self.calibration["bno055_magnetometer"]
                )
                self.bno055.offsets_gyroscope = tuple(
                    self.calibration["bno055_gyroscope"]
                )
                self.bno055.offsets_accelerometer = tuple(
                    self.calibration["bno055_accelerometer"]
                )
            except Exception as error:
                logger.error("failed to calibrated bno055: %s", error)

    def get_calibration(self):
        try:
            return {
                "bno055_magnetometer": list(self.bno055.offsets_magnetometer),
                "bno055_gyroscope": list(self.bno055.offsets_gyroscope),
                "bno055_accelerometer": list(self.bno055.offsets_accelerometer),
            }
        except Exception as error:
            logger.error("failed to retrieve bno055 calibration: %s", error)
            return {}

    def update(self, timeout=0.1):
        counter = 0
        heading = None
        if not self.initialized:
            self.init_bno055()
        else:
            try:
                start = time.monotonic()
                while heading == None:
                    if time.monotonic() - start > timeout:
                        self.raw_heading = None
                        self.offset_heading = None
                        self.initialized = False
                        logger.debug("euler reading is empty")
                        break
                    heading = self.bno055.euler[0]
                    time.sleep(0.01)
                    counter += 1
                print(f"counter {counter}")
                self.raw_heading = heading
            except Exception as error:
                logger.error("failed to update bno055: %s", error)
                self.initialized = False

        if heading != None:
            self.offset_heading = heading + self.offset

    def check_and_calibrate_heading(self, speed_kmh, gps_hdg):
        # assume driving over 8 yields
        # compass heading + offset = gps headnig
        # offset = gps heading - compass heading
        try:
            # stop if compass not connected
            self.update()
            if not self.initialized:
                return
            if speed_kmh > 8 and self.raw_heading != None:
                # calculate new offset
                new_offset = (
                    gps_hdg + 180 - self.raw_heading
                ) % 360 - 180  # mininum angle +/-
                # append data
                self.offset_history = [
                    time.time(),
                    speed_kmh,
                    gps_hdg,
                    self.raw_heading,
                    new_offset,
                ]
                if len(self.offset_history) > MAX_HISTORY:
                    self.offset_history.pop(0)
                # save offset data
                self._save_data()
                # calculate new offset
                self.offset = sum([i[-1] for i in self.offset_history]) / len(
                    self.offset_history
                )
                logger.info(
                    f"updating compass offset, gps {gps_hdg:.2f} compass {self.raw_heading:.2f} new {self.offset:.2f}"
                )
        except Exception as e:
            logger.warning("failed to calculate compass offset %s", e)

    def _save_data(self):
        try:
            # create file path if not present
            if not os.path.exists(FILE_PATH):
                logger.info("creating bno055 data file")
                os.makedirs("/".join(FILE_PATH.split("/")[:-1]), exist_ok=True)
            # save offset data
            with open(FILE_PATH, "w", newline="") as csvfile:
                writer = csv.writer(csvfile, delimiter=",")
                writer.writerow(["time", "gps_spd", "gps_hdg", "imu_hdg", "offset"])
                writer.writerows(self.offset_history)
        except Exception as e:
            logger.warning("failed to write %s", e)

    def _load_data(self):
        self.offset_history = []
        try:
            # load offset data (EVERY VARIABLE IS A FLOAT)
            if os.path.exists(FILE_PATH):
                with open(FILE_PATH, newline="") as csvfile:
                    reader = csv.reader(csvfile, delimiter=",")
                    for row in reader:
                        self.offset_history.append([float(i) for i in row])
            # calculate new offset
            if len(self.offset_history):
                self.offset = sum([i[-1] for i in self.offset_history]) / len(
                    self.offset_history
                )
        except Exception as e:
            logger.warning("failed to read/set offset %s", e)


if __name__ == "__main__":
    i2c = board.I2C()
    compass = Compass(i2c, {})
    while True:
        start = time.monotonic()
        compass.update()
        print(f"{time.monotonic() - start:.5f} hdg: {compass.raw_heading}")
        time.sleep(1)
