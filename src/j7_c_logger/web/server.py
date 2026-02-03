import asyncio
import csv
import json
import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager
from collections import deque

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from j7_c_logger.core.client import J7CBLEClient
from j7_c_logger.core.protocol import Measurement

# Global State
latest_data: Measurement | None = None
# Store last 3600 points (approx 1 hour) for chart restoration
history_buffer: deque = deque(maxlen=3600)
connection_status: str = "Initializing..."
connected_clients: list[WebSocket] = []
logger = logging.getLogger("uvicorn")

# Configuration (set by main.py)
CSV_LOG_PATH = os.getenv("J7C_CSV_PATH", "web_log.csv")

async def broadcast_status(msg: str):
    global connection_status
    connection_status = msg
    payload = json.dumps({"type": "status", "msg": msg})
    to_remove = []
    for client in connected_clients:
        try:
            await client.send_text(payload)
        except:
            to_remove.append(client)
    for c in to_remove:
        if c in connected_clients: connected_clients.remove(c)

async def broadcast_data(m: Measurement):
    # Only broadcast 'live' updates (single point)
    payload = json.dumps({"type": "data", "data": m.to_dict()})
    to_remove = []
    for client in connected_clients:
        try:
            await client.send_text(payload)
        except:
            to_remove.append(client)
    for c in to_remove:
        if c in connected_clients: connected_clients.remove(c)

async def ble_worker():
    global latest_data
    csv_file = None
    csv_writer = None
    
    try:
        csv_file = open(CSV_LOG_PATH, 'w', newline='')
    except Exception as e:
        logger.error(f"CSV Error: {e}")

    def on_measurement(m: Measurement):
        global latest_data
        latest_data = m
        history_buffer.append(m.to_dict()) # Save to RAM
        
        # Save to Disk
        nonlocal csv_writer
        if csv_file:
            try:
                if not csv_writer:
                    csv_writer = csv.DictWriter(csv_file, fieldnames=m.to_dict().keys())
                    csv_writer.writeheader()
                csv_writer.writerow(m.to_dict())
                csv_file.flush()
            except Exception as e:
                logger.error(f"Write Error: {e}")
        
        asyncio.create_task(broadcast_data(m))

    client = J7CBLEClient(on_measurement=on_measurement)
    
    while True:
        try:
            await broadcast_status("Scanning...")
            device = await client.find_device()
            
            if device:
                logger.info(f"Connected to {device.name}")
                await broadcast_status(f"Connecting to {device.name}...")
                await client.run(device.address)
                await broadcast_status("Disconnected. Retrying...")
            else:
                await broadcast_status("Device not found. Retrying...")
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"BLE Loop Error: {e}")
            await broadcast_status(f"Error: {e}")
            await asyncio.sleep(5)
    
    if csv_file:
        csv_file.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(ble_worker())
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
    
    # 1. Send Status
    await websocket.send_text(json.dumps({"type": "status", "msg": connection_status}))
    
    # 2. Send History (Bulk) for Chart Restoration
    if history_buffer:
        await websocket.send_text(json.dumps({"type": "history", "data": list(history_buffer)}))
    
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)