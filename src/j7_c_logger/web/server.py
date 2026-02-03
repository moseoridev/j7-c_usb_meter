import asyncio
import csv
import json
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from j7_c_logger.core.client import J7CBLEClient
from j7_c_logger.core.protocol import Measurement

# Global State for latest measurement
latest_data: Measurement | None = None
connected_clients: list[WebSocket] = []
logger = logging.getLogger("uvicorn")

# Background BLE Task
async def ble_worker(csv_path: str = None):
    global latest_data
    
    csv_file = None
    csv_writer = None
    if csv_path:
        csv_file = open(csv_path, 'w', newline='')
    
    def on_measurement(m: Measurement):
        global latest_data
        latest_data = m
        
        # Write to CSV
        nonlocal csv_writer
        if csv_file:
            if not csv_writer:
                csv_writer = csv.DictWriter(csv_file, fieldnames=m.to_dict().keys())
                csv_writer.writeheader()
            csv_writer.writerow(m.to_dict())
            csv_file.flush()

    client = J7CBLEClient(on_measurement=on_measurement)
    
    while True:
        try:
            device = await client.find_device()
            if device:
                logger.info(f"Connected to {device.name}")
                await client.run(device.address)
            else:
                logger.warning("Device not found. Retrying in 5s...")
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"BLE Error: {e}")
            await asyncio.sleep(5)
    
    if csv_file:
        csv_file.close()

# FastAPI App Lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start BLE worker
    # Note: We need a way to pass CSV path. For simplicity in this v1, 
    # we default to 'web_session.csv' or get from env var if needed.
    # In a real app, we might pass args differently.
    task = asyncio.create_task(ble_worker("web_log.csv"))
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def get():
    html_path = Path(__file__).parent / "templates" / "index.html"
    return HTMLResponse(html_path.read_text())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            if latest_data:
                await websocket.send_text(json.dumps(latest_data.to_dict()))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
