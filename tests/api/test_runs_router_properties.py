"""Property-based tests for the Web API runs router.

Feature: process-run-manager
Property 12: Web API 404 for unknown run_id
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from app.api.routers.runs_router import get_manager, router
from app.core.services.process_run_manager import ProcessRunManager


def _make_app(manager: ProcessRunManager) -> FastAPI:
    """Create a fresh FastAPI app with the runs router and a custom manager."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_manager] = lambda: manager
    return app


# ---------------------------------------------------------------------------
# Property 12: Web API 404 for unknown run_id
# Validates: Requirements 5.5
# ---------------------------------------------------------------------------


def _is_valid_path_segment(s: str) -> bool:
    """Return True if s is safe to embed as a URL path segment.

    Rejects strings that contain characters which would be interpreted as
    URL structure (e.g. '/', '?', '#') or non-printable ASCII bytes that
    httpx rejects as invalid URLs.
    """
    if not s:
        return False
    # Reject path separators and query/fragment delimiters
    if any(c in s for c in ("//", "?", "#", "\\")):
        return False
    # Reject non-printable ASCII (httpx raises InvalidURL for these)
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in s):
        return False
    return True


# Strategy: printable ASCII text that forms a valid URL path segment and
# does not accidentally match a real route prefix.
_path_segment_strategy = (
    st.text(
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            whitelist_characters="-_.",
        ),
        min_size=1,
        max_size=50,
    )
    .filter(_is_valid_path_segment)
)


@given(unknown_id=_path_segment_strategy)
@settings(max_examples=100)
def test_unknown_run_id_returns_404(unknown_id: str) -> None:
    """For any string that is not a registered run_id, GET /runs/{id},
    DELETE /runs/{id}, and GET /runs/{id}/output must all return HTTP 404.

    **Validates: Requirements 5.5**
    """
    # Fresh manager with no registered runs
    manager = ProcessRunManager()
    app = _make_app(manager)

    with TestClient(app, raise_server_exceptions=False) as client:
        get_resp = client.get(f"/runs/{unknown_id}")
        delete_resp = client.delete(f"/runs/{unknown_id}")
        output_resp = client.get(f"/runs/{unknown_id}/output")

    assert get_resp.status_code == 404, (
        f"GET /runs/{unknown_id!r} expected 404, got {get_resp.status_code}"
    )
    assert delete_resp.status_code == 404, (
        f"DELETE /runs/{unknown_id!r} expected 404, got {delete_resp.status_code}"
    )
    assert output_resp.status_code == 404, (
        f"GET /runs/{unknown_id!r}/output expected 404, got {output_resp.status_code}"
    )
