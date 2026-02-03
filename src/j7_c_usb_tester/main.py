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

def parse_data(data_pkt):
    if not data_pkt or len(data_pkt) != 36:
        return None
    if not data_pkt.startswith(b'\xFF\x55'):
        return None

    def _get_duration(pkt):
        return datetime.timedelta(days=pkt[0], hours=pkt[1], minutes=pkt[2], seconds=pkt[3])

    return {
            'voltage': struct.unpack('>I', (b'\x00' + data_pkt[4:7]))[0]/100,
            'current': struct.unpack('>I', (b'\x00' + data_pkt[7:10]))[0]/100,
            'mAh': struct.unpack('>I', (b'\x00' + data_pkt[10:13]))[0],
            'Wh': struct.unpack('>I', data_pkt[13:17])[0]/100,
            'D+': struct.unpack('>H', data_pkt[17:19])[0]/100,
            'D-': struct.unpack('>H', data_pkt[19:21])[0]/100,
            'temperature': struct.unpack('>H', data_pkt[21:23])[0],
            'duration': _get_duration(data_pkt[23:27]),
        }

def read_loop(serial_obj):
    """Yields parsed data from an open serial object."""
    serial_obj.reset_input_buffer()
    while True:
        data = serial_obj.read(36)
        if data:
            parsed = parse_data(data)
            if parsed:
                yield (data, parsed)
            else:
                pass

def _wake_up_device(s):
    """Toggles DTR/RTS to simulate a fresh connection."""
    s.dtr = False
    s.rts = False
    time.sleep(0.5) 
    s.dtr = True
    s.rts = True
    time.sleep(0.5)

def auto_run(csv_filename):
    print("Auto-detecting J7-C/UC96 USB Tester...")
    ports = serial.tools.list_ports.comports()
    target_serial = None
    
    for port_info in ports:
        port = port_info.device
        if "Bluetooth-Incoming" in port or "wlan" in port: 
            continue
            
        print(f"Probing {port}...", end='', flush=True)
        try:
            s = serial.Serial(port, timeout=2.5)
            _wake_up_device(s)
            
            start_time = time.time()
            buf = b""
            found = False
            
            while time.time() - start_time < 5.0:
                if s.in_waiting or True: 
                    chunk = s.read(s.in_waiting or 36)
                    if chunk:
                        buf += chunk
                        if b'\xFF\x55' in buf:
                            found = True
                            break
                time.sleep(0.1)
            
            if found:
                print(" FOUND!")
                print(f"  -> Locked on {port}. Keeping connection open.")
                target_serial = s
                break
            else:
                s.close()
                print(" No data.")
        except (OSError, serial.SerialException) as e:
            print(f" Failed ({e}).")

    if not target_serial:
        print("\n[Error] No transmitting device found.")
        print("Tip: If the device is paired, try 'Forget Device' and re-pair to reset the connection state.")
        return

    run_logging(target_serial, csv_filename)

def manual_run(port, csv_filename):
    print(f"Connecting to {port}...")
    try:
        s = serial.Serial(port, timeout=3)
        _wake_up_device(s)
        run_logging(s, csv_filename)
    except serial.SerialException as e:
        print(f"Connection Failed: {e}")

def run_logging(serial_obj, csv_filename):
    csv_file = None
    csv_writer = None
    
    print("Starting Data Logger. Press Ctrl+C to stop.")
    try:
        if csv_filename:
            csv_file = open(csv_filename, 'w', newline='')
            print(f"Saving data to: {csv_filename}")

        for data, parsed_data in read_loop(serial_obj):
            if not csv_writer and csv_file:
                csv_writer = csv.DictWriter(csv_file, fieldnames=parsed_data.keys())
                csv_writer.writeheader()

            if csv_writer:
                csv_writer.writerow(parsed_data)

            print(f"{binascii.hexlify(data[:4]).decode('utf-8')}... Temp:{parsed_data['temperature']}C V:{parsed_data['voltage']} A:{parsed_data['current']}")
            
    except KeyboardInterrupt:
        print("\nStopping...")
    except Exception as e:
        print(f"\nError during logging: {e}")
    finally:
        if csv_file:
            csv_file.close()
            print("CSV file closed.")
        if serial_obj:
            try:
                serial_obj.dtr = False
                serial_obj.rts = False
                time.sleep(0.5)
                serial_obj.close()
                print("Serial port closed gracefully.")
            except:
                pass


def parse_args():
    parser = argparse.ArgumentParser(description='J7-C/UC96 USB Tester Data Logger')
    subparsers = parser.add_subparsers(dest='command', help='Mode')

    auto_parser = subparsers.add_parser('auto', help='Auto-detect and run')
    auto_parser.add_argument('--csv', help='Output CSV filename')

    scan_parser = subparsers.add_parser('scan', help='Scan only (May reset connection!)')

    run_parser = subparsers.add_parser('run', help='Manual connect')
    run_parser.add_argument('device_port', help='Device port path')
    run_parser.add_argument('--csv', help='Output CSV filename')

    return parser, parser.parse_known_args()

def main():
    parser, (args, remaining) = parse_args()
    
    command = args.command
    
    if command == 'auto':
        auto_run(args.csv)
    elif command == 'scan':
        print("Note: 'scan' opens and closes the port, which may freeze the device.")
        auto_run(None) 
    elif command == 'run' or (command is None and len(remaining) > 0):
        if command is None:
            run_parser = argparse.ArgumentParser()
            run_parser.add_argument('--csv')
            run_parser.add_argument('device_port')
            if len(remaining) == 0:
                parser.print_help()
                return
            run_args = run_parser.parse_args(remaining)
        else:
            run_args = args
            
        manual_run(run_args.device_port, run_args.csv)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
