# HAUCS_GUI

HAUCS-GUI is a user-friendly graphical interface software developed for **real-time monitoring of dissolved oxygen (DO) levels** in aquaculture ponds using mobile sensors installed on a field truck.  
The software is designed to run on **Raspberry Pi 4 with a touchscreen**, requiring minimal interaction by the user.

---

## Purpose of the System
The system is intended to help farmers and field operators monitor DO levels efficiently and automatically, even without technical expertise.

Once powered on, the system:
- **Starts automatically**
- **Connects to Bluetooth DO sensors**
- **Displays real-time DO measurements**
- **Uploads results to the cloud (Firebase)**

Users can view current oxygen levels, switch between units (mg/L or % saturation), calibrate the sensor, and review the measurement history — all through a simple and intuitive touch interface.

---

## Key Features
- **Automated startup and data upload**
- **Touchscreen operation** with large fonts for outdoor readability
- **Automatic Pond ID detection via GPS**
- **DO sensor calibration** and history logs
- **Bluetooth-based DO measurement** with optional YSI sensor support
- **Offline operation** and data buffering when internet is unavailable

---

## System Architecture
The diagram below shows the hardware and data flow of the HAUCS-GUI system:

![System Architecture](architecture.png)

**Description:**
- **DO Sensor & YSI Sensor**: Capture dissolved oxygen data via Bluetooth or direct measurement.
- **Raspberry Pi + HAUCS GUI Software**: Processes the sensor data, stores it locally, and displays it on a **touchscreen monitor**.
- **GPS & Cellular Modules**: Provide location data and enable cloud synchronization via Firebase.
- **YSI Measure (ADC)**: Allows compatibility with analog sensors.

---

## Autostart Setup
To enable the GUI to start automatically on boot:

1. **Create the autostart directory:**
   ```bash
   mkdir -p ~/.config/autostart
   ```
2. Create a file named `gui.desktop` with the following content:
   ```bash
   [Desktop Entry]
   Type=Application
   Name=TRUCKGUI
   Exec=/home/haucs/Desktop/gui.sh
   ```
3. Save the `gui.desktop` file in:
   ```bash
   ~/.config/autostart
   ```