from flask import Flask, render_template, jsonify, request
import flask
# from flask_apscheduler import APScheduler
from datetime import datetime, timedelta, timezone
import os, smtplib, json
import numpy as np
import pytz
import random
import time
# from adafruit_ble import BLERadio
# from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
# from adafruit_ble.services.nordic import UARTService


sensor_file = "data/sensor.json"

app = Flask(__name__)

@app.route('/')
def home():
#    with open('static/json/farm_features.json', 'r') as file:
#        data = file.read()
    return render_template('home.html')

'''
Data Source: call this from javascript to get fresh data
'''
@app.route('/sdata', methods=['GET'])
def get_ble():
    with open(sensor_file) as file:
        sdata = json.load(file)
        
    return jsonify(sdata)

@app.route('/idata', methods=['GET'])
def send_img():
    return flask.send_file('test.png')
    # flask.send_from_directory('/', 'test.png')


if __name__ == "__main__":
    # scheduler = APScheduler()
    # scheduler.add_job(func=update_overview, trigger='interval', id='job', seconds=60)
    # scheduler.start()
    app.run(debug=True)

