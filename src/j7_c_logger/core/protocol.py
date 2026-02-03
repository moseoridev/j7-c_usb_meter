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

def parse_packet(data: bytes) -> Measurement:
    if len(data) != 36 or not data.startswith(b'\xFF\x55'):
        return None

    def _get_duration(pkt):
        d = datetime.timedelta(days=pkt[0], hours=pkt[1], minutes=pkt[2], seconds=pkt[3])
        return str(d)

    v = struct.unpack('>I', (b'\x00' + data[4:7]))[0]/100
    i = struct.unpack('>I', (b'\x00' + data[7:10]))[0]/100
    
    return Measurement(
        timestamp=datetime.datetime.now().isoformat(),
        voltage=v,
        current=i,
        power=v * i,
        resistance=v / i if i > 0 else 0,
        mAh=struct.unpack('>I', (b'\x00' + data[10:13]))[0],
        Wh=struct.unpack('>I', data[13:17])[0]/100,
        d_plus=struct.unpack('>H', data[17:19])[0]/100,
        d_minus=struct.unpack('>H', data[19:21])[0]/100,
        temperature=struct.unpack('>H', data[21:23])[0],
        duration=_get_duration(data[23:27]),
        lvp=struct.unpack('>H', data[30:32])[0]/100,
        ocp=struct.unpack('>H', data[32:34])[0]/100,
        raw_hex=data.hex()
    )
