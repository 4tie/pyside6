"""
Property-based tests for ImproveService.

Property 3: BaselineParams round-trip from params.json
Validates: Requirements 3.5
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.services.improve_service import ImproveService

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------
_params_st = st.fixed_dictionaries({
    "stoploss": st.floats(min_value=-0.99, max_value=-0.01, allow_nan=False, allow_infinity=False),
    "max_open_trades": st.integers(min_value=1, max_value=10),
    "minimal_roi": st.fixed_dictionaries({
        "0": st.floats(min_value=0.001, max_value=0.5, allow_nan=False, allow_infinity=False),
        "30": st.floats(min_value=0.001, max_value=0.3, allow_nan=False, allow_infinity=False),
    }),
    "buy_params": st.just({}),
    "sell_params": st.just({}),
})


# ---------------------------------------------------------------------------
# Property 3 — BaselineParams round-trip from params.json
# Validates: Requirements 3.5
# ---------------------------------------------------------------------------
@given(params=_params_st)
@settings(max_examples=100)
def test_load_baseline_params_round_trip(params):
    """**Validates: Requirements 3.5**

    For any BaselineParams dict, writing it to params.json and loading it back
    via ImproveService.load_baseline_params() must return an equal dict
    (accounting for JSON float serialization normalization).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        run_dir = Path(tmpdir)
        (run_dir / "params.json").write_text(json.dumps(params), encoding="utf-8")
        service = ImproveService(MagicMock(), MagicMock())
        loaded = service.load_baseline_params(run_dir)
        expected = json.loads(json.dumps(params))
        assert loaded == expected


# ---------------------------------------------------------------------------
# Unit tests for ImproveService file I/O methods
# ---------------------------------------------------------------------------
import json
import os
from unittest.mock import MagicMock, patch


def _make_service(tmp_path):
    """Helper: build an ImproveService whose settings point at tmp_path."""
    mock_settings = MagicMock()
    mock_settings.user_data_path = str(tmp_path)
    mock_settings_service = MagicMock()
    mock_settings_service.load_settings.return_value = mock_settings
    return ImproveService(mock_settings_service, MagicMock())


# ---------------------------------------------------------------------------
# test_load_baseline_params
# ---------------------------------------------------------------------------
def test_load_baseline_params(tmp_path):
    params = {"stoploss": -0.10, "max_open_trades": 3}
    (tmp_path / "params.json").write_text(json.dumps(params), encoding="utf-8")

    service = ImproveService(MagicMock(), MagicMock())
    result = service.load_baseline_params(tmp_path)
    assert result == params


def test_load_baseline_params_missing_file(tmp_path):
    empty_dir = tmp_path / "empty_run"
    empty_dir.mkdir()

    service = ImproveService(MagicMock(), MagicMock())
    result = service.load_baseline_params(empty_dir)
    assert result == {}


# ---------------------------------------------------------------------------
# test_prepare_sandbox
# ---------------------------------------------------------------------------
def test_prepare_sandbox(tmp_path):
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir(parents=True)
    (strategies_dir / "MyStrategy.py").write_text("# strategy", encoding="utf-8")

    service = _make_service(tmp_path)
    sandbox_dir = service.prepare_sandbox("MyStrategy", {"stoploss": -0.08})

    assert sandbox_dir.exists()
    assert (sandbox_dir / "MyStrategy.py").exists()
    assert (sandbox_dir / "MyStrategy.json").exists()
    assert json.loads((sandbox_dir / "MyStrategy.json").read_text()) == {"stoploss": -0.08}


def test_prepare_sandbox_missing_strategy(tmp_path):
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir(parents=True)
    # No .py file created

    service = _make_service(tmp_path)
    try:
        service.prepare_sandbox("MyStrategy", {"stoploss": -0.08})
        assert False, "Expected FileNotFoundError"
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# test_accept_candidate_atomic_write
# ---------------------------------------------------------------------------
def test_accept_candidate_atomic_write(tmp_path):
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir(parents=True)

    service = _make_service(tmp_path)
    service.accept_candidate("MyStrategy", {"stoploss": -0.08})

    final = strategies_dir / "MyStrategy.json"
    assert final.exists()
    assert json.loads(final.read_text()) == {"stoploss": -0.08}

    # .tmp file must have been cleaned up by os.replace
    tmp_file = strategies_dir / "MyStrategy.json.tmp"
    assert not tmp_file.exists()


# ---------------------------------------------------------------------------
# test_reject_candidate_cleanup
# ---------------------------------------------------------------------------
def test_reject_candidate_cleanup(tmp_path):
    sandbox_dir = tmp_path / "sandbox"
    sandbox_dir.mkdir()
    (sandbox_dir / "MyStrategy.py").write_text("# strategy", encoding="utf-8")
    (sandbox_dir / "MyStrategy.json").write_text("{}", encoding="utf-8")

    # A separate file that must NOT be touched
    main_param_file = tmp_path / "MyStrategy.json"
    main_param_file.write_text('{"stoploss": -0.10}', encoding="utf-8")

    service = ImproveService(MagicMock(), MagicMock())
    service.reject_candidate(sandbox_dir)

    assert not sandbox_dir.exists()
    assert main_param_file.exists()


# ---------------------------------------------------------------------------
# test_rollback
# ---------------------------------------------------------------------------
def test_rollback(tmp_path):
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir(parents=True)

    service = _make_service(tmp_path)
    service.rollback("MyStrategy", {"stoploss": -0.10})

    final = strategies_dir / "MyStrategy.json"
    assert final.exists()
    assert json.loads(final.read_text()) == {"stoploss": -0.10}
