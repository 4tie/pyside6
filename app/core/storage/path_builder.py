"""Path building utilities with naming strategy."""
from pathlib import Path
import uuid
from app.core.utils.app_logger import get_logger

_log = get_logger("storage.path_builder")

def build_run_id() -> str:
    """Generate unique run ID for tracking."""
    return uuid.uuid4().hex[:12]

def build_gate_export_dir(
    sandbox_dir: Path,
    gate_name: str,
    iteration_number: int,
) -> Path:
    """Build export directory path for gate results with naming strategy."""
    run_id = build_run_id()
    export_dir = sandbox_dir / f"gate_{gate_name}_{iteration_number:03d}_{run_id}"
    export_dir.mkdir(parents=True, exist_ok=True)
    _log.debug("Created gate export dir: %s", export_dir)
    return export_dir
