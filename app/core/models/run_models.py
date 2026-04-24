"""Data models for ProcessRunManager.

Defines RunStatus enum and ProcessRun dataclass used to track
subprocess invocations throughout their lifecycle.
"""

import queue
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from app.core.utils.app_logger import get_logger

_log = get_logger("core.run_models")


class RunStatus(str, Enum):
    """Lifecycle states for a ProcessRun.

    Using str as a mixin makes the enum JSON-serializable without a
    custom encoder, which simplifies FastAPI response models.
    """

    PENDING = "pending"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProcessRun:
    """Immutable-identity record representing one subprocess invocation.

    Holds all metadata and I/O queues for a single run. The raw
    subprocess.Popen handle is stored on the manager, not here, keeping
    the public model clean.

    Args:
        command: Tokenized command list (e.g. ["python", "-m", "freqtrade", ...]).
        cwd: Optional working directory for the subprocess.
        run_id: UUID4 string uniquely identifying this run. Auto-generated.
        status: Current lifecycle state. Starts as PENDING.
        started_at: UTC datetime when the subprocess was launched. None until started.
        finished_at: UTC datetime when the subprocess exited. None until finished.
        exit_code: Process exit code. None until the process exits.
        stdout_queue: Thread-safe queue receiving stdout lines line-by-line.
        stderr_queue: Thread-safe queue receiving stderr lines line-by-line.
        stdout_buffer: Accumulated stdout lines for late consumers.
        stderr_buffer: Accumulated stderr lines for late consumers.
    """

    command: list[str]
    cwd: Optional[str] = None
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: RunStatus = RunStatus.PENDING
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    exit_code: Optional[int] = None
    # Typed as queue.Queue (not queue.Queue[str]) for Python 3.9 compatibility
    stdout_queue: queue.Queue = field(default_factory=queue.Queue)  # type: ignore[assignment]
    stderr_queue: queue.Queue = field(default_factory=queue.Queue)  # type: ignore[assignment]
    stdout_buffer: list[str] = field(default_factory=list)
    stderr_buffer: list[str] = field(default_factory=list)
