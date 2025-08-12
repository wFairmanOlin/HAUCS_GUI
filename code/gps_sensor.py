import adafruit_gps
import pandas as pd
import time
import numpy as np
import logging
import board
logger = logging.getLogger(__name__)


def degToCompass(num):
    val=int((num/22.5)+.5)
    arr=["N","NNE","NE","ENE","E","ESE", "SE", "SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return arr[(val % 16)]

class GPSSensor:
    # accessed internally
    default_pond_id = 'unk'

    # accessed externally
    pond_id = default_pond_id
    numsat = 0
    latitude = 0
    longitude = 0
    heading = 0
    speed_kmh = 0
    last_valid_signal = time.time()
    valid_signal_timeout = 20 # seconds
    valid_signal = False



    def __init__(self, i2c, timeout=0.1):
        self.gps = adafruit_gps.GPS_GtopI2C(i2c, timeout=timeout)
        self.gps.send_command(b'PMTK314,0,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0')
        #TODO: Make update rate variable
        self.gps.send_command(b"PMTK220,2000")
        self.df = pd.read_csv('sampling_points.csv')
        self.pond_ids = self.df.pop('pond')
        self.pond_gps = self.df.to_numpy()

    def update(self):
        '''
        This is called externally to update GPS object attributes
        '''
        self.parse_nmea()
        if time.time() - self.last_valid_signal > self.valid_signal_timeout:
            self.valid_signal = False
            logger.warning("no gps signal")
            self.reset_gps_data()
        self.get_pond_id()

    def parse_nmea(self, timeout=0.5):
        try:
            start_time = time.time()
            msgs_received = 0
            while self.gps.update():
                if time.time() - start_time > timeout:
                    break
                msgs_received += 1
            # update values that are not None
            if self.gps.satellites:
                self.numsat = self.gps.satellites
            if self.gps.latitude:
                self.latitude = self.gps.latitude
            if self.gps.longitude:
                self.longitude = self.gps.longitude
            if self.gps.track_angle_deg:
                self.heading = self.gps.track_angle_deg
            if self.gps.speed_kmh:
                self.speed_kmh = self.gps.speed_kmh
        except:
            logger.info('gps update failed')
        if msgs_received >= 2: # considered valid if 2/3 messages are beign transmitted
            self.valid_signal = True
            self.last_valid_signal = time.time()
            
    def reset_gps_data(self):
        self.last_valid_signal = time.time()
        self.pond_id = self.default_pond_id
        self.gps.satellites = 0
        self.gps.latitude = 0
        self.gps.longitude = 0
        self.gps.track_angle_deg = 0
        self.gps.speed_kmh = 0
        self.latitude = 0
        self.longitude = 0
        self.heading = 0
        self.speed_kmh = 0
        self.numsat = 0

    def get_pond_id(self, lat= None, lng= None):
        if lat is None:
            lat = self.latitude
            lng = self.longitude

        self.pond_id = self.default_pond_id

        try:
            point = np.array([float(lng), float(lat)])
        except:
            logger.warning('get pond id received malformed coordinates')
            self.pond_id = self.default_pond_id
            return self.pond_id
        
        point_y = np.tile(point, (self.pond_gps.shape[0], 1))
        #calculate euclidean distances
        distances = np.linalg.norm(self.pond_gps - point_y, axis=1)
        #calculate minimum distance in meters
        min_dist = distances.min() * 111_000
        #determine if min distance is acceptable
        if min_dist < 100:
            #find pond associated with minimum distance
            self.pond_id = str(self.pond_ids[np.argmin(distances)])
        else:
            self.pond_id = self.default_pond_id
        
        return self.pond_id
    
if __name__ == "__main__":
    gps = GPSSensor(board.I2C(), timeout=0.1)
    long_delay = 1
    while True:
        if long_delay % 10 == 0:
            time.sleep(30)
        start = time.time()
        gps.update()
        print(f"time to complete: {(time.time() - start):.2f}")
        data = {'lat':gps.latitude,
                'lng':gps.longitude,
                'hdg':gps.heading,
                'pid':gps.pond_id,
                'nsat':gps.numsat,
                'speed_kmh':gps.speed_kmh,
                }
        data2 = {'lat':gps.gps.latitude,
                'lng':gps.gps.longitude,
                'hdg':gps.gps.track_angle_deg,
                'pid':gps.pond_id,
                'nsat':gps.gps.satellites,
                'speed_kmh':gps.gps.speed_kmh,
                }
        print(data)
        print(data2)
        time.sleep(2)