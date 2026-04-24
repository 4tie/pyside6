"""Process event models for rich callback support."""
from typing import Literal
from dataclasses import dataclass

@dataclass
class ProcessEvent:
    """Rich event for process lifecycle callbacks with structured fields.
    
    Uses specific fields instead of generic data for better UI/AI parsing.
    """
    type: Literal["started", "stdout", "stderr", "finished", "error"]
    message: str | None = None
    exit_code: int | None = None
    metadata: dict | None = None
    timestamp: float = 0.0
