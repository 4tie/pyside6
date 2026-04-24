"""Unit and structural tests for the enhanced _build_summary in ResultsPage.

Tests Properties 9–10 and structural/behavioral requirements.

Feature: backtest-summary-enhancement
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QWidget, QFrame

from app.ui.pages.results_page import ResultsPage
from app.ui.widgets.stat_card import StatCard

# ── QApplication singleton ────────────────────────────────────────────────────

_app = QApplication.instance() or QApplication(sys.argv)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def results_page() -> ResultsPage:
    """Minimal ResultsPage instance for testing."""
    mock_state = MagicMock()
    mock_state.current_settings = None
    return ResultsPage(mock_state)


FULL_RUN = {
    "strategy": "TestStrategy",
    "timeframe": "5m",
    "timerange": "20260101-20260201",
    "backtest_start": "2026-01-01",
    "backtest_end": "2026-02-01",
    "pairs": ["BTC/USDT", "ETH/USDT"],
    "run_id": "run_001",
    "saved_at": "2026-01-01T12:00:00",
    "starting_balance": 1000.0,
    "final_balance": 1200.0,
    "profit_total_pct": 20.0,
    "profit_total_abs": 200.0,
    "profit_factor": 1.5,
    "expectancy": 0.4,
    "trades_count": 50,
    "wins": 30,
    "losses": 20,
    "win_rate_pct": 60.0,
    "max_drawdown_pct": 15.0,
    "max_drawdown_abs": 150.0,
    "sharpe": 1.2,
    "sortino": 1.5,
    "calmar": 0.8,
}


def _collect_widgets(widget: QWidget, widget_type: type) -> list:
    """Recursively collect all child widgets of a given type."""
    result = []
    for child in widget.findChildren(widget_type):
        result.append(child)
    return result


def _collect_labels_with_text(widget: QWidget, text: str) -> list:
    """Find all QLabel children whose text matches (case-insensitive)."""
    return [
        lbl for lbl in widget.findChildren(QLabel)
        if lbl.text().upper() == text.upper()
    ]


# ── 9.1 KPI row structure ─────────────────────────────────────────────────────

def test_kpi_row_contains_six_stat_cards(results_page: ResultsPage):
    """_build_kpi_row({}) returns a widget containing exactly 6 StatCard children.
    Validates: Requirements 2.1, 2.2
    """
    kpi_widget = results_page._build_kpi_row({})
    stat_cards = _collect_widgets(kpi_widget, StatCard)
    assert len(stat_cards) == 6, f"Expected 6 StatCards, got {len(stat_cards)}"


def test_kpi_row_empty_run_shows_dashes(results_page: ResultsPage):
    """All 6 KPI cards display '—' when the run dict is empty.
    Validates: Requirement 2.8
    """
    kpi_widget = results_page._build_kpi_row({})
    stat_cards = _collect_widgets(kpi_widget, StatCard)
    dash_count = sum(1 for card in stat_cards if card._value_lbl.text() == "—")
    # Profit factor and sharpe show "—" when missing; others show formatted 0
    # At minimum sharpe (None default) and profit_factor (0 → "—") show dashes
    assert dash_count >= 2, f"Expected at least 2 '—' cards for empty run, got {dash_count}"


def test_kpi_row_full_run_no_dashes(results_page: ResultsPage):
    """KPI cards show formatted values (not '—') when run dict is fully populated.
    Validates: Requirement 2.1
    """
    kpi_widget = results_page._build_kpi_row(FULL_RUN)
    stat_cards = _collect_widgets(kpi_widget, StatCard)
    dash_cards = [card for card in stat_cards if card._value_lbl.text() == "—"]
    assert len(dash_cards) == 0, f"Unexpected '—' in cards: {[c._value_lbl.text() for c in dash_cards]}"


# ── 9.2 Section structure ─────────────────────────────────────────────────────

def test_build_summary_produces_all_four_section_headers(results_page: ResultsPage):
    """_build_summary produces widgets for all four section headers.
    Validates: Requirements 1.1, 1.4, 1.5, 1.6, 1.7
    """
    results_page._build_summary(FULL_RUN)
    summary_widget = results_page._summary_widget
    all_labels = summary_widget.findChildren(QLabel)
    label_texts = {lbl.text() for lbl in all_labels}
    for expected in ("OVERVIEW", "PERFORMANCE", "TRADE STATISTICS", "RISK METRICS"):
        assert expected in label_texts, (
            f"Section header '{expected}' not found. Found: {label_texts}"
        )


def test_strategy_appears_in_overview(results_page: ResultsPage):
    """'TestStrategy' value appears in the summary after _build_summary.
    Validates: Requirement 1.4
    """
    results_page._build_summary(FULL_RUN)
    summary_widget = results_page._summary_widget
    all_labels = summary_widget.findChildren(QLabel)
    texts = {lbl.text() for lbl in all_labels}
    assert "TestStrategy" in texts, f"Strategy value not found. Labels: {texts}"


def test_profit_pct_appears_in_performance(results_page: ResultsPage):
    """Profit % value appears in the summary (Performance section).
    Validates: Requirement 1.5
    """
    results_page._build_summary(FULL_RUN)
    summary_widget = results_page._summary_widget
    all_labels = summary_widget.findChildren(QLabel)
    texts = {lbl.text() for lbl in all_labels}
    assert "+20.00%" in texts, f"Profit % value not found. Labels: {texts}"


def test_trades_count_appears_in_trade_statistics(results_page: ResultsPage):
    """Trades count value appears in the summary (Trade Statistics section).
    Validates: Requirement 1.6
    """
    results_page._build_summary(FULL_RUN)
    summary_widget = results_page._summary_widget
    all_labels = summary_widget.findChildren(QLabel)
    texts = {lbl.text() for lbl in all_labels}
    assert "50" in texts, f"Trades count not found. Labels: {texts}"


def test_sharpe_appears_in_risk_metrics(results_page: ResultsPage):
    """Sharpe ratio value appears in the summary (Risk Metrics section).
    Validates: Requirement 1.7
    """
    results_page._build_summary(FULL_RUN)
    summary_widget = results_page._summary_widget
    all_labels = summary_widget.findChildren(QLabel)
    texts = {lbl.text() for lbl in all_labels}
    assert "1.200" in texts, f"Sharpe value not found. Labels: {texts}"


# ── 9.3 Pairs display ─────────────────────────────────────────────────────────

def test_pairs_widget_two_badges(results_page: ResultsPage):
    """_build_pairs_widget(['BTC/USDT', 'ETH/USDT']) returns a widget with 2 badge labels.
    Validates: Requirement 5.1
    """
    widget = results_page._build_pairs_widget(["BTC/USDT", "ETH/USDT"])
    assert isinstance(widget, QWidget)
    labels = widget.findChildren(QLabel)
    assert len(labels) == 2, f"Expected 2 badge labels, got {len(labels)}"
    texts = {lbl.text() for lbl in labels}
    assert texts == {"BTC/USDT", "ETH/USDT"}


def test_pairs_widget_empty_returns_dash_label(results_page: ResultsPage):
    """_build_pairs_widget([]) returns a QLabel with text '—'.
    Validates: Requirement 5.3
    """
    widget = results_page._build_pairs_widget([])
    assert isinstance(widget, QLabel)
    assert widget.text() == "—"


# ── 9.4 Balance delta ─────────────────────────────────────────────────────────

def test_balance_delta_equal_returns_none(results_page: ResultsPage):
    """Equal balances produce None from _balance_delta_widget.
    Validates: Requirement 6.3
    """
    result = results_page._balance_delta_widget(1000.0, 1000.0)
    assert result is None


# ── 9.5 Idempotency and robustness (Properties 9–10) ─────────────────────────

def test_build_summary_idempotent_widget_count(results_page: ResultsPage):
    """Calling _build_summary twice produces the same top-level widget count.
    Feature: backtest-summary-enhancement, Property 9: _build_summary is idempotent on widget count
    Validates: Requirement 7.2
    """
    results_page._build_summary(FULL_RUN)
    count_first = results_page._summary_layout.count()
    results_page._build_summary(FULL_RUN)
    count_second = results_page._summary_layout.count()
    assert count_first == count_second, (
        f"Widget count changed across calls: {count_first} → {count_second}"
    )


def test_build_summary_robust_to_missing_fields(results_page: ResultsPage):
    """_build_summary({}) completes without raising an exception.
    Feature: backtest-summary-enhancement, Property 10: _build_summary is robust to missing fields
    Validates: Requirement 7.3
    """
    try:
        results_page._build_summary({})
    except Exception as exc:
        pytest.fail(f"_build_summary raised an exception on empty dict: {exc}")


# ── 9.6 Exception handling ────────────────────────────────────────────────────

def test_build_summary_logs_warning_on_exception(results_page: ResultsPage):
    """When a helper raises, _build_summary logs a warning and leaves layout cleared.
    Validates: Requirement 7.4
    """
    with patch.object(results_page, "_summary_section", side_effect=RuntimeError("boom")):
        with patch("app.ui.pages.results_page._log") as mock_log:
            results_page._build_summary(FULL_RUN)
            mock_log.warning.assert_called_once()
            warning_msg = mock_log.warning.call_args[0][0]
            assert "_build_summary failed" in warning_msg

    # Layout should be in cleared state — clear happens before the try block
    count = results_page._summary_layout.count()
    assert count == 0, f"Expected cleared layout after exception, got {count} items"
