"""Property-based tests for ProcessRunManager.

Feature: process-run-manager
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.models.run_models import ProcessRun, RunStatus
from app.core.services.process_run_manager import ProcessRunManager


# ---------------------------------------------------------------------------
# Property 4: stop_run on non-RUNNING run raises ValueError
# Validates: Requirements 2.5
# ---------------------------------------------------------------------------


@given(
    status=st.sampled_from(
        [RunStatus.PENDING, RunStatus.FINISHED, RunStatus.FAILED, RunStatus.CANCELLED]
    )
)
@settings(max_examples=100)
def test_stop_run_non_running_raises_value_error(status: RunStatus) -> None:
    """For any ProcessRun whose status is not RUNNING, stop_run must raise ValueError.

    **Validates: Requirements 2.5**
    """
    manager = ProcessRunManager()

    # Construct a ProcessRun and manually set its status to a non-RUNNING value
    run = ProcessRun(command=["echo", "hello"])
    run.status = status

    # Inject directly into _runs without launching a subprocess
    manager._runs[run.run_id] = run

    with pytest.raises(ValueError):
        manager.stop_run(run.run_id)


# ---------------------------------------------------------------------------
# Property 7: get_run with unknown id raises KeyError
# Validates: Requirements 2.9
# ---------------------------------------------------------------------------


@given(arbitrary_id=st.text(min_size=1))
@settings(max_examples=100)
def test_get_run_unknown_id_raises_key_error(arbitrary_id: str) -> None:
    """For any string not returned by start_run, get_run must raise KeyError.

    **Validates: Requirements 2.9**
    """
    manager = ProcessRunManager()

    # The manager is empty — no runs have been started
    with pytest.raises(KeyError):
        manager.get_run(arbitrary_id)


# ---------------------------------------------------------------------------
# Property 8: list_runs preserves creation order and supports status filtering
# Validates: Requirements 2.10, 8.1, 8.2
# ---------------------------------------------------------------------------


@given(
    statuses=st.lists(
        st.sampled_from(list(RunStatus)),
        min_size=1,
        max_size=10,
    )
)
@settings(max_examples=100)
def test_list_runs_ordering_and_status_filtering(statuses: list[RunStatus]) -> None:
    """list_runs() returns runs in insertion order; list_runs(status=S) returns
    exactly the subset with status == S.

    **Validates: Requirements 2.10, 8.1, 8.2**
    """
    manager = ProcessRunManager()

    # Construct ProcessRun instances with the given statuses and inject them
    runs: list[ProcessRun] = []
    for status in statuses:
        run = ProcessRun(command=["echo", "test"])
        run.status = status
        manager._runs[run.run_id] = run
        runs.append(run)

    # list_runs() must return all runs in insertion order
    all_runs = manager.list_runs()
    assert len(all_runs) == len(runs), (
        f"Expected {len(runs)} runs, got {len(all_runs)}"
    )
    for i, (expected, actual) in enumerate(zip(runs, all_runs)):
        assert expected.run_id == actual.run_id, (
            f"Run at position {i} has wrong run_id: "
            f"expected {expected.run_id!r}, got {actual.run_id!r}"
        )

    # list_runs(status=S) must return exactly the subset with status == S
    for filter_status in RunStatus:
        filtered = manager.list_runs(status=filter_status)
        expected_filtered = [r for r in runs if r.status == filter_status]

        assert len(filtered) == len(expected_filtered), (
            f"For status={filter_status.value}: expected {len(expected_filtered)} runs, "
            f"got {len(filtered)}"
        )
        for expected_run, actual_run in zip(expected_filtered, filtered):
            assert expected_run.run_id == actual_run.run_id, (
                f"Filtered run mismatch for status={filter_status.value}: "
                f"expected {expected_run.run_id!r}, got {actual_run.run_id!r}"
            )
        # All returned runs must have the correct status
        for r in filtered:
            assert r.status == filter_status, (
                f"list_runs(status={filter_status.value}) returned run with "
                f"status={r.status.value}"
            )
