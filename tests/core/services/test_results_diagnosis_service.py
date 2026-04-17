"""
Property-based tests for ResultsDiagnosisService.

Property 1: Diagnosis threshold rules are exhaustive and correct
Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.backtests.results_models import BacktestSummary
from app.core.services.results_diagnosis_service import ResultsDiagnosisService

# ---------------------------------------------------------------------------
# Shared field strategies
# ---------------------------------------------------------------------------
_float_st = st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False)
_int_st = st.integers(min_value=0, max_value=1000)
_str_st = st.text(min_size=1, max_size=20)
_pairlist_st = st.lists(st.text(min_size=1, max_size=10), min_size=0, max_size=10)
_opt_float_st = st.one_of(st.none(), _float_st)


def _summary_strategy():
    """Return a hypothesis strategy that builds arbitrary BacktestSummary instances."""
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


# ---------------------------------------------------------------------------
# Property 1 — Diagnosis threshold rules are exhaustive and correct
# Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
# ---------------------------------------------------------------------------
@given(summary=_summary_strategy())
@settings(max_examples=200)
def test_diagnosis_threshold_rules_exhaustive_and_correct(summary: BacktestSummary):
    """**Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7**

    For every possible BacktestSummary, each issue ID must be present in the
    diagnosis result if and only if its corresponding threshold condition holds.
    """
    issues = ResultsDiagnosisService.diagnose(summary)
    issue_ids = {issue.issue_id for issue in issues}

    # Req 4.1 / 4.2 — stoploss_too_wide: max_drawdown > 20.0
    if summary.max_drawdown > 20.0:
        assert "stoploss_too_wide" in issue_ids, (
            f"Expected 'stoploss_too_wide' when max_drawdown={summary.max_drawdown}"
        )
    else:
        assert "stoploss_too_wide" not in issue_ids, (
            f"Unexpected 'stoploss_too_wide' when max_drawdown={summary.max_drawdown}"
        )

    # Req 4.3 — trades_too_low: total_trades < 30
    if summary.total_trades < 30:
        assert "trades_too_low" in issue_ids, (
            f"Expected 'trades_too_low' when total_trades={summary.total_trades}"
        )
    else:
        assert "trades_too_low" not in issue_ids, (
            f"Unexpected 'trades_too_low' when total_trades={summary.total_trades}"
        )

    # Req 4.4 — weak_win_rate: win_rate < 45.0
    if summary.win_rate < 45.0:
        assert "weak_win_rate" in issue_ids, (
            f"Expected 'weak_win_rate' when win_rate={summary.win_rate}"
        )
    else:
        assert "weak_win_rate" not in issue_ids, (
            f"Unexpected 'weak_win_rate' when win_rate={summary.win_rate}"
        )

    # Req 4.5 — drawdown_high: max_drawdown > 30.0
    if summary.max_drawdown > 30.0:
        assert "drawdown_high" in issue_ids, (
            f"Expected 'drawdown_high' when max_drawdown={summary.max_drawdown}"
        )
    else:
        assert "drawdown_high" not in issue_ids, (
            f"Unexpected 'drawdown_high' when max_drawdown={summary.max_drawdown}"
        )

    # Req 4.6 — poor_pair_concentration: len(pairlist) < 3
    if len(summary.pairlist) < 3:
        assert "poor_pair_concentration" in issue_ids, (
            f"Expected 'poor_pair_concentration' when len(pairlist)={len(summary.pairlist)}"
        )
    else:
        assert "poor_pair_concentration" not in issue_ids, (
            f"Unexpected 'poor_pair_concentration' when len(pairlist)={len(summary.pairlist)}"
        )

    # Req 4.7 — negative_profit: total_profit < 0.0
    if summary.total_profit < 0.0:
        assert "negative_profit" in issue_ids, (
            f"Expected 'negative_profit' when total_profit={summary.total_profit}"
        )
    else:
        assert "negative_profit" not in issue_ids, (
            f"Unexpected 'negative_profit' when total_profit={summary.total_profit}"
        )
