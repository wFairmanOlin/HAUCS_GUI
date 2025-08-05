import adafruit_gps
import pandas as pd
import time
import numpy as np
import logging
logger = logging.getLogger(__name__)

class GPSSensor:

    # accessed externally
    pond_id = 0
    numsat = 0
    latitude = 0
    longitude = 0
    heading = 0

    # accessed internally
    default_pond_id = 'unk25'

    def __init__(self, i2c, timeout=2):
        self.gps = adafruit_gps.GPS_GtopI2C(i2c, timeout=timeout)
        self.gps.send_command(b'PMTK314,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0')
        #TODO: Make update rate variable
        self.gps.send_command(b"PMTK220,8000")
        # clear stale data
        self.parse_nmea(timeout=5)
        self.df = pd.read_csv('sampling_points.csv')
        self.pond_ids = self.df.pop('pond')
        self.pond_gps = self.df.to_numpy()

    def update(self):
        '''
        This is called externally to update GPS object attributes
        '''
        self.parse_nmea()
        self.get_pond_id()

    def parse_nmea(self, timeout=2):
        try:
            start_time = time.time()
            while time.time() - start_time < timeout:
                while self.gps.update():
                    time.sleep(0.01)
            # update values that are not None
            if self.gps.satellites is not None:
                self.numsat = self.gps.satellites
            if self.gps.latitude:
                self.latitude = self.gps.latitude
            if self.gps.longitude:
                self.longitude = self.gps.longitude
            if self.gps.track_angle_deg:
                self.heading = self.gps.track_angle_deg
        except:
            logger.info('gps update failed')

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