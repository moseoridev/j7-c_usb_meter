#!/usr/bin/env python3
import serial
import serial.tools.list_ports
import datetime
import contextlib
import binascii
import struct
import sys
import argparse
import csv
import time

try:
    from .ble_main import main_ble
except ImportError:
    main_ble = None

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

    # Protection Settings
    lvp = struct.unpack('>H', data_pkt[30:32])[0]/100
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
            'LVP': lvp,
            'OCP': ocp,
            'raw_hex': data_pkt.hex()
        }

def read_loop(serial_obj):
    serial_obj.reset_input_buffer()
    while True:
        data = serial_obj.read(36)
        if data:
            parsed = parse_data(data)
            if parsed:
                yield (data, parsed)

def _wake_up_device(s):
    s.dtr = False
    s.rts = False
    time.sleep(0.5) 
    s.dtr = True
    s.rts = True
    time.sleep(0.5)

def auto_run(csv_filename):
    print("Auto-detecting J7-C/UC96 USB Tester (SPP Mode)...")
    ports = serial.tools.list_ports.comports()
    target_serial = None
    for port_info in ports:
        port = port_info.device
        if "Bluetooth-Incoming" in port or "wlan" in port: continue
        print(f"Probing {port}...", end='', flush=True)
        try:
            s = serial.Serial(port, timeout=2.5)
            _wake_up_device(s)
            start_time = time.time()
            buf = b""
            found = False
            while time.time() - start_time < 5.0:
                chunk = s.read(s.in_waiting or 36)
                if chunk:
                    buf += chunk
                    if b'\xFF\x55' in buf:
                        found = True
                        break
                time.sleep(0.1)
            if found:
                print(" FOUND!")
                target_serial = s
                break
            else:
                s.close()
                print(" No data.")
        except Exception as e:
            print(f" Failed ({e}).")

    if not target_serial:
        print("\n[Error] No device found via SPP. Try: uv run j7-c-usb-tester ble")
        return
    run_logging(target_serial, csv_filename)

def run_logging(serial_obj, csv_filename):
    csv_file = None
    csv_writer = None
    print("Starting Data Logger (SPP). Press Ctrl+C to stop.")
    try:
        if csv_filename:
            csv_file = open(csv_filename, 'w', newline='')
        for data, parsed_data in read_loop(serial_obj):
            if not csv_writer and csv_file:
                csv_writer = csv.DictWriter(csv_file, fieldnames=parsed_data.keys())
                csv_writer.writeheader()
            if csv_writer:
                csv_writer.writerow(parsed_data)
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] V:{parsed_data['voltage']:5.2f}V I:{parsed_data['current']:5.2f}A LVP:<{parsed_data['LVP']:.2f}V OCP:>{parsed_data['OCP']:.2f}A")
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        if csv_file: csv_file.close()
        if serial_obj:
            serial_obj.dtr = False
            serial_obj.rts = False
            serial_obj.close()

def parse_args():
    parser = argparse.ArgumentParser(description='J7-C/UC96 USB Tester Data Logger')
    subparsers = parser.add_subparsers(dest='command', help='Mode')
    ble_p = subparsers.add_parser('ble', help='Connect via BLE (Recommended)')
    ble_p.add_argument('--csv', help='Output CSV filename')
    auto_p = subparsers.add_parser('auto', help='Auto-detect via SPP')
    auto_p.add_argument('--csv', help='Output CSV filename')
    return parser, parser.parse_known_args()

def main():
    parser, (args, remaining) = parse_args()
    if args.command == 'ble':
        if main_ble: main_ble(args.csv)
        else: print("BLE error. Install bleak.")
    elif args.command == 'auto':
        auto_run(args.csv)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()