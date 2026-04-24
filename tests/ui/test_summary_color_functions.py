"""Property-based tests for the color-coding pure functions in results_page.

Tests Properties 1–6 (color functions) and Properties 7–8 (balance delta widget).

Feature: backtest-summary-enhancement
"""
from __future__ import annotations

import sys
import re

import pytest
from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st

from PySide6.QtWidgets import QApplication, QLabel

from app.ui.pages.results_page import (
    _profit_color,
    _win_rate_color,
    _sharpe_color,
    _profit_factor_color,
    _profit_accent_color,
    _drawdown_accent_color,
)
from app.ui import theme

# ── QApplication singleton ────────────────────────────────────────────────────

_app = QApplication.instance() or QApplication(sys.argv)


# ── Property 1: Profit color partitions the real line correctly ───────────────
# Feature: backtest-summary-enhancement, Property 1: profit color partitions the real line correctly

@given(st.floats(min_value=0.001, allow_nan=False, allow_infinity=False))
@hyp_settings(max_examples=200)
def test_profit_color_positive(v: float):
    """_profit_color returns GREEN for any v > 0. Validates: Requirements 3.1"""
    assert _profit_color(v) == theme.GREEN


@given(st.floats(max_value=-0.001, allow_nan=False, allow_infinity=False))
@hyp_settings(max_examples=200)
def test_profit_color_negative(v: float):
    """_profit_color returns RED for any v < 0. Validates: Requirement 3.2"""
    assert _profit_color(v) == theme.RED


def test_profit_color_zero():
    """_profit_color returns TEXT_PRIMARY for v == 0. Validates: Requirement 3.3"""
    assert _profit_color(0.0) == theme.TEXT_PRIMARY


# ── Property 2: Win rate color threshold is monotone at 50.0 ─────────────────
# Feature: backtest-summary-enhancement, Property 2: win rate color threshold is monotone at 50.0

@given(st.floats(min_value=50.0, max_value=100.0, allow_nan=False, allow_infinity=False))
@hyp_settings(max_examples=200)
def test_win_rate_color_green(v: float):
    """_win_rate_color returns GREEN for v >= 50.0. Validates: Requirement 3.4"""
    assert _win_rate_color(v) == theme.GREEN


@given(st.floats(min_value=0.0, max_value=49.999, allow_nan=False, allow_infinity=False))
@hyp_settings(max_examples=200)
def test_win_rate_color_red(v: float):
    """_win_rate_color returns RED for v in [0.0, 50.0). Validates: Requirement 3.5"""
    assert _win_rate_color(v) == theme.RED


# ── Property 3: Sharpe color partitions into three zones ─────────────────────
# Feature: backtest-summary-enhancement, Property 3: sharpe color partitions into three zones

@given(st.floats(min_value=1.0, max_value=100.0, allow_nan=False, allow_infinity=False))
@hyp_settings(max_examples=200)
def test_sharpe_color_green(v: float):
    """_sharpe_color returns GREEN for v >= 1.0. Validates: Requirement 3.6"""
    assert _sharpe_color(v) == theme.GREEN


@given(st.floats(min_value=0.001, max_value=0.999, allow_nan=False, allow_infinity=False))
@hyp_settings(max_examples=200)
def test_sharpe_color_yellow(v: float):
    """_sharpe_color returns YELLOW for v in (0.0, 1.0). Validates: Requirement 3.7"""
    assert _sharpe_color(v) == theme.YELLOW


@given(st.floats(max_value=0.0, allow_nan=False, allow_infinity=False))
@hyp_settings(max_examples=200)
def test_sharpe_color_red(v: float):
    """_sharpe_color returns RED for v <= 0.0. Validates: Requirement 3.8"""
    assert _sharpe_color(v) == theme.RED


# ── Property 4: Profit factor color threshold is monotone at 1.0 ─────────────
# Feature: backtest-summary-enhancement, Property 4: profit factor color threshold is monotone at 1.0

@given(st.floats(min_value=1.0, max_value=100.0, allow_nan=False, allow_infinity=False))
@hyp_settings(max_examples=200)
def test_profit_factor_color_green(v: float):
    """_profit_factor_color returns GREEN for v >= 1.0. Validates: Requirement 3.9"""
    assert _profit_factor_color(v) == theme.GREEN


@given(st.floats(min_value=0.0, max_value=0.999, allow_nan=False, allow_infinity=False))
@hyp_settings(max_examples=200)
def test_profit_factor_color_red(v: float):
    """_profit_factor_color returns RED for v in [0.0, 1.0). Validates: Requirement 3.10"""
    assert _profit_factor_color(v) == theme.RED


