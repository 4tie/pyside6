"""WebSocket handler for loop progress updates.

Provides real-time updates during the optimization loop execution.
"""
from fastapi import WebSocket, WebSocketDisconnect
import json
from typing import Dict, Any

# Connection manager for loop WebSocket connections
class LoopConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_iteration_start(self, iteration: int, params: Dict[str, Any]):
        """Send iteration start message to all connected clients."""
        data = {
            "type": "iteration_start",
            "data": {
                "iteration": iteration,
                "params": params
            }
        }
        for connection in self.active_connections:
            await connection.send_json(data)

    async def send_gate_result(self, gate_name: str, passed: bool, metrics: Dict[str, Any]):
        """Send gate result message to all connected clients."""
        data = {
            "type": "gate_result",
            "data": {
                "gate_name": gate_name,
                "passed": passed,
                "metrics": metrics
            }
        }
        for connection in self.active_connections:
            await connection.send_json(data)

    async def send_diagnosis(self, issues: list, suggestions: list):
        """Send diagnosis message to all connected clients."""
        data = {
            "type": "diagnosis",
            "data": {
                "issues": issues,
                "suggestions": suggestions
            }
        }
        for connection in self.active_connections:
            await connection.send_json(data)

    async def send_suggestion(self, parameter: str, proposed_value: Any, reason: str):
        """Send suggestion message to all connected clients."""
        data = {
            "type": "suggestion",
            "data": {
                "parameter": parameter,
                "proposed_value": proposed_value,
                "reason": reason
            }
        }
        for connection in self.active_connections:
            await connection.send_json(data)

    async def send_complete(self, total_iterations: int, best_run_id: str, stop_reason: str):
        """Send completion message to all connected clients."""
        data = {
            "type": "complete",
            "data": {
                "total_iterations": total_iterations,
                "best_run_id": best_run_id,
                "stop_reason": stop_reason
            }
        }
        for connection in self.active_connections:
            await connection.send_json(data)


manager = LoopConnectionManager()


async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for loop progress updates."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and handle any client messages
            data = await websocket.receive_text()
            # Echo back or handle client messages if needed
            await websocket.send_json({"type": "echo", "data": json.loads(data)})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
