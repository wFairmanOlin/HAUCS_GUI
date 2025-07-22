# HAUCS_GUI Code Structure

This directory contains all Python modules and configuration files for the HAUCS-GUI software.  
The following sections describe the purpose of each file.

---

## Main GUI
- **gui02.py** – The main GUI file that manages display, user interactions, and communication between the GUI and backend (`truck_sensor.py`).

---

## Widgets (used in the main GUI)
- **battery_widget.py** – Displays the battery level.
- **led_indicator.py** – LED status indicator (Green = ready to use, Yellow = connected but not ready, Red = disconnected).
- **toggle_switch.py** – Implements a toggle switch widget (left/right state).

---

## Pop-up Windows
- **custom_yesno_dialog.py** – Custom Yes/No dialog with larger font size for field use (e.g., Calibration DO).
- **history_window.py** – Shows the DO measurement history table, reading from the local history log database.
- **result_window.py** – Displays the result summary after each DO measurement. It reads the same local history log database and may support Firebase data retrieval in the future.
  - **numpad_dialog.py** – Pop-up number pad for entering pond ID.
- **setting_dialog.py** – User settings window. Contains a numeric up/down widget:
  - **bigspin_widget.py** – A large numeric up/down widget for field usability.
- **shutdown_dialog.py** – Prevents accidental closing of the program by requiring user confirmation.

---

## Backend (Sensor and Data Processing)
- **truck_sensor.py** – The backend core handling sensor connections and internet communication.
  - **bt_sensor.py** – Interfaces with DO sensors via `adafruit_ble` (send commands, read data).
  - **firebase_worker.py** – Processes JSON files, generates history logs and CSV files, and uploads data to Firebase silently without interfering with the GUI.
  - **gps_sensor.py** – Connects to GPS devices via `adafruit_gps`. Uses `sampling_points.csv` to convert GPS locations into pond IDs. (Compass integration planned.)
  - **ysi_reader.py** – Interfaces with legacy YSI machines (analog DO meter) using ADC.

---

## Utility and Support Files
- **converter.py** – Provides four functions:
  - Celsius to Fahrenheit
  - Fahrenheit to Celsius
  - DO % saturation to mg/L
  - DO mg/L to % saturation
- **setting.setting** – Stores user or engineer settings configured via `setting_dialog.py`.
- **sampling_points.csv** – Maps GPS coordinates to pond IDs.

---

## Data and Log Folders

- **log/** – Stores program log files. A new log file is created each time the program is started.
- **DO_data/** – Stores DO sensor data from each reading cycle. Each measurement session is saved as a separate `.csv` file, which contains raw loop data and final computed DO values.
- **YSI_data/** – Stores DO data collected from the YSI machine, saved in a similar structure to `DO_data/`.
- **unsaved_json/** – Temporary storage for raw measurement results in `.txt` format. Each file corresponds to one measurement.
- **database_truck/** – Contains daily `.csv` files summarizing measurement sessions. Each CSV file represents one day of data, with one row per reading session and paths pointing to related `DO_data` and `YSI_data` files.
- **completed_json/** – Stores finalized TXT files after data is successfully uploaded.

---

**Data Flow:**
1. When a reading is performed, a `.txt` file is saved in `DO_data/` or `YSI_data/`.
2. A `.json` file for that session is created in `unsaved_json/`.
3. A summary line (including paths to data files) is appended to the daily `.csv` file in `database_truck/` inside must set upload status as `FALSE`.
4. After successful upload or post-processing, the `.txt` files from `unsaved_json/` must be moved to `completed_json/` and change upload status of `.csv` file that is the same uploaded information as `TRUE`.

---

## Log and Media
- **settings.png** – Image assets for settings UI.

---

## Notes
- Detailed function-level explanations are documented in code comments.
- For development and debugging, start the main program with:
  ```bash
  > cd /home/haucs/Desktop/HAUCS_GUI/
  > /home/haucs/buoy/bin/python3 gui02.py
  ```

## License
MIT license