import adafruit_bno055
import logging
import board
import time

#init logger
logger = logging.getLogger(__name__)

class Compass:
    def __init__(self, i2c, calibration):
        self.initialized = False
        self.calibration = calibration
        self.i2c = i2c
        self.init_bno055()
        if self.initialized:
            self._calibrate()
    
    def init_bno055(self):
        try:
            self.bno055 = adafruit_bno055.BNO055_I2C(self.i2c)
            self.initialized = True
        except Exception as error:
            logger.error(f'cannot initialize bno055: {error}')
            self.initialized = False
    
    def _calibrate(self):
        calibration_keys = ['bno055_magnetometer', 'bno055_gyroscope', 'bno055_accelerometer']
        if all([key in self.calibration for key in calibration_keys]):
            self.bno055.offsets_magnetometer = tuple(self.calibration['bno055_magnetometer'])
            self.bno055.offsets_gyroscope = tuple(self.calibration['bno055_gyroscope'])
            self.bno055.offsets_accelerometer = tuple(self.calibration['bno055_accelerometer'])
    
    def get_calibration(self):
        return {'bno055_magnetometer': list(self.bno055.offsets_magnetometer),
                'bno055_gyroscope': list(self.bno055.offsets_gyroscope),
                'bno055_accelerometer': list(self.bno055.offsets_accelerometer),
                'bno055_gps_offset': self.calibration.get('bno055_gps_offset', 0)}
    
    def update(self, timeout=0.1):
        counter = 0
        heading = None
        start = time.monotonic()
        while heading != None:
            if (time.monotonic() - start > timeout):
                self.raw_heading = None
                logger.debug('euler reading is empty')
                break
            heading = self.bno055.euler[0]
            time.sleep(0.01)
            counter += 1
        print(f"counter {counter}")
        self.raw_heading = heading
        
        self.offset_heading = heading + self.calibration.get('bno055_gps_offset', 0)
        
    def check_and_calibrate_heading(self, speed_kmh, gps_hdg, alpha=0.01):
        # assume driving over 8 yields 
        if speed_kmh > 8 and self.raw_heading != None:
            new_offset = gps_hdg - self.raw_heading
            old_offset = self.calibration.get('bno055_gps_offset', 0)
            offset = alpha * new_offset + (1 - alpha) * old_offset
            self.calibration['bno055_gps_offset'] = offset
            logger.info(f"updating compass offset, gps {gps_hdg:.2f} compass {self.raw_heading:.2f} old {old_offset:.2f} new {offset:.2f}")
        




if __name__ == "__main__":
    i2c = board.I2C()
    compass = Compass(i2c, {})
    while True:
        start = time.monotonic()
        compass.update()
        print(f"{time.monotonic() - start:.5f} hdg: {compass.raw_heading}")
        time.sleep(1)