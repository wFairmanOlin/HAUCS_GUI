import board, adafruit_gps
import pandas as pd
import time
import numpy as np

class GPS_sensor:
    latitude = 0
    longitude = 0
    pond_id = 0
    fails = 0
    num_satellites = 0
    default_pond_id = 'unk25'

    logger_status = "normal"
    logger_string = ""

    def update_logger(self, logger_status, logger_string):
        self.logger_status = logger_status
        self.logger_string = logger_string

    def __init__(self, timeout=1):
        i2c = board.I2C()
        self.gps = adafruit_gps.GPS_GtopI2C(i2c, timeout=2)
        self.gps.send_command(b'PMTK314,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0')
        #TODO: Make update rate variable
        self.gps.send_command(b"PMTK220,8000")
        # clear stale data
        self.update_GPS(timeout=5)
        self.df = pd.read_csv('sampling_points.csv')
        self.pond_ids = self.df.pop('pond')
        self.pond_gps = self.df.to_numpy()

    def update_GPS(self, timeout=2):
        try:
            start_time = time.time()
            while time.time() - start_time < timeout:
                while self.gps.update():
                    time.sleep(0.01)
                self.fails = 0
            if self.gps.satellites is not None:
                self.numsat = self.gps.satellites
            return True
        except:
            self.fails += 1
            print('GPS update failed')
            self.update_logger("warning", 'GPS update routine failed')
            return False

    def get_GPS_pond(self):
        self.update_GPS()
        self.get_pond_id()

        return self.pond_id, self.gps.latitude, self.gps.longitude

    def get_pond_id(self, lat= None, lng= None):
        if lat is None:
            lat = self.latitude
            lng = self.longitude

        self.pond_id = self.default_pond_id

        try:
            point = np.array([float(lng), float(lat)])
        except:
            print("malformed latitude and longitude")
            self.pond_id = self.default_pond_id
            return self.pond_id
        
        point_y = np.tile(point, (self.pond_gps.shape[0], 1))
        #calculate euclidean distances
        distances = np.linalg.norm(self.pond_gps - point_y, axis=1)
        #calculate minimum distance in meters
        print(distances)
        min_dist = distances.min() * 111_000
        #determine if min distance is acceptable
        if min_dist < 1_000: #TODO: DISTANCES
            #find pond associated with minimum distance
            self.pond_id = str(self.pond_ids[np.argmin(distances)])
        else:
            self.pond_id = self.default_pond_id
        
        return self.pond_id