"""
Bug Condition Exploration Test — ImproveService flat-format write bug.

THIS TEST IS DESIGNED TO FAIL ON UNFIXED CODE.
Failure confirms the bug exists. Do NOT fix the code to make this pass.

Bug summary
-----------
`prepare_sandbox`, `accept_candidate`, and `rollback` all call
``json.dumps(candidate_config, indent=2)`` directly on the flat params dict,
producing a file that freqtrade rejects with
``ERROR - Invalid parameter file provided.``

The flat format written by the buggy code looks like::

    {"stoploss": -0.245, "minimal_roi": {"0": 0.109}, "buy_params": {}, "sell_params": {}}

The freqtrade nested format that freqtrade actually expects looks like::

    {
      "strategy_name": "MultiMeee",
      "params": {
        "stoploss": {"stoploss": -0.245},
        "roi": {"0": 0.109},
        "buy": {},
        "sell": {}
      },
      "ft_stratparam_v": 1,
      "export_time": "..."
    }

Additionally, ``load_baseline_params`` has no ``strategy_name`` parameter and
no fallback when ``params.json`` is missing — it simply returns ``{}``.

Validates: Requirements 1.1, 1.2, 1.3, 1.6
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.core.services.improve_service import ImproveService

# ---------------------------------------------------------------------------
# Hypothesis strategy — arbitrary flat params dicts
# ---------------------------------------------------------------------------
_flat_params_st = st.fixed_dictionaries(
    {
        "stoploss": st.floats(
            min_value=-0.99, max_value=-0.01, allow_nan=False, allow_infinity=False
        ),
        "max_open_trades": st.integers(min_value=1, max_value=10),
        "minimal_roi": st.fixed_dictionaries(
            {"0": st.floats(min_value=0.001, max_value=0.5, allow_nan=False, allow_infinity=False)}
        ),
        "buy_params": st.one_of(
            st.just({}),
            st.fixed_dictionaries(
                {"buy_rsi": st.integers(min_value=10, max_value=40)}
            ),
        ),
        "sell_params": st.one_of(
            st.just({}),
            st.fixed_dictionaries(
                {"sell_rsi": st.integers(min_value=60, max_value=90)}
            ),
        ),
    }
)


# ---------------------------------------------------------------------------
# Helper — build a service whose settings point at tmp_path
# ---------------------------------------------------------------------------
def _make_service(tmp_path: Path) -> ImproveService:
    mock_settings = MagicMock()
    mock_settings.user_data_path = str(tmp_path)
    mock_settings_service = MagicMock()
    mock_settings_service.load_settings.return_value = mock_settings
    return ImproveService(mock_settings_service, MagicMock())


# ---------------------------------------------------------------------------
# Test A — prepare_sandbox writes flat format (BUG: should write nested)
# Validates: Requirements 1.1
# ---------------------------------------------------------------------------
@given(flat_params=_flat_params_st)
@settings(max_examples=25)
def test_prepare_sandbox_writes_nested_format(flat_params):
    """**Validates: Requirements 1.1**

    For any flat params dict, ``prepare_sandbox`` MUST write a JSON file that
    contains ``"strategy_name"`` at the top level.

    On UNFIXED code this test FAILS because the written file is the raw flat
    dict (no ``strategy_name`` key).

    Counterexample documented:
        flat_params = {"stoploss": -0.01, "max_open_trades": 1,
                       "minimal_roi": {"0": 0.001}, "buy_params": {}, "sell_params": {}}
        written file = {"stoploss": -0.01, "max_open_trades": 1, ...}
        assertion "strategy_name" in result  →  FAILS
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        strategies_dir = tmp_path / "strategies"
        strategies_dir.mkdir(parents=True, exist_ok=True)
        (strategies_dir / "MultiMeee.py").write_text("# strategy", encoding="utf-8")

        service = _make_service(tmp_path)
        sandbox_dir = service.prepare_sandbox("MultiMeee", flat_params)

        written = json.loads((sandbox_dir / "MultiMeee.json").read_text(encoding="utf-8"))

        # BUG: on unfixed code this assertion fails — the file is the flat dict
        assert "strategy_name" in written, (
            f"prepare_sandbox wrote flat format instead of nested freqtrade format.\n"
            f"Written file: {written}\n"
            f"Expected key 'strategy_name' to be present."
        )


# ---------------------------------------------------------------------------
# Test B — accept_candidate writes flat format (BUG: should write nested)
# Validates: Requirements 1.2
# ---------------------------------------------------------------------------
@given(flat_params=_flat_params_st)
@settings(max_examples=25)
def test_accept_candidate_writes_nested_format(flat_params):
    """**Validates: Requirements 1.2**

    For any flat params dict, ``accept_candidate`` MUST write a JSON file
    where ``result["params"]["stoploss"]["stoploss"] == flat_params["stoploss"]``.

    On UNFIXED code this test FAILS because the written file is the raw flat
    dict — there is no ``params`` sub-object.

    Counterexample documented:
        flat_params = {"stoploss": -0.245, ...}
        written file = {"stoploss": -0.245, ...}   (flat, no "params" key)
        result["params"]["stoploss"]["stoploss"]  →  KeyError / FAILS
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        strategies_dir = tmp_path / "strategies"
        strategies_dir.mkdir(parents=True, exist_ok=True)

        service = _make_service(tmp_path)
        service.accept_candidate("MultiMeee", flat_params)

        written = json.loads(
            (strategies_dir / "MultiMeee.json").read_text(encoding="utf-8")
        )

        # BUG: on unfixed code "params" key is absent — KeyError raised
        assert "params" in written, (
            f"accept_candidate wrote flat format instead of nested freqtrade format.\n"
            f"Written file: {written}"
        )
        assert written["params"]["stoploss"]["stoploss"] == flat_params["stoploss"], (
            f"Nested stoploss mismatch.\n"
            f"Expected: {flat_params['stoploss']}\n"
            f"Got: {written['params'].get('stoploss')}"
        )


# ---------------------------------------------------------------------------
# Test C — rollback writes flat format (BUG: should write nested)
# Validates: Requirements 1.3
# ---------------------------------------------------------------------------
@given(flat_params=_flat_params_st)
@settings(max_examples=25)
def test_rollback_writes_nested_format(flat_params):
    """**Validates: Requirements 1.3**

    For any flat params dict, ``rollback`` MUST write a JSON file that
    contains ``"ft_stratparam_v"`` at the top level.

    On UNFIXED code this test FAILS because the written file is the raw flat
    dict (no ``ft_stratparam_v`` key).

    Counterexample documented:
        flat_params = {"stoploss": -0.5, ...}
        written file = {"stoploss": -0.5, ...}   (flat, no "ft_stratparam_v")
        assertion "ft_stratparam_v" in result  →  FAILS
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        strategies_dir = tmp_path / "strategies"
        strategies_dir.mkdir(parents=True, exist_ok=True)

        service = _make_service(tmp_path)
        service.rollback("MultiMeee", flat_params)

        written = json.loads(
            (strategies_dir / "MultiMeee.json").read_text(encoding="utf-8")
        )

        # BUG: on unfixed code this assertion fails — the file is the flat dict
        assert "ft_stratparam_v" in written, (
            f"rollback wrote flat format instead of nested freqtrade format.\n"
            f"Written file: {written}\n"
            f"Expected key 'ft_stratparam_v' to be present."
        )


# ---------------------------------------------------------------------------
# Unit test — load_baseline_params has no strategy_name fallback (BUG)
# Validates: Requirements 1.6
# ---------------------------------------------------------------------------
def test_load_baseline_params_fallback_when_params_json_missing(tmp_path):
    """**Validates: Requirements 1.6**

    When ``params.json`` is absent AND a ``strategy_name`` is provided,
    ``load_baseline_params`` MUST fall back to reading the live strategy JSON
    and return a non-empty flat params dict.

    On UNFIXED code this test FAILS in one of two ways:
      - TypeError: ``load_baseline_params()`` only accepts one argument
        (``run_dir``), so passing ``strategy_name`` raises TypeError.
      - Returns ``{}``: the method has no fallback and returns empty dict.

    Either outcome confirms the bug (no fallback exists).

    Counterexample documented:
        run_dir has no params.json
        live strategy JSON exists at strategies/MultiMeee.json with valid params
        load_baseline_params(run_dir, "MultiMeee")
          → TypeError (wrong number of args)  OR  returns {}
        assertion result is non-empty  →  FAILS
    """
    # Create a run_dir WITHOUT params.json
    run_dir = tmp_path / "run_20260101_120000_abc123"
    run_dir.mkdir(parents=True)

    # Create the live strategy JSON with valid nested freqtrade params
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir(parents=True, exist_ok=True)
    live_strategy_json = {
        "strategy_name": "MultiMeee",
        "params": {
            "stoploss": {"stoploss": -0.10},
            "max_open_trades": {"max_open_trades": 3},
            "roi": {"0": 0.05},
            "buy": {"buy_rsi": 30},
            "sell": {"sell_rsi": 70},
        },
        "ft_stratparam_v": 1,
        "export_time": "2026-01-01T00:00:00+00:00",
    }
    (strategies_dir / "MultiMeee.json").write_text(
        json.dumps(live_strategy_json), encoding="utf-8"
    )

    service = _make_service(tmp_path)

    # BUG: on unfixed code this raises TypeError (unexpected keyword argument)
    # OR returns {} (no fallback implemented)
    try:
        result = service.load_baseline_params(run_dir, "MultiMeee")
    except TypeError as exc:
        pytest.fail(
            f"load_baseline_params does not accept strategy_name parameter — "
            f"no fallback exists (TypeError: {exc})"
        )

    # If no TypeError, the result must be non-empty (fallback must have worked)
    assert result, (
        "load_baseline_params returned empty dict when params.json is missing "
        "and a live strategy JSON exists — no fallback implemented."
    )
