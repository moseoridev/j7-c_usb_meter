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

# Global State
latest_data: Measurement | None = None
connection_status: str = "Initializing..."
connected_clients: list[WebSocket] = []
logger = logging.getLogger("uvicorn")

async def broadcast_status(msg: str):
    global connection_status
    connection_status = msg
    payload = json.dumps({"type": "status", "msg": msg})
    # Broadcast to all clients
    for client in connected_clients:
        try:
            await client.send_text(payload)
        except:
            pass

async def broadcast_data(m: Measurement):
    payload = json.dumps({"type": "data", "data": m.to_dict()})
    for client in connected_clients:
        try:
            await client.send_text(payload)
        except:
            pass

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
        
        # Broadcast immediately
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
            logger.error(f"BLE Error: {e}")
            await broadcast_status(f"Error: {str(e)}")
            await asyncio.sleep(5)
    
    if csv_file:
        csv_file.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
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
    
    # Send initial state
    await websocket.send_text(json.dumps({"type": "status", "msg": connection_status}))
    if latest_data:
        await websocket.send_text(json.dumps({"type": "data", "data": latest_data.to_dict()}))
        
    try:
        while True:
            await websocket.receive_text() # Keep connection open
    except WebSocketDisconnect:
        connected_clients.remove(websocket)