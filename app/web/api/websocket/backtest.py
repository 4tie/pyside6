"""WebSocket handler for backtest progress updates.

Provides real-time progress updates during backtest execution.
"""
from fastapi import WebSocket, WebSocketDisconnect
import json

# Connection manager for backtest WebSocket connections
class BacktestConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_progress(self, progress_pct: float, message: str):
        """Send progress update to all connected clients."""
        data = {
            "type": "progress",
            "data": {
                "progress_pct": progress_pct,
                "message": message
            }
        }
        for connection in self.active_connections:
            await connection.send_json(data)

    async def send_complete(self, run_id: str, success: bool):
        """Send completion message to all connected clients."""
        data = {
            "type": "complete",
            "data": {
                "run_id": run_id,
                "success": success
            }
        }
        for connection in self.active_connections:
            await connection.send_json(data)

    async def send_error(self, error: str, details: str):
        """Send error message to all connected clients."""
        data = {
            "type": "error",
            "data": {
                "error": error,
                "details": details
            }
        }
        for connection in self.active_connections:
            await connection.send_json(data)

    async def send_log(self, line: str):
        """Send a log line to all connected clients."""
        data = {
            "type": "log",
            "data": {
                "line": line
            }
        }
        for connection in self.active_connections:
            await connection.send_json(data)


manager = BacktestConnectionManager()


async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for backtest progress updates."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and handle any client messages
            data = await websocket.receive_text()
            # Echo back or handle client messages if needed
            await websocket.send_json({"type": "echo", "data": json.loads(data)})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
