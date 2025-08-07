import adafruit_bno055
import logging
import board

#init logger
logger = logging.getLogger(__name__)

class Compass:

    initialized = False

    def __init__(self, i2c, calibration):
        self.i2c = i2c
        self.init_bno055()
    
    def init_bno055(self):
        try:
            self.bno055 = adafruit_bno055.BNO055_I2C(self.i2c)
            self.initialized = True
        except Exception as error:
            logger.error(f'cannot initialize bno055: {error}')
            self.initialized = False
    
    def calibrate(self, calibration):
        self.bno055.offsets_magnetometer = calibration['bno055_magnetometer']

        {sensor.offsets_magnetometer}")
print(f"  Offsets_Gyroscope:     {sensor.offsets_gyroscope}")
print(f"  Offsets_Accelerometer: {sensor.offsets_accelerometer

if __name__ == "__main__":
    i2c = board.I2C()
    sensor = adafruit_bno055.BNO055_I2C(i2c)
    while True:
        print(f"Accelerometer (m/s^2): {sensor.acceleration}")
        print(f"Magnetometer (microteslas): {sensor.magnetic}")
        print(f"Gyroscope (rad/sec): {sensor.gyro}")
        print(f"Euler angle: {sensor.euler}")
        print(f"Quaternion: {sensor.quaternion}")
        print(f"Linear acceleration (m/s^2): {sensor.linear_acceleration}")
        print(f"Gravity (m/s^2): {sensor.gravity}")
        print(f"  Offsets_Magnetometer:  {sensor.offsets_magnetometer}")
        print(f"  Offsets_Gyroscope:     {sensor.offsets_gyroscope}")
        print(f"  Offsets_Accelerometer: {sensor.offsets_accelerometer}")
        print()

        time.sleep(1)