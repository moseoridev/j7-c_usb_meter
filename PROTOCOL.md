# J7-C BLE Protocol Documentation

This document describes the Bluetooth Low Energy (BLE) data packet format used by the **J7-C / UC96** USB Tester.

## BLE Service Info
- **Service UUID**: `0000ffe0-0000-1000-8000-00805f9b34fb`
- **Characteristic UUID**: `0000ffe1-0000-1000-8000-00805f9b34fb` (Notify)

## Data Packet Structure
The device broadcasts a **36-byte** packet approximately once per second. Multi-byte values are generally **Big-Endian**, except for USB data lines and temperature which are **Little-Endian**.

| Offset | Length | Type | Description | Unit / Scaling | Endian |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 0 | 2 | Header | Magic Header | `0xFF 0x55` | - |
| 2 | 1 | Byte | Unknown | Always `0x01` | - |
| 3 | 1 | Byte | Unknown | Always `0x03` | - |
| 4 | 3 | Int | **Voltage** | V / 100 | Big |
| 7 | 3 | Int | **Current** | A / 100 | Big |
| 10 | 4 | Int | **Capacity** | mAh | Big |
| 14 | 4 | Int | **Energy** | Wh / 100 | Big |
| 18 | 2 | Int | **D+ Voltage** | V / 100 | **Little** |
| 20 | 2 | Int | **D- Voltage** | V / 100 | **Little** |
| 22 | 2 | Int | **Temperature** | Celsius | **Little** |
| 24 | 4 | Time | **Duration** | Days, Hours, Mins, Secs (1 byte each) | - |
| 28 | 2 | - | *Reserved* | - | - |
| 30 | 2 | Int | **LVP Setting** | V / 100 (Low Voltage Protect) | Big |
| 32 | 2 | Int | **OCP Setting** | A / 100 (Over Current Protect) | Big |
| 34 | 1 | - | *Reserved* | - | - |
| 35 | 1 | Byte | Checksum | Sum of bytes 1-34 (firmware dependent) | - |

### Example Decoding
Raw Hex: `ff55010300039600000c9a...`

1. **Voltage**: `00 03 96` (hex) -> `918` (dec) -> **9.18 V**
2. **Current**: `00 00 0c` (hex) -> `12` (dec) -> **0.12 A**
3. **Power**: Calculated as $P = V \times I$ (e.g., $9.18 \times 0.12 = 1.10 \text{ W}$)
4. **Resistance**: Calculated as $R = V / I$ (e.g., $9.18 / 0.12 = 76.5 \Omega$)
