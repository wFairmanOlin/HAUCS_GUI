from queue import Queue, Empty
import os
import firebase_admin
from firebase_admin import credentials,db
import concurrent.futures
from PyQt5.QtCore import QThread, pyqtSignal, QObject
import pandas as pd
from datetime import datetime
import numpy as np
import shutil

def convert_numpy(obj):
    if isinstance(obj, np.generic):
        return obj.item()
    elif isinstance(obj, (np.ndarray, list, tuple)):
        return [convert_numpy(o) for o in obj]
    elif isinstance(obj, dict):
        return {k: convert_numpy(v) for k, v in obj.items()}
    else:
        return obj

class FirebaseWorker(QThread):
    logger_data = pyqtSignal(str, str)

    app = None
    cred = None
    fail_counter = 0

    max_fail = 30
    truck_id = "truck1"
    fb_key="/home/haucs/Desktop/HAUCS_GUI/fb_key.json"
    database_folder = "database_truck"
    unsaved_json = "unsaved_json"
    completed_upload = "completed_json"
    key=['sid', 'init_do', 'init_pressure', 'pid', 'do', 'temp', 'pressure', 'batt_v', 'lng', 'lat', 'message_time', 'ysi_do']
    sdatas = []

    def __init__(self):
        super().__init__()
        self._abort = False

    def init_firebase(self):
        try:
            self.logger_data.emit("info", f'use firebase key:{self.fb_key}')
            # print(self.fb_key)
            if os.path.exists(self.fb_key):
                self.cred = credentials.Certificate(self.fb_key)
                self.app = firebase_admin.initialize_app(self.cred, {'databaseURL': 'https://haucs-monitoring-default-rtdb.firebaseio.com'})
            else:
                self.logger_data.emit("warning", 'Firebase initialize failed, no fb_key')
        except Exception as error:
            self.logger_data.emit("warning", f'Firebase initialize failed {str(error)}')

    def restart_firebase(self, in_app):
        self.logger_data.emit('info', 'Attempting to restart Firebase Connection')
        if in_app is not None:
            firebase_admin.delete_app(in_app)
            self.msleep(10000)
        if os.path.exists(self.fb_key) and self.cred is None:
            self.cred = credentials.Certificate(self.fb_key)
            # self.update_logger_text("warning", 'Firebase initialize failed, no fb_key')
        if self.cred is not None:
            new_app = firebase_admin.initialize_app(self.cred,
                                                {'databaseURL': 'https://haucs-monitoring-default-rtdb.firebaseio.com'})
            return new_app
        return None

    def convert_datadict_for_save(self, sdata, key, full_info = False):
        truck_id = sdata[key[0]]
        init_DO = sdata[key[1]]
        init_pressure = sdata[key[2]]
        pond_id = sdata[key[3]]
        avg_do_perc = [float(sdata[key[4]])]
        temp = np.array(sdata[key[5]]).tolist()
        pressure = np.array(sdata[key[6]]).tolist()
        battv = sdata[key[7]]
        lng = sdata[key[8]]
        if (lng is None or lng == "None"):
            lng = -1000
        lat = sdata[key[9]]
        if (lat is None or lat == "None"):
            lat = -1000
        message_time = sdata[key[10]]
        ysi_do = [sdata[key[11]]]

        data = {
            'do': avg_do_perc, 'init_do': init_DO, 'init_pressure': init_pressure,
            'lat': lat, 'lng': lng, 'pid': pond_id, 'pressure': pressure,
            'sid': truck_id, 'temp': temp, 'batt_v': battv, 'type': 'truck', 'ysi_do_mgl': ysi_do
        }
        if full_info:
            data[key[10]] = message_time
        return data, message_time

    def add_sdata(self, sdata, csv_file, row):
        # สร้างชื่อไฟล์
        today_str = datetime.now().strftime("%Y-%m-%d")
        time_str = datetime.now().strftime("%H:%M:%S")
        folder = self.database_folder
        os.makedirs(folder, exist_ok=True)  # สร้างโฟลเดอร์ถ้ายังไม่มี
        file_path = os.path.join(folder, f"{self.truck_id}_{today_str}.csv")

        key=['name', 'init_do', 'init_pressure', 'pid', 'do', 'temp', 'pressure', 'battv', 'lng', 'lat', 'message_time', 'ysi_do_mgl']
        data, message_time = self.convert_datadict_for_save(sdata, key, full_info=True)
        # print(data)
        # self.save_json_firebase_single(data)
        self.save_datadict_txt(data, self.key)
        self.sdatas.append(data)

        # ถ้ามีไฟล์อยู่แล้ว ให้ append
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        else:
            df = pd.DataFrame([row])  # สร้างใหม่พร้อม header

        # บันทึกลงไฟล์
        df.to_csv(file_path, index=False)

    def run(self):
        # self.restore_unsaved_from_json()
        folder = self.unsaved_json
        if not os.path.exists(folder):
            return  # ไม่มีโฟลเดอร์ ไม่ต้องทำอะไร

        files = [f for f in os.listdir(folder) if f.endswith(".txt")]
        for filename in files:
            filepath = os.path.join(folder, filename)
            sdata = self.convert_txt_to_dict(filepath)
            if sdata is not None:
                self.sdatas.append(sdata)

        while not self._abort:
            self.update_firebase_when_internet()
            if self._abort:
                break
            self.msleep(2000)

    def abort(self):
        self.logger_data.emit("info", "Stop Firebase worker, normal process")
        self._abort = True

    def restore_unsaved_from_json(self):
        folder = self.unsaved_json
        if not os.path.exists(folder):
            return  # ไม่มีโฟลเดอร์ ไม่ต้องทำอะไร

        files = [f for f in os.listdir(folder) if f.endswith(".json")]
        self.sdatas = []
        for filename in files:
            filepath = os.path.join(folder, filename)
            try:
                with open(filepath, 'r') as infile:
                    sdata = json.load(infile)
                    self.sdatas.append(sdata)
            except Exception as e:
                print(f"Error reading {filename}: {e}")
                self.logger_data.emit("warning", f"Error reading {filename}: {e}")

    def delete_json_unsaved(self, sdata):
        safe_time = sdata['message_time'].replace(":", "-")
        json_file = os.path.join(self.unsaved_json, safe_time + ".json")
        if os.path.exists(json_file):
            try:
                os.remove(json_file)
                self.logger_data.emit("info", f"removed local JSON file: {json_file}")
            except Exception as e:
                self.logger_data.emit("error", f"failed to delete {json_file}: {e}")

    def save_json_firebase_single(self, sdata):
        safe_time = sdata['message_time'].replace(":", "-")
        sensor_file = os.path.join(self.unsaved_json, safe_time + ".json")

        print(sensor_file)
        try:
            os.makedirs(self.unsaved_json, exist_ok=True)
            with open(sensor_file, 'w') as outfile:
                print("here")
                print(sdata)
                json.dump(sdata, outfile, default=str)
                print("done writing")
        except Exception as e:
            self.logger_data.emit("error", f"Failed to write JSON: {sensor_file} — {e}")

    def save_json_firebase_completed(self, sdata):
        safe_time = sdata['message_time'].replace(":", "-")
        sensor_file = os.path.join(self.unsaved_json, safe_time + ".json")
        try:
            with open(sensor_file, 'w') as outfile:
                json.dump(sdata, outfile, default=str)
        except Exception as e:
            self.logger_data.emit("error", f"Failed to write JSON: {sensor_file} — {e}")

    def move_json_to_completed(self, sdata):
        safe_time = sdata['message_time'].replace(":", "-")
        src_path = os.path.join(self.unsaved_json, safe_time + ".json")
        dst_path = os.path.join(self.completed_upload, safe_time + ".json")

        try:
            os.makedirs(self.completed_upload, exist_ok=True)
            shutil.move(src_path, dst_path)
            self.logger_data.emit("info", f"Moved JSON file to completed: {dst_path}")
        except FileNotFoundError:
            self.logger_data.emit("warning", f"Source file not found, saving new JSON: {dst_path}")
            try:
                with open(dst_path, 'w') as f:
                    json.dump(sdata, f, default=str)
                self.logger_data.emit("info", f"Saved completed JSON directly: {dst_path}")
            except Exception as e:
                self.logger_data.emit("error", f"Failed to save completed JSON: {dst_path} — {e}")
        except Exception as e:
            self.logger_data.emit("error", f"Failed to move JSON: {src_path} → {dst_path} — {e}")


    def update_firebase(self, sdata, key=['name', 'init_do', 'init_pressure', 'pid', 'do', 'temp', 'pressure', 'battv', 'lng', 'lat', 'message_time', 'ysi_do_mgl']):
        data, message_time = self.convert_datadict_for_save(sdata, key, False)

        try:
            pond_id = sdata[key[3]]
            if self.app is not None:
                db.reference('LH_Farm/pond_' + pond_id + '/' + message_time + '/').set(data)
                data[key[10]] = message_time
            else:
                self.update_logger_text("warning", "uploading data to firebase failed")
                data[key[10]] = message_time
                return False, data
        except Exception as error:
            print("An exception occurred:", error)
            self.logger_data.emit("warning", "uploading data to firebase failed")
            print("uploading data to firebase failed")
            self.fail_counter +=1
            if self.fail_counter >= self.max_fail:
                self.app = self.restart_firebase(self.app)
                self.fail_counter = 0
            data[key[10]] = message_time
            return False, data
        return True, data

    def update_firebase_when_internet(self):
        # upload when internet recovered
        for i in reversed(range(len(self.sdatas))):
            sdata = self.sdatas[i]
            # print("update_firebase_when_internet")
            # print(sdata)
            upload_status, data_dict = self.update_firebase(sdata, self.key)
            if upload_status:
                # self.move_json_to_completed(sdata)
                self.move_txt_to_completed(sdata)

                self.logger_data.emit("info", "upload missing data to firebase completed")
                del self.sdatas[i]

                try:
                    # แปลง message_time เป็นวันที่ เพื่อหาไฟล์ CSV ที่เกี่ยวข้อง
                    msg_time_str = sdata.get("message_time", "")
                    msg_date = datetime.strptime(msg_time_str.split("_")[0], "%Y%m%d").strftime("%Y-%m-%d")

                    # โหลดไฟล์ CSV เดิม
                    file_path = os.path.join(self.database_folder, f"{self.truck_id}_{msg_date}.csv")
                    if os.path.exists(file_path):
                        df = pd.read_csv(file_path)

                        # หาตำแหน่งแถวที่ message_time ตรงกัน
                        match_index = df[df["message_time"] == msg_time_str].index

                        if not match_index.empty:
                            df.loc[match_index, "upload status"] = True
                            df.to_csv(file_path, index=False)
                    
                except Exception as e:
                    self.logger_data.emit("error", f"Failed to update CSV status for {msg_time_str}: {e}")
                    
                self.msleep(300)

    def save_datadict_txt(self, sdata, key):
        data, message_time = self.convert_datadict_for_save(sdata, key, full_info=True)
        safe_time = message_time.replace(":", "-")
        txt_file = os.path.join(self.unsaved_json, safe_time + ".txt")

        try:
            os.makedirs(self.unsaved_json, exist_ok=True)
            with open(txt_file, 'w') as f:
                for k, v in data.items():
                    if isinstance(v, list):
                        v_str = ','.join(str(x) for x in v)
                        f.write(f"{k}=[{v_str}]\n")
                    else:
                        f.write(f"{k}={v}\n")
            self.logger_data.emit("info", f"Saved TXT: {txt_file}")
        except Exception as e:
            self.logger_data.emit("error", f"Failed to save TXT: {txt_file} — {e}")

    def convert_txt_to_dict(self, txt_file):
        sdata = {}
        try:
            with open(txt_file, 'r') as f:
                lines = f.readlines()
                for line in lines:
                    if '=' not in line:
                        continue
                    key, val = line.strip().split('=', 1)

                    # Type conversion by key name
                    if key in ['sid', 'pid', 'type', 'message_time']:
                        sdata[key] = val
                    elif key in ['init_do', 'init_pressure', 'batt_v', 'lat', 'lng', 'ysi_do_mgl', 'do']:
                        try:
                            sdata[key] = float(val) if val != 'None' else None
                        except:
                            sdata[key] = None
                    elif key in ['temp', 'pressure']:
                        val_clean = val.strip('[]')
                        if val_clean:
                            sdata[key] = [float(x) for x in val_clean.split(',')]
                        else:
                            sdata[key] = []
                    else:
                        sdata[key] = val  # fallback: string
            # print("txt to dict conversion completed")
            # print(sdata)
            return sdata
        except Exception as e:
            self.logger_data.emit("error", f"Failed to read TXT: {txt_file} — {e}")
            return None

    def move_txt_to_completed(self, sdata):
        safe_time = sdata['message_time'].replace(":", "-")
        src_path = os.path.join(self.unsaved_json, safe_time + ".txt")
        dst_path = os.path.join(self.completed_upload, safe_time + ".txt")

        try:
            os.makedirs(self.completed_upload, exist_ok=True)
            shutil.move(src_path, dst_path)
            self.logger_data.emit("info", f"Moved txt file to completed: {dst_path}")
        except FileNotFoundError:
            self.logger_data.emit("warning", f"Source file not found, saving new txt: {dst_path}")
        except Exception as e:
            self.logger_data.emit("error", f"Failed to move txt: {src_path} → {dst_path} — {e}")