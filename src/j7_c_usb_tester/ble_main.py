import asyncio
import csv
import binascii
import struct
import datetime
import argparse
from bleak import BleakScanner, BleakClient

# Define UUIDs
UART_SERVICE_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb"
UART_RX_CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"

def parse_data(data_pkt):
    if not data_pkt or len(data_pkt) != 36:
        return None
    if not data_pkt.startswith(b'\xFF\x55'):
        return None

    def _get_duration(pkt):
        return datetime.timedelta(days=pkt[0], hours=pkt[1], minutes=pkt[2], seconds=pkt[3])

    # Core measurements
    v = struct.unpack('>I', (b'\x00' + data_pkt[4:7]))[0]/100
    i = struct.unpack('>I', (b'\x00' + data_pkt[7:10]))[0]/100
    
    # Cumulative data
    mah = struct.unpack('>I', (b'\x00' + data_pkt[10:13]))[0]
    wh = struct.unpack('>I', data_pkt[13:17])[0]/100
    
    # USB Data lines
    d_plus = struct.unpack('>H', data_pkt[17:19])[0]/100
    d_minus = struct.unpack('>H', data_pkt[19:21])[0]/100
    
    # Environmental
    temp = struct.unpack('>H', data_pkt[21:23])[0]
    duration = _get_duration(data_pkt[23:27])

    # Protection Settings (Corrected based on user analysis)
    # V- was actually LVP (Low Voltage Protection)
    lvp = struct.unpack('>H', data_pkt[30:32])[0]/100
    # V+ was actually OCP (Over Current Protection) - It is Current limit, not Voltage
    # Check if 9.00 matches 900 (0x0384). If it's 9.00A, then divisor is 100.
    ocp = struct.unpack('>H', data_pkt[32:34])[0]/100

    # Calculated derived values
    pwr = v * i
    res = v / i if i > 0 else 0

    return {
            'timestamp': datetime.datetime.now().isoformat(),
            'voltage': v,
            'current': i,
            'power': pwr,
            'resistance': res,
            'mAh': mah,
            'Wh': wh,
            'D+': d_plus,
            'D-': d_minus,
            'temperature': temp,
            'duration': str(duration),
            'LVP': lvp,  # Low Voltage Protection Setting
            'OCP': ocp,  # Over Current Protection Setting
            'raw_hex': data_pkt.hex()
        }

class BLELogger:
    def __init__(self, csv_filename=None):
        self.csv_filename = csv_filename
        self.csv_file = None
        self.csv_writer = None
        if csv_filename:
            self.csv_file = open(csv_filename, 'w', newline='')
            print(f"Saving data to: {csv_filename}")

    def handle_notification(self, sender, data):
        if len(data) == 36:
            parsed = parse_data(data)
            if parsed:
                self._log(data, parsed)

    def _log(self, raw_data, parsed_data):
        if self.csv_file and not self.csv_writer:
            self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=parsed_data.keys())
            self.csv_writer.writeheader()
        
        if self.csv_writer:
            self.csv_writer.writerow(parsed_data)
            self.csv_file.flush()

        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] "
              f"{parsed_data['voltage']:5.2f}V {parsed_data['current']:5.2f}A {parsed_data['power']:6.2f}W | "
              f"D+:{parsed_data['D+']:.2f}V D-:{parsed_data['D-']:.2f}V | "
              f"LVP:<{parsed_data['LVP']:.2f}V OCP:>{parsed_data['OCP']:.2f}A")

    def close(self):
        if self.csv_file:
            self.csv_file.close()

async def run_ble_logger(csv_filename=None):
    logger = BLELogger(csv_filename)
    print("Scanning for J7-C/UC96 BLE devices...")
    
    devices = await BleakScanner.discover(timeout=5.0)
    target_device = next((d for d in devices if d.name and ("UC96" in d.name or "J7-C" in d.name)), None)
            
    if not target_device:
        print("Device not found.")
        logger.close()
        return

    print(f"Found {target_device.name}! Connecting...")
    try:
        async with BleakClient(target_device.address) as client:
            await client.start_notify(UART_RX_CHAR_UUID, logger.handle_notification)
            print("Logging started. Press Ctrl+C to stop.")
            while True:
                await asyncio.sleep(1)
                if not client.is_connected: break
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        logger.close()

def main_ble(csv_filename=None):
    try:
        asyncio.run(run_ble_logger(csv_filename))
    except KeyboardInterrupt:
        print("\nStopped.")
