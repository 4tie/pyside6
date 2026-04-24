"""Web API router for ProcessRunManager.

Exposes endpoints to start, inspect, stop, and retrieve output for
subprocess runs managed by ProcessRunManager.

No subprocess.Popen objects are created here — all subprocess interaction
is delegated to ProcessRunManager.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.models.command_models import RunCommand
from app.core.models.run_models import ProcessRun, RunStatus
from app.core.services.process_run_manager import ProcessRunManager
from app.core.utils.app_logger import get_logger

_log = get_logger("api.runs_router")

# ---------------------------------------------------------------------------
# Module-level manager instance and dependency
# ---------------------------------------------------------------------------

_manager = ProcessRunManager()


def get_manager() -> ProcessRunManager:
    """Return the module-level ProcessRunManager instance."""
    return _manager


# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------


class RunRequest(BaseModel):
    """Request body for POST /runs."""

    command: list[str]
    cwd: Optional[str] = None


class RunResponse(BaseModel):
    """Response model carrying ProcessRun metadata (no queues or buffers)."""

    run_id: str
    status: RunStatus
    command: list[str]
    cwd: Optional[str]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    exit_code: Optional[int]


class RunOutputResponse(BaseModel):
    """Response model for accumulated stdout/stderr output."""

    run_id: str
    stdout: list[str]
    stderr: list[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_to_response(run: ProcessRun) -> RunResponse:
    """Convert a ProcessRun to a RunResponse."""
    return RunResponse(
        run_id=run.run_id,
        status=run.status,
        command=run.command,
        cwd=run.cwd,
        started_at=run.started_at,
        finished_at=run.finished_at,
        exit_code=run.exit_code,
    )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunResponse, status_code=201)
def create_run(
    body: RunRequest,
    manager: ProcessRunManager = Depends(get_manager),
) -> RunResponse:
    """Start a new subprocess run.

    Args:
        body: RunRequest with command list and optional cwd.
        manager: Injected ProcessRunManager.

    Returns:
        RunResponse with the new run's metadata.
    """
    cmd = RunCommand(
        program=body.command[0],
        args=body.command[1:],
        cwd=body.cwd or "",
    )
    run = manager.start_run(cmd)
    _log.info("POST /runs — started run_id=%s", run.run_id)
    return _run_to_response(run)


@router.get("/{run_id}", response_model=RunResponse)
def get_run(
    run_id: str,
    manager: ProcessRunManager = Depends(get_manager),
) -> RunResponse:
    """Return the current status and metadata for a run.

    Args:
        run_id: The unique run identifier.
        manager: Injected ProcessRunManager.

    Returns:
        RunResponse with current metadata.

    Raises:
        HTTPException: 404 if run_id is not found.
    """
    try:
        run = manager.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return _run_to_response(run)


@router.delete("/{run_id}", response_model=RunResponse)
def stop_run(
    run_id: str,
    manager: ProcessRunManager = Depends(get_manager),
) -> RunResponse:
    """Stop a running subprocess.

    Args:
        run_id: The unique run identifier.
        manager: Injected ProcessRunManager.

    Returns:
        RunResponse with updated (CANCELLED) status.

    Raises:
        HTTPException: 404 if run_id is not found.
        HTTPException: 409 if the run is not in RUNNING state.
    """
    try:
        manager.stop_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    run = manager.get_run(run_id)
    _log.info("DELETE /runs/%s — status=%s", run_id, run.status.value)
    return _run_to_response(run)


@router.get("/{run_id}/output", response_model=RunOutputResponse)
def get_output(
    run_id: str,
    manager: ProcessRunManager = Depends(get_manager),
) -> RunOutputResponse:
    """Return accumulated stdout and stderr for a run.

    Args:
        run_id: The unique run identifier.
        manager: Injected ProcessRunManager.

    Returns:
        RunOutputResponse with stdout and stderr line lists.

    Raises:
        HTTPException: 404 if run_id is not found.
    """
    try:
        run = manager.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return RunOutputResponse(
        run_id=run.run_id,
        stdout=list(run.stdout_buffer),
        stderr=list(run.stderr_buffer),
    )
