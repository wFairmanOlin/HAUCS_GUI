import asyncio
from bleak import BleakScanner
import csv
import time

async def scan_ble_rssi(logfile="ble_rssi_log.csv"):
    with open(logfile, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "address", "name", "rssi"])

        def detection_callback(device, advertisement_data):
            rssi = advertisement_data.rssi if advertisement_data.rssi is not None else 'N/A'
            name = device.name or "Unknown"
            if "CIRCUIT" in name.upper():  # Case-insensitive check for "CIRCUIT" in the name
                writer.writerow([time.time(), device.address, name, rssi])
                print(f"{device.address} ({name}) RSSI={rssi} dBm")
                f.flush()  # Ensure data is written immediately (flush the file, not the writer)

        print("Scanning for BLE devices... Press Ctrl+C to stop.")
        scanner = BleakScanner(detection_callback)
        # For dongle, add: BleakScanner(detection_callback, adapter="hci1")

        await scanner.start()
        try:
            while True:
                await asyncio.sleep(1)  # Keep running indefinitely
        except KeyboardInterrupt:
            print("Stopping scan...")
        finally:
            await scanner.stop()

asyncio.run(scan_ble_rssi())