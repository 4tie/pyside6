"""Unit tests for CompareWidget."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from app.core.backtests.results_models import RunComparison
from app.ui_v2.widgets.compare_widget import CompareWidget


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_compare_widget_initialization(qapp):
    """Test widget initializes correctly."""
    widget = CompareWidget()
    
    # Check that selectors and button exist
    assert widget._combo_run_a is not None
    assert widget._combo_run_b is not None
    assert widget._btn_compare is not None
    
    # Prompt should have text set initially
    assert len(widget._prompt_label.text()) > 0
    
    # Results widget exists
    assert widget._results_widget is not None


def test_compare_widget_set_run_choices_empty(qapp):
    """Test widget handles empty run list."""
    widget = CompareWidget()
    widget.set_run_choices([])
    
    # Combos should be empty
    assert widget._combo_run_a.count() == 0
    assert widget._combo_run_b.count() == 0
    
    # Prompt should indicate no runs available
    assert "No runs available" in widget._prompt_label.text()
    
    # Compare button should be disabled
    assert not widget._btn_compare.isEnabled()


def test_compare_widget_set_run_choices_single_run(qapp):
    """Test widget handles single run (insufficient for comparison)."""
    widget = CompareWidget()
    runs = [{"id": "run_1", "timestamp": "2024-01-01"}]
    widget.set_run_choices(runs)
    
    # Combos should have 1 item each
    assert widget._combo_run_a.count() == 1
    assert widget._combo_run_b.count() == 1
    
    # Prompt should indicate need for 2 runs
    assert "at least 2 runs" in widget._prompt_label.text()
    
    # Compare button should be disabled
    assert not widget._btn_compare.isEnabled()


def test_compare_widget_set_run_choices_multiple_runs(qapp):
    """Test widget handles multiple runs correctly."""
    widget = CompareWidget()
    runs = [
        {"id": "run_1", "timestamp": "2024-01-01"},
        {"id": "run_2", "timestamp": "2024-01-02"},
        {"id": "run_3", "timestamp": "2024-01-03"},
    ]
    widget.set_run_choices(runs)
    
    # Combos should have 3 items each
    assert widget._combo_run_a.count() == 3
    assert widget._combo_run_b.count() == 3
    
    # Second combo should pre-select second run
    assert widget._combo_run_b.currentIndex() == 1
    
    # Compare button should be enabled
    assert widget._btn_compare.isEnabled()
    
    # Prompt should have text (until comparison is shown)
    assert len(widget._prompt_label.text()) > 0


def test_compare_widget_display_improved(qapp):
    """Test widget displays improved verdict correctly."""
    widget = CompareWidget()
    
    comparison = RunComparison(
        profit_diff=5.5,
        winrate_diff=3.2,
        drawdown_diff=-1.5,
        verdict="improved",
    )
    
    widget.display(comparison)
    
    # Check labels have been updated with values
    assert len(widget._label_profit_diff.text()) > 0
    assert len(widget._label_winrate_diff.text()) > 0
    assert len(widget._label_drawdown_diff.text()) > 0
    assert len(widget._label_verdict.text()) > 0
    
    # Check profit diff (positive = green)
    assert "+5.500" in widget._label_profit_diff.text()
    assert "#4ec9a0" in widget._label_profit_diff.styleSheet()  # green
    
    # Check winrate diff (positive = green)
    assert "+3.2" in widget._label_winrate_diff.text()
    assert "#4ec9a0" in widget._label_winrate_diff.styleSheet()  # green
    
    # Check drawdown diff (negative = green, improvement)
    assert "-1.5" in widget._label_drawdown_diff.text()
    assert "#4ec9a0" in widget._label_drawdown_diff.styleSheet()  # green
    
    # Check verdict (improved = green)
    assert "IMPROVED" in widget._label_verdict.text()
    assert "#4ec9a0" in widget._label_verdict.styleSheet()  # green


def test_compare_widget_display_degraded(qapp):
    """Test widget displays degraded verdict correctly."""
    widget = CompareWidget()
    
    comparison = RunComparison(
        profit_diff=-3.2,
        winrate_diff=-5.0,
        drawdown_diff=8.5,
        verdict="degraded",
    )
    
    widget.display(comparison)
    
    # Check labels have been updated
    assert len(widget._label_profit_diff.text()) > 0
    assert len(widget._label_verdict.text()) > 0
    
    # Check profit diff (negative = red)
    assert "-3.200" in widget._label_profit_diff.text()
    assert "#f44747" in widget._label_profit_diff.styleSheet()  # red
    
    # Check winrate diff (negative = red)
    assert "-5.0" in widget._label_winrate_diff.text()
    assert "#f44747" in widget._label_winrate_diff.styleSheet()  # red
    
    # Check drawdown diff (positive = red, worse)
    assert "+8.5" in widget._label_drawdown_diff.text()
    assert "#f44747" in widget._label_drawdown_diff.styleSheet()  # red
    
    # Check verdict (degraded = red)
    assert "DEGRADED" in widget._label_verdict.text()
    assert "#f44747" in widget._label_verdict.styleSheet()  # red


def test_compare_widget_display_neutral(qapp):
    """Test widget displays neutral verdict correctly."""
    widget = CompareWidget()
    
    comparison = RunComparison(
        profit_diff=0.5,
        winrate_diff=-0.2,
        drawdown_diff=2.0,
        verdict="neutral",
    )
    
    widget.display(comparison)
    
    # Check labels have been updated
    assert len(widget._label_verdict.text()) > 0
    
    # Check verdict (neutral = neutral color)
    assert "NEUTRAL" in widget._label_verdict.text()
    assert "#9cdcfe" in widget._label_verdict.styleSheet()  # neutral


def test_compare_widget_get_selected_runs(qapp):
    """Test get_selected_runs returns correct data."""
    widget = CompareWidget()
    
    runs = [
        {"id": "run_1", "timestamp": "2024-01-01"},
        {"id": "run_2", "timestamp": "2024-01-02"},
    ]
    widget.set_run_choices(runs)
    
    # Get selected runs
    run_a, run_b = widget.get_selected_runs()
    
    # Should return the run data
    assert run_a == runs[0]
    assert run_b == runs[1]


def test_compare_widget_display_zero_diffs(qapp):
    """Test widget handles zero diffs (neutral color)."""
    widget = CompareWidget()
    
    comparison = RunComparison(
        profit_diff=0.0,
        winrate_diff=0.0,
        drawdown_diff=0.0,
        verdict="neutral",
    )
    
    widget.display(comparison)
    
    # All diffs should show neutral color
    assert "#9cdcfe" in widget._label_profit_diff.styleSheet()  # neutral
    assert "#9cdcfe" in widget._label_winrate_diff.styleSheet()  # neutral
    assert "#9cdcfe" in widget._label_drawdown_diff.styleSheet()  # neutral