# ── Property 5: KPI accent colors are consistent with profit color rules ──────
# Feature: backtest-summary-enhancement, Property 5: KPI accent colors are consistent with profit color rules

@given(st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False))
@hyp_settings(max_examples=200)
def test_profit_accent_color_green(v: float):
    """_profit_accent_color returns GREEN for v >= 0. Validates: Requirement 2.3"""
    assert _profit_accent_color(v) == theme.GREEN


@given(st.floats(max_value=-0.001, allow_nan=False, allow_infinity=False))
@hyp_settings(max_examples=200)
def test_profit_accent_color_red(v: float):
    """_profit_accent_color returns RED for v < 0. Validates: Requirement 2.4"""
    assert _profit_accent_color(v) == theme.RED


# ── Property 6: Drawdown accent color threshold is monotone at 20.0 ──────────
# Feature: backtest-summary-enhancement, Property 6: drawdown accent color threshold is monotone at 20.0

@given(st.floats(min_value=20.001, max_value=100.0, allow_nan=False, allow_infinity=False))
@hyp_settings(max_examples=200)
def test_drawdown_accent_color_red(v: float):
    """_drawdown_accent_color returns RED for v > 20.0. Validates: Requirement 2.5"""
    assert _drawdown_accent_color(v) == theme.RED


@given(st.floats(min_value=0.0, max_value=20.0, allow_nan=False, allow_infinity=False))
@hyp_settings(max_examples=200)
def test_drawdown_accent_color_yellow(v: float):
    """_drawdown_accent_color returns YELLOW for v in [0.0, 20.0]. Validates: Requirement 2.6"""
    assert _drawdown_accent_color(v) == theme.YELLOW


# ── Properties 7–8: Balance delta widget ─────────────────────────────────────
# Requires ResultsPage instance (needs QApplication, already created above)

from unittest.mock import MagicMock
from app.ui.pages.results_page import ResultsPage


@pytest.fixture(scope="session")
def results_page_instance():
    """Minimal ResultsPage instance for testing helper methods."""
    mock_state = MagicMock()
    mock_state.current_settings = None
    return ResultsPage(mock_state)


# Feature: backtest-summary-enhancement, Property 7: balance delta sign and color are consistent

@given(
    starting=st.floats(min_value=0.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False),
    delta=st.floats(min_value=0.01, max_value=100_000.0, allow_nan=False, allow_infinity=False),
)
@hyp_settings(max_examples=200)
def test_balance_delta_positive_sign_and_color(
    results_page_instance: ResultsPage, starting: float, delta: float
):
    """When final > starting, label starts with '+' and color is GREEN. Validates: Requirement 6.1"""
    final = starting + delta
    lbl = results_page_instance._balance_delta_widget(starting, final)
    assert lbl is not None
    assert lbl.text().startswith("+"), f"Expected '+' prefix, got: {lbl.text()!r}"
    assert theme.GREEN in lbl.styleSheet()


@given(
    starting=st.floats(min_value=0.01, max_value=1_000_000.0, allow_nan=False, allow_infinity=False),
    delta=st.floats(min_value=0.01, max_value=100_000.0, allow_nan=False, allow_infinity=False),
)
@hyp_settings(max_examples=200)
def test_balance_delta_negative_sign_and_color(
    results_page_instance: ResultsPage, starting: float, delta: float
):
    """When final < starting, label starts with '−' and color is RED. Validates: Requirement 6.2"""
    final = max(0.0, starting - delta)
    if final >= starting:
        return  # skip degenerate case
    lbl = results_page_instance._balance_delta_widget(starting, final)
    assert lbl is not None
    assert lbl.text().startswith("\u2212"), f"Expected '−' prefix, got: {lbl.text()!r}"
    assert theme.RED in lbl.styleSheet()


# Feature: backtest-summary-enhancement, Property 8: balance delta formatting precision

@given(
    starting=st.floats(min_value=0.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False),
    delta=st.floats(min_value=0.01, max_value=100_000.0, allow_nan=False, allow_infinity=False),
)
@hyp_settings(max_examples=200)
def test_balance_delta_formatting_precision(
    results_page_instance: ResultsPage, starting: float, delta: float
):
    """Delta label contains a value to exactly 2 decimal places followed by ' USDT'. Validates: Requirement 6.4"""
    final = starting + delta
    lbl = results_page_instance._balance_delta_widget(starting, final)
    assert lbl is not None
    text = lbl.text()
    # Match pattern: optional sign prefix, then digits.dd USDT
    assert re.search(r"\d+\.\d{2} USDT$", text), (
        f"Expected '...X.XX USDT' format, got: {text!r}"
    )
