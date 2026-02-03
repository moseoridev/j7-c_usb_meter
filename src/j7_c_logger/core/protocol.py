from dataclasses import dataclass, asdict
import datetime
import struct
import binascii

@dataclass
class Measurement:
    timestamp: str
    voltage: float
    current: float
    power: float
    resistance: float
    mAh: int
    Wh: float
    d_plus: float
    d_minus: float
    temperature: int
    duration: str
    lvp: float
    ocp: float
    raw_hex: str

    def to_dict(self):
        return asdict(self)

def verify_checksum(data: bytes) -> bool:
    # J7-C Checksum: Sum of bytes 1 to 34 (0-based index) modulo 256 should equal byte 35
    # The header FF (byte 0) is usually excluded or included depending on firmware.
    # Let's try standard summation of payload excluding the magic header FF 55.
    # Or sum of everything except last byte.
    
    # Based on observation, we will skip strict checksum for now unless confirmed,
    # but we can at least check length and header.
    # If user wants strict check later, we can enable the sum logic.
    return True

def parse_packet(data: bytes) -> Measurement:
    if len(data) != 36 or not data.startswith(b'\xFF\x55'):
        return None

    # Optional: Checksum validation
    # if not verify_checksum(data): return None

    def _get_duration(pkt):
        return str(datetime.timedelta(days=pkt[0], hours=pkt[1], minutes=pkt[2], seconds=pkt[3]))

    # Core measurements
    v = struct.unpack('>I', (b'\x00' + data[4:7]))[0]/100
    i = struct.unpack('>I', (b'\x00' + data[7:10]))[0]/100
    
    # Cumulative data
    mah = struct.unpack('>I', data[10:14])[0]
    wh = struct.unpack('>I', data[14:18])[0]/100
    
    # USB Data lines
    d_plus = struct.unpack('>H', data[18:20])[0]/100
    d_minus = struct.unpack('>H', data[20:22])[0]/100
    
    # Environmental
    temp = struct.unpack('>H', data[22:24])[0]
    duration = _get_duration(data[24:28])

    # Protection Settings
    lvp = struct.unpack('>H', data[30:32])[0]/100
    ocp = struct.unpack('>H', data[32:34])[0]/100

    # Derived
    pwr = v * i
    res = v / i if i > 0 else 0

    return Measurement(
        timestamp=datetime.datetime.now().isoformat(),
        voltage=v,
        current=i,
        power=pwr,
        resistance=res,
        mAh=mah,
        Wh=wh,
        d_plus=d_plus,
        d_minus=d_minus,
        temperature=temp,
        duration=duration,
        lvp=lvp,
        ocp=ocp,
        raw_hex=data.hex()
    )