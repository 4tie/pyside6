"""
Preservation Property Tests — ImproveService and related services.

These tests capture EXISTING baseline behaviors that MUST be preserved after
the bug fix is applied. All tests MUST PASS on UNFIXED code.

Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
"""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.core.backtests.results_models import BacktestSummary
from app.core.models.improve_models import DiagnosedIssue
from app.core.services.improve_service import ImproveService
from app.core.services.results_diagnosis_service import ResultsDiagnosisService
from app.core.services.rule_suggestion_service import RuleSuggestionService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service(tmp_path: Path) -> ImproveService:
    """Build an ImproveService whose settings point at tmp_path."""
    mock_settings = MagicMock()
    mock_settings.user_data_path = str(tmp_path)
    mock_settings_service = MagicMock()
    mock_settings_service.load_settings.return_value = mock_settings
    return ImproveService(mock_settings_service, MagicMock())


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Flat params dict — arbitrary valid values
_flat_params_st = st.fixed_dictionaries({
    "stoploss": st.floats(
        min_value=-0.99, max_value=-0.01, allow_nan=False, allow_infinity=False
    ),
    "max_open_trades": st.integers(min_value=1, max_value=10),
    "minimal_roi": st.fixed_dictionaries({
        "0": st.floats(min_value=0.001, max_value=0.5, allow_nan=False, allow_infinity=False),
        "30": st.floats(min_value=0.001, max_value=0.3, allow_nan=False, allow_infinity=False),
        "60": st.floats(min_value=0.001, max_value=0.2, allow_nan=False, allow_infinity=False),
    }),
    "buy_params": st.just({}),
    "sell_params": st.just({}),
})

# BacktestSummary strategy — arbitrary valid instances
_float_st = st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False)
_int_st = st.integers(min_value=0, max_value=1000)
_str_st = st.text(min_size=1, max_size=20)
_pairlist_st = st.lists(st.text(min_size=1, max_size=10), min_size=0, max_size=10)
_opt_float_st = st.one_of(st.none(), _float_st)


def _summary_strategy():
    """Return a Hypothesis strategy that builds arbitrary BacktestSummary instances."""
    return st.builds(
        BacktestSummary,
        strategy=_str_st,
        timeframe=_str_st,
        total_trades=_int_st,
        wins=_int_st,
        losses=_int_st,
        draws=_int_st,
        win_rate=_float_st,
        avg_profit=_float_st,
        total_profit=_float_st,
        total_profit_abs=_float_st,
        sharpe_ratio=_opt_float_st,
        sortino_ratio=_opt_float_st,
        calmar_ratio=_opt_float_st,
        max_drawdown=_float_st,
        max_drawdown_abs=_float_st,
        trade_duration_avg=_int_st,
        starting_balance=_float_st,
        final_balance=_float_st,
        timerange=_str_st,
        pairlist=_pairlist_st,
        backtest_start=_str_st,
        backtest_end=_str_st,
        expectancy=_float_st,
        profit_factor=_float_st,
        max_consecutive_wins=_int_st,
        max_consecutive_losses=_int_st,
    )


# Issue list strategy — arbitrary subsets of the 6 existing issue IDs
_issues_st = st.lists(
    st.sampled_from([
        DiagnosedIssue("stoploss_too_wide", "desc"),
        DiagnosedIssue("trades_too_low", "desc"),
        DiagnosedIssue("weak_win_rate", "desc"),
        DiagnosedIssue("drawdown_high", "desc"),
        DiagnosedIssue("poor_pair_concentration", "desc"),
        DiagnosedIssue("negative_profit", "desc"),
    ]),
    min_size=1,
    unique_by=lambda i: i.issue_id,
)

# Params dict for suggestion tests
_params_st = st.fixed_dictionaries({
    "stoploss": st.floats(
        min_value=-0.99, max_value=-0.01, allow_nan=False, allow_infinity=False
    ),
    "max_open_trades": st.integers(min_value=1, max_value=10),
    "minimal_roi": st.fixed_dictionaries({
        "0": st.floats(min_value=0.001, max_value=0.5, allow_nan=False, allow_infinity=False),
        "30": st.floats(min_value=0.001, max_value=0.3, allow_nan=False, allow_infinity=False),
        "60": st.floats(min_value=0.001, max_value=0.2, allow_nan=False, allow_infinity=False),
    }),
    "buy_params": st.just({}),
    "sell_params": st.just({}),
})


# ===========================================================================
# Test 1 — load_baseline_params primary path (params.json exists)
# Validates: Requirements 3.4
# ===========================================================================

@given(params=_flat_params_st)
@settings(max_examples=100)
def test_load_baseline_params_round_trip(params):
    """**Validates: Requirements 3.4**

    For any valid params dict written to params.json,
    load_baseline_params(run_dir) returns the exact same dict
    (JSON round-trip equality).

    This MUST PASS on unfixed code — the primary path is not broken.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        run_dir = Path(tmpdir) / "run_dir"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "params.json").write_text(json.dumps(params), encoding="utf-8")

        service = ImproveService(MagicMock(), MagicMock())
        loaded = service.load_baseline_params(run_dir)

        # JSON round-trip normalises floats the same way
        expected = json.loads(json.dumps(params))
        assert loaded == expected, (
            f"load_baseline_params returned {loaded!r}, expected {expected!r}"
        )


# ===========================================================================
# Test 2 — prepare_sandbox creates timestamped directory and copies .py file
# Validates: Requirements 3.1
# ===========================================================================

def test_prepare_sandbox_creates_directory_and_copies_files(tmp_path):
    """**Validates: Requirements 3.1**

    Call prepare_sandbox("MultiMeee", {"stoploss": -0.10}), assert:
    - The returned sandbox_dir exists
    - sandbox_dir / "MultiMeee.py" exists (copied from strategies dir)
    - sandbox_dir / "MultiMeee.json" exists (written)
    - The sandbox_dir is under {user_data_path}/strategies/_improve_sandbox/

    This MUST PASS on unfixed code — sandbox creation is not broken.
    """
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir(parents=True, exist_ok=True)
    (strategies_dir / "MultiMeee.py").write_text("# strategy", encoding="utf-8")

    service = _make_service(tmp_path)
    sandbox_dir = service.prepare_sandbox("MultiMeee", {"stoploss": -0.10})

    # Directory must exist
    assert sandbox_dir.exists(), f"sandbox_dir does not exist: {sandbox_dir}"

    # .py file must be copied
    assert (sandbox_dir / "MultiMeee.py").exists(), (
        f"MultiMeee.py not found in sandbox_dir: {sandbox_dir}"
    )

    # .json file must be written
    assert (sandbox_dir / "MultiMeee.json").exists(), (
        f"MultiMeee.json not found in sandbox_dir: {sandbox_dir}"
    )

    # sandbox_dir must be under {user_data_path}/strategies/_improve_sandbox/
    expected_parent = tmp_path / "strategies" / "_improve_sandbox"
    assert sandbox_dir.parent == expected_parent, (
        f"sandbox_dir parent is {sandbox_dir.parent!r}, "
        f"expected {expected_parent!r}"
    )


# ===========================================================================
# Test 3 — accept_candidate uses atomic write pattern
# Validates: Requirements 3.2
# ===========================================================================

def test_accept_candidate_atomic_write_pattern(tmp_path):
    """**Validates: Requirements 3.2**

    Call accept_candidate("MultiMeee", {"stoploss": -0.10}), assert:
    - The final file {strategies_dir}/MultiMeee.json exists
    - The .tmp file {strategies_dir}/MultiMeee.json.tmp does NOT exist
      (cleaned up by os.replace)

    This MUST PASS on unfixed code — atomic write pattern is not broken.
    """
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir(parents=True, exist_ok=True)

    service = _make_service(tmp_path)
    service.accept_candidate("MultiMeee", {"stoploss": -0.10})

    final_path = strategies_dir / "MultiMeee.json"
    tmp_file_path = strategies_dir / "MultiMeee.json.tmp"

    assert final_path.exists(), (
        f"Final file {final_path} does not exist after accept_candidate"
    )
    assert not tmp_file_path.exists(), (
        f".tmp file {tmp_file_path} still exists — atomic write pattern broken"
    )


# ===========================================================================
# Test 4 — rollback uses atomic write pattern
# Validates: Requirements 3.3
# ===========================================================================

def test_rollback_atomic_write_pattern(tmp_path):
    """**Validates: Requirements 3.3**

    Call rollback("MultiMeee", {"stoploss": -0.10}), assert:
    - The final file {strategies_dir}/MultiMeee.json exists
    - The .tmp file does NOT exist (cleaned up by os.replace)

    This MUST PASS on unfixed code — atomic write pattern is not broken.
    """
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir(parents=True, exist_ok=True)

    service = _make_service(tmp_path)
    service.rollback("MultiMeee", {"stoploss": -0.10})

    final_path = strategies_dir / "MultiMeee.json"
    tmp_file_path = strategies_dir / "MultiMeee.json.tmp"

    assert final_path.exists(), (
        f"Final file {final_path} does not exist after rollback"
    )
    assert not tmp_file_path.exists(), (
        f".tmp file {tmp_file_path} still exists — atomic write pattern broken"
    )


# ===========================================================================
# Test 5 — Existing diagnosis rules unchanged (PBT)
# Validates: Requirements 3.5
# ===========================================================================

@given(summary=_summary_strategy())
@settings(max_examples=200)
def test_existing_diagnosis_rules_unchanged(summary: BacktestSummary):
    """**Validates: Requirements 3.5**

    For any BacktestSummary, all 6 existing rules fire correctly:
    - stoploss_too_wide fires iff max_drawdown > 20.0
    - trades_too_low fires iff total_trades < 30
    - weak_win_rate fires iff win_rate < 45.0
    - drawdown_high fires iff max_drawdown > 30.0
    - poor_pair_concentration fires iff len(pairlist) < 3
    - negative_profit fires iff total_profit < 0.0

    This MUST PASS on unfixed code — diagnosis rules are not broken.
    """
    issues = ResultsDiagnosisService.diagnose(
        __import__("app.core.models.diagnosis_models", fromlist=["DiagnosisInput"]).DiagnosisInput(in_sample=summary)
    ).issues
    issue_ids = {issue.issue_id for issue in issues}

    # stoploss_too_wide: max_drawdown > 20.0
    if summary.max_drawdown > 20.0:
        assert "stoploss_too_wide" in issue_ids, (
            f"Expected 'stoploss_too_wide' when max_drawdown={summary.max_drawdown}"
        )
    else:
        assert "stoploss_too_wide" not in issue_ids, (
            f"Unexpected 'stoploss_too_wide' when max_drawdown={summary.max_drawdown}"
        )

    # trades_too_low: total_trades < 30
    if summary.total_trades < 30:
        assert "trades_too_low" in issue_ids, (
            f"Expected 'trades_too_low' when total_trades={summary.total_trades}"
        )
    else:
        assert "trades_too_low" not in issue_ids, (
            f"Unexpected 'trades_too_low' when total_trades={summary.total_trades}"
        )

    # weak_win_rate: win_rate < 45.0
    if summary.win_rate < 45.0:
        assert "weak_win_rate" in issue_ids, (
            f"Expected 'weak_win_rate' when win_rate={summary.win_rate}"
        )
    else:
        assert "weak_win_rate" not in issue_ids, (
            f"Unexpected 'weak_win_rate' when win_rate={summary.win_rate}"
        )

    # drawdown_high: max_drawdown > 30.0
    if summary.max_drawdown > 30.0:
        assert "drawdown_high" in issue_ids, (
            f"Expected 'drawdown_high' when max_drawdown={summary.max_drawdown}"
        )
    else:
        assert "drawdown_high" not in issue_ids, (
            f"Unexpected 'drawdown_high' when max_drawdown={summary.max_drawdown}"
        )

    # poor_pair_concentration: len(pairlist) < 3
    if len(summary.pairlist) < 3:
        assert "poor_pair_concentration" in issue_ids, (
            f"Expected 'poor_pair_concentration' when len(pairlist)={len(summary.pairlist)}"
        )
    else:
        assert "poor_pair_concentration" not in issue_ids, (
            f"Unexpected 'poor_pair_concentration' when len(pairlist)={len(summary.pairlist)}"
        )

    # negative_profit: total_profit < 0.0
    if summary.total_profit < 0.0:
        assert "negative_profit" in issue_ids, (
            f"Expected 'negative_profit' when total_profit={summary.total_profit}"
        )
    else:
        assert "negative_profit" not in issue_ids, (
            f"Unexpected 'negative_profit' when total_profit={summary.total_profit}"
        )


# ===========================================================================
# Test 6 — Existing suggestion handlers unchanged (PBT)
# Validates: Requirements 3.6
# ===========================================================================

@given(params=_params_st, issues=_issues_st)
@settings(max_examples=200)
def test_existing_suggestion_handlers_unchanged(params, issues):
    """**Validates: Requirements 3.6**

    For any of the 6 existing issue_id values, suggest() returns a
    ParameterSuggestion with the correct parameter, proposed_value formula,
    and is_advisory flag.

    This MUST PASS on unfixed code — suggestion handlers are not broken.
    """
    suggestions = RuleSuggestionService.suggest(issues, params)

    # Build mapping by calling handlers directly for each issue
    # (suggest() filters out None values, so we can't rely on zip)
    suggestion_by_issue: dict = {}
    for issue in issues:
        suggestion = RuleSuggestionService._handle_issue(issue, params)
        if suggestion is not None:
            suggestion_by_issue[issue.issue_id] = suggestion

    issue_id_set = {issue.issue_id for issue in issues}

    # stoploss_too_wide: proposed_stoploss == round(stoploss + 0.02, 10)
    if "stoploss_too_wide" in issue_id_set and "stoploss_too_wide" in suggestion_by_issue:
        s = suggestion_by_issue["stoploss_too_wide"]
        assert s.parameter == "stoploss", (
            f"stoploss_too_wide: expected parameter='stoploss', got {s.parameter!r}"
        )
        expected = round(params["stoploss"] + 0.02, 10)
        assert s.proposed_value == expected, (
            f"stoploss_too_wide: expected proposed_value={expected}, got {s.proposed_value}"
        )
        assert s.is_advisory is False, (
            f"stoploss_too_wide: expected is_advisory=False, got {s.is_advisory}"
        )

    # trades_too_low: proposed_max_open_trades == min(max_open_trades + 1, 10)
    if "trades_too_low" in issue_id_set and "trades_too_low" in suggestion_by_issue:
        s = suggestion_by_issue["trades_too_low"]
        assert s.parameter == "max_open_trades", (
            f"trades_too_low: expected parameter='max_open_trades', got {s.parameter!r}"
        )
        expected = min(params["max_open_trades"] + 1, 10)
        assert s.proposed_value == expected, (
            f"trades_too_low: expected proposed_value={expected}, got {s.proposed_value}"
        )
        assert s.is_advisory is False, (
            f"trades_too_low: expected is_advisory=False, got {s.is_advisory}"
        )

    # weak_win_rate: proposed minimal_roi at smallest int key == round(original - 0.005, 10)
    if "weak_win_rate" in issue_id_set and "weak_win_rate" in suggestion_by_issue:
        s = suggestion_by_issue["weak_win_rate"]
        assert s.parameter == "minimal_roi", (
            f"weak_win_rate: expected parameter='minimal_roi', got {s.parameter!r}"
        )
        minimal_roi = params["minimal_roi"]
        smallest_key = min(minimal_roi.keys(), key=lambda k: int(k))
        original_val = minimal_roi[smallest_key]
        expected_val = round(original_val - 0.005, 10)
        assert isinstance(s.proposed_value, dict), (
            f"weak_win_rate: proposed_value should be a dict, got {type(s.proposed_value)}"
        )
        assert s.proposed_value[smallest_key] == expected_val, (
            f"weak_win_rate: expected roi[{smallest_key}]={expected_val}, "
            f"got {s.proposed_value[smallest_key]}"
        )
        assert s.is_advisory is False, (
            f"weak_win_rate: expected is_advisory=False, got {s.is_advisory}"
        )

    # drawdown_high: proposed_max_open_trades == max(max_open_trades - 1, 1)
    if "drawdown_high" in issue_id_set and "drawdown_high" in suggestion_by_issue:
        s = suggestion_by_issue["drawdown_high"]
        assert s.parameter == "max_open_trades", (
            f"drawdown_high: expected parameter='max_open_trades', got {s.parameter!r}"
        )
        expected = max(params["max_open_trades"] - 1, 1)
        assert s.proposed_value == expected, (
            f"drawdown_high: expected proposed_value={expected}, got {s.proposed_value}"
        )
        assert s.is_advisory is False, (
            f"drawdown_high: expected is_advisory=False, got {s.is_advisory}"
        )

    # poor_pair_concentration: is_advisory=True, proposed_value=None
    # NOTE: This handler always returns None, so we expect NO suggestion
    if "poor_pair_concentration" in issue_id_set:
        assert "poor_pair_concentration" not in suggestion_by_issue, (
            "poor_pair_concentration should not generate a suggestion (handler returns None)"
        )

    # negative_profit: proposed_stoploss == round(stoploss + 0.03, 10)
    if "negative_profit" in issue_id_set and "negative_profit" in suggestion_by_issue:
        s = suggestion_by_issue["negative_profit"]
        assert s.parameter == "stoploss", (
            f"negative_profit: expected parameter='stoploss', got {s.parameter!r}"
        )
        expected = round(params["stoploss"] + 0.03, 10)
        assert s.proposed_value == expected, (
            f"negative_profit: expected proposed_value={expected}, got {s.proposed_value}"
        )
        assert s.is_advisory is False, (
            f"negative_profit: expected is_advisory=False, got {s.is_advisory}"
        )
