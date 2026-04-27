"""API endpoints for the optimization loop.

Provides endpoints to start, stop, and monitor the auto-optimization loop.
"""
from typing import List

from fastapi import APIRouter, HTTPException, Depends

from app.core.services.loop_service import LoopService
from leave.web.dependencies import LoopServiceDep
from leave.web.models import (
    LoopStatusResponse,
    LoopStartRequest,
    LoopIterationResponse,
)

router = APIRouter()


@router.get("/loop/status", response_model=LoopStatusResponse)
async def get_loop_status(
    loop_service: LoopServiceDep,
) -> LoopStatusResponse:
    """Get current loop status."""
    return LoopStatusResponse(
        running=loop_service.is_running(),
        current_iteration=None,  # Will be populated from loop state
        total_iterations=None,
        strategy=None,
    )


@router.post("/loop/start")
async def start_loop(
    request: LoopStartRequest,
    loop_service: LoopServiceDep,
) -> dict:
    """Start the optimization loop with the given configuration."""
    # For now, return a placeholder response
    # Full implementation will integrate with LoopService.start()
    return {
        "status": "queued",
        "message": "Loop execution will be implemented with full LoopService integration",
        "config": {
            "strategy": request.strategy,
            "max_iterations": request.max_iterations,
            "target_profit_pct": request.target_profit_pct,
        },
    }


@router.post("/loop/stop")
async def stop_loop(
    loop_service: LoopServiceDep,
) -> dict:
    """Stop the currently running loop."""
    if not loop_service.is_running():
        raise HTTPException(status_code=400, detail="Loop is not running")
    
    # Full implementation will call loop_service.stop()
    return {"status": "stopped", "message": "Loop stop will be implemented with full LoopService integration"}


@router.get("/loop/iterations", response_model=List[LoopIterationResponse])
async def get_loop_iterations(
    loop_service: LoopServiceDep,
) -> List[LoopIterationResponse]:
    """Get history of loop iterations."""
    # For now, return empty list
    # Full implementation will retrieve iteration history from LoopService
    return []
