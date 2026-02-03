import asyncio
from bleak import BleakScanner, BleakClient

async def run():
    print("Scanning for BLE devices...")
    devices = await BleakScanner.discover()
    
    target_device = None
    for d in devices:
        print(f"Found: {d.name} ({d.address})")
        # Check known names
        if d.name and ("UC96" in d.name or "J7-C" in d.name or "UD18" in d.name):
            target_device = d
            print(f" -> MATCH! Found target device: {d.name}")

    if not target_device:
        print("\nTarget device not found via BLE. Please ensure it is powered on.")
        return

    print(f"\nConnecting to {target_device.name} ({target_device.address})...")
    async with BleakClient(target_device.address) as client:
        print(f"Connected: {client.is_connected}")
        
        print("\nAvailable Services & Characteristics:")
        for service in client.services:
            print(f"[Service] {service.uuid} ({service.description})")
            for char in service.characteristics:
                print(f"  - [Char] {char.uuid} ({','.join(char.properties)})")
                
        # Try to guess the serial characteristic (often starts with 0000ffe1)
        # We will just listen to everything that has 'notify'
        print("\nAttempting to read from Notify characteristics...")
        
        def notification_handler(sender, data):
            print(f"Received from {sender}: {data.hex()}")

        for service in client.services:
            for char in service.characteristics:
                if "notify" in char.properties:
                    print(f"Subscribing to {char.uuid}...")
                    try:
                        await client.start_notify(char.uuid, notification_handler)
                        print("Subscribed! Waiting for data (5s)...")
                        await asyncio.sleep(5)
                        await client.stop_notify(char.uuid)
                    except Exception as e:
                        print(f"Failed to subscribe: {e}")

if __name__ == "__main__":
    asyncio.run(run())
