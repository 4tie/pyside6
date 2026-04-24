"""Integration tests for the Web API runs router.

Feature: process-run-manager
Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5
"""

import sys
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers.runs_router import get_manager, router
from app.core.services.process_run_manager import ProcessRunManager


def _make_app(manager: ProcessRunManager) -> FastAPI:
    """Create a fresh FastAPI app with the runs router and a custom manager."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_manager] = lambda: manager
    return app


@pytest.fixture()
def client_and_manager():
    """Provide a TestClient backed by a fresh ProcessRunManager."""
    manager = ProcessRunManager()
    app = _make_app(manager)
    with TestClient(app) as client:
        yield client, manager


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

_ECHO_CMD = [sys.executable, "-c", "import sys; print('hello'); sys.stderr.write('err\\n')"]
_SLEEP_CMD = [sys.executable, "-c", "import time; time.sleep(30)"]
_EXIT1_CMD = [sys.executable, "-c", "import sys; sys.exit(1)"]


def _wait_for_terminal(manager: ProcessRunManager, run_id: str, timeout: float = 10.0) -> None:
    """Poll until the run reaches a terminal state or timeout expires."""
    from app.core.models.run_models import RunStatus

    terminal = {RunStatus.FINISHED, RunStatus.FAILED, RunStatus.CANCELLED}
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = manager.get_run(run_id)
        if run.status in terminal:
            return
        time.sleep(0.05)
    raise TimeoutError(f"Run {run_id} did not reach terminal state within {timeout}s")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_post_runs_returns_201_with_run_id(client_and_manager):
    """POST /runs with a valid body returns 201 and a run_id in the response.

    Validates: Requirements 5.1
    """
    client, _ = client_and_manager
    response = client.post("/runs", json={"command": _ECHO_CMD})
    assert response.status_code == 201
    data = response.json()
    assert "run_id" in data
    assert data["run_id"]  # non-empty


def test_get_run_returns_200_with_all_fields(client_and_manager):
    """GET /runs/{run_id} returns 200 with all expected fields present.

    Validates: Requirements 5.2
    """
    client, _ = client_and_manager
    post_resp = client.post("/runs", json={"command": _ECHO_CMD})
    assert post_resp.status_code == 201
    run_id = post_resp.json()["run_id"]

    get_resp = client.get(f"/runs/{run_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()

    # All RunResponse fields must be present
    for field in ("run_id", "status", "command", "cwd", "started_at", "finished_at", "exit_code"):
        assert field in data, f"Field '{field}' missing from GET /runs response"

    assert data["run_id"] == run_id
    assert data["command"] == _ECHO_CMD


def test_delete_running_run_returns_200_cancelled(client_and_manager):
    """DELETE /runs/{run_id} on a running run returns 200 with status 'cancelled'.

    Validates: Requirements 5.3
    """
    client, _ = client_and_manager
    post_resp = client.post("/runs", json={"command": _SLEEP_CMD})
    assert post_resp.status_code == 201
    run_id = post_resp.json()["run_id"]

    delete_resp = client.delete(f"/runs/{run_id}")
    assert delete_resp.status_code == 200
    data = delete_resp.json()
    assert data["status"] == "cancelled"
    assert data["run_id"] == run_id


def test_get_output_returns_200_with_stdout_stderr_lists(client_and_manager):
    """GET /runs/{run_id}/output returns 200 with stdout and stderr lists.

    Validates: Requirements 5.4
    """
    client, manager = client_and_manager
    post_resp = client.post("/runs", json={"command": _ECHO_CMD})
    assert post_resp.status_code == 201
    run_id = post_resp.json()["run_id"]

    # Wait for the run to finish so buffers are populated
    _wait_for_terminal(manager, run_id)

    output_resp = client.get(f"/runs/{run_id}/output")
    assert output_resp.status_code == 200
    data = output_resp.json()

    assert "run_id" in data
    assert "stdout" in data
    assert "stderr" in data
    assert isinstance(data["stdout"], list)
    assert isinstance(data["stderr"], list)
    assert data["run_id"] == run_id


def test_delete_finished_run_returns_409(client_and_manager):
    """DELETE /runs/{run_id} on a finished run returns 409 Conflict.

    Validates: Requirements 5.5 (wrong-status path)
    """
    client, manager = client_and_manager
    post_resp = client.post("/runs", json={"command": _ECHO_CMD})
    assert post_resp.status_code == 201
    run_id = post_resp.json()["run_id"]

    # Wait for the run to finish
    _wait_for_terminal(manager, run_id)

    delete_resp = client.delete(f"/runs/{run_id}")
    assert delete_resp.status_code == 409
