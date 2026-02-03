import asyncio
import logging
from bleak import BleakScanner, BleakClient
from .protocol import parse_packet

UART_RX_CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"
logger = logging.getLogger(__name__)

class J7CBLEClient:
    def __init__(self, on_measurement=None):
        self.on_measurement = on_measurement
        self._client = None
        self._stop_event = asyncio.Event()

    async def find_device(self, timeout=5.0):
        """Scans for the device. Returns BleakDevice or None."""
        try:
            devices = await BleakScanner.discover(timeout=timeout)
            for d in devices:
                if d.name and ("UC96" in d.name or "J7-C" in d.name):
                    return d
        except Exception as e:
            logger.error(f"Scan error: {e}")
        return None

    def _notification_handler(self, sender, data):
        if len(data) == 36:
            measurement = parse_packet(data)
            if measurement and self.on_measurement:
                self.on_measurement(measurement)

    async def run(self, address):
        """Connects and listens for notifications until disconnected or stopped."""
        logger.info(f"Connecting to {address}...")
        try:
            async with BleakClient(address) as client:
                self._client = client
                logger.info("Connected!")
                
                await client.start_notify(UART_RX_CHAR_UUID, self._notification_handler)
                
                # Keep running until stop event or disconnect
                while not self._stop_event.is_set():
                    if not client.is_connected:
                        logger.warning("Device disconnected.")
                        break
                    await asyncio.sleep(1)
                    
                await client.stop_notify(UART_RX_CHAR_UUID)
        except Exception as e:
            logger.error(f"Connection error: {e}")
            raise # Re-raise to let caller handle retry

    def stop(self):
        self._stop_event.set()