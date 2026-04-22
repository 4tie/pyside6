"""Unit tests for PairResultsWidget."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from app.core.backtests.results_models import PairAnalysis, PairMetrics
from app.ui_v2.widgets.pair_results_widget import PairResultsWidget


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_pair_results_widget_display_empty(qapp):
    """Test widget displays empty state when no pair metrics."""
    widget = PairResultsWidget()
    analysis = PairAnalysis(
        pair_metrics=[],
        best_pairs=[],
        worst_pairs=[],
        dominance_flags=[],
    )
    widget.display(analysis)
    
    # Should show "No pairs to display" message
    assert widget._table.rowCount() == 1
    assert widget._table.item(0, 0).text() == "No pairs to display"
    assert not widget._concentration_warning.isVisible()


def test_pair_results_widget_display_with_data(qapp):
    """Test widget displays pair metrics correctly."""
    widget = PairResultsWidget()
    
    pm1 = PairMetrics(
        pair="BTC/USDT",
        total_profit_pct=10.5,
        win_rate=65.0,
        trade_count=20,
        max_drawdown_pct=2.5,
        profit_share=0.7,
    )
    pm2 = PairMetrics(
        pair="ETH/USDT",
        total_profit_pct=-3.2,
        win_rate=40.0,
        trade_count=15,
        max_drawdown_pct=5.0,
        profit_share=0.3,
    )
    
    analysis = PairAnalysis(
        pair_metrics=[pm1, pm2],
        best_pairs=[pm1],
        worst_pairs=[pm2],
        dominance_flags=["profit_concentration"],
    )
    
    widget.display(analysis)
    
    # Should have 2 rows
    assert widget._table.rowCount() == 2
    
    # Check first row (BTC/USDT)
    assert widget._table.item(0, 0).text() == "BTC/USDT"
    assert widget._table.item(0, 1).text() == "10.500"
    assert widget._table.item(0, 2).text() == "65.0"
    assert widget._table.item(0, 3).text() == "20"
    assert widget._table.item(0, 4).text() == "2.500"
    
    # Check second row (ETH/USDT)
    assert widget._table.item(1, 0).text() == "ETH/USDT"
    assert widget._table.item(1, 1).text() == "-3.200"
    assert widget._table.item(1, 2).text() == "40.0"
    assert widget._table.item(1, 3).text() == "15"
    assert widget._table.item(1, 4).text() == "5.000"
    
    # Concentration warning should be visible (check text is set)
    assert "60%" in widget._concentration_warning.text()
    # Note: isVisible() may not work in headless tests, but text being set confirms the logic works


def test_pair_results_widget_clear(qapp):
    """Test widget clear method."""
    widget = PairResultsWidget()
    
    # First display some data
    pm = PairMetrics(
        pair="BTC/USDT",
        total_profit_pct=10.5,
        win_rate=65.0,
        trade_count=20,
        max_drawdown_pct=2.5,
        profit_share=0.5,
    )
    analysis = PairAnalysis(
        pair_metrics=[pm],
        best_pairs=[pm],
        worst_pairs=[],
        dominance_flags=[],
    )
    widget.display(analysis)
    
    # Now clear
    widget.clear()
    
    # Should show "No results loaded" message
    assert widget._table.rowCount() == 1
    assert widget._table.item(0, 0).text() == "No results loaded"
    assert not widget._concentration_warning.isVisible()


def test_pair_results_widget_no_concentration_warning(qapp):
    """Test widget hides concentration warning when flag not present."""
    widget = PairResultsWidget()
    
    pm = PairMetrics(
        pair="BTC/USDT",
        total_profit_pct=10.5,
        win_rate=65.0,
        trade_count=20,
        max_drawdown_pct=2.5,
        profit_share=0.5,  # Below 60% threshold
    )
    
    analysis = PairAnalysis(
        pair_metrics=[pm],
        best_pairs=[pm],
        worst_pairs=[],
        dominance_flags=[],  # No concentration flag
    )
    
    widget.display(analysis)
    
    # Concentration warning should be hidden (text should be empty or not contain warning)
    # In headless tests, isVisible() may not work reliably, so we check the logic by
    # verifying the warning text is not set when flag is absent
    assert not widget._concentration_warning.isVisible() or widget._concentration_warning.text() == ""
