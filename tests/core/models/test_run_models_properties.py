"""Property-based tests for ProcessRun construction invariants.

Feature: process-run-manager
"""

import re
import uuid

from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.models.run_models import ProcessRun, RunStatus

# UUID4 pattern: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
_UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Property 1: ProcessRun construction invariants
# Validates: Requirements 1.2, 1.3
# ---------------------------------------------------------------------------


@given(
    command=st.lists(st.text(min_size=1), min_size=1),
    cwd=st.one_of(st.none(), st.text(min_size=1)),
)
@settings(max_examples=100)
def test_process_run_construction_invariants(command: list[str], cwd) -> None:
    """For any non-empty command and optional cwd, a newly constructed ProcessRun
    must have a UUID4 run_id, PENDING status, and all optional fields at their
    zero/None values.

    **Validates: Requirements 1.2, 1.3**
    """
    run = ProcessRun(command=command, cwd=cwd)

    # run_id must be a non-empty string matching UUID4 format
    assert isinstance(run.run_id, str), "run_id must be a str"
    assert len(run.run_id) > 0, "run_id must be non-empty"
    assert _UUID4_RE.match(run.run_id), f"run_id {run.run_id!r} does not match UUID4 format"

    # status must be PENDING
    assert run.status == RunStatus.PENDING, f"Expected PENDING, got {run.status}"

    # All optional fields must be None
    assert run.started_at is None, "started_at must be None on construction"
    assert run.finished_at is None, "finished_at must be None on construction"
    assert run.exit_code is None, "exit_code must be None on construction"

    # Buffers must be empty lists
    assert run.stdout_buffer == [], "stdout_buffer must be [] on construction"
    assert run.stderr_buffer == [], "stderr_buffer must be [] on construction"

    # command and cwd must be stored as-is
    assert run.command == command
    assert run.cwd == cwd


# ---------------------------------------------------------------------------
# Property 2: run_id uniqueness
# Validates: Requirements 1.2
# ---------------------------------------------------------------------------


@given(
    commands=st.lists(
        st.lists(st.text(min_size=1), min_size=1),
        min_size=2,
        max_size=20,
    )
)
@settings(max_examples=100)
def test_run_id_uniqueness(commands: list[list[str]]) -> None:
    """For any collection of independently constructed ProcessRun instances,
    all run_id values must be distinct.

    **Validates: Requirements 1.2**
    """
    runs = [ProcessRun(command=cmd) for cmd in commands]
    run_ids = [run.run_id for run in runs]

    assert len(run_ids) == len(set(run_ids)), (
        f"Duplicate run_ids found among {len(runs)} instances: {run_ids}"
    )
