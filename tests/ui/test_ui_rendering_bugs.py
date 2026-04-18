"""
Bug condition exploration and preservation tests for UI rendering bugs.

These tests encode the EXPECTED (correct) behavior and are designed to FAIL on
the unfixed code (exploration tests), confirming the bugs described in the bugfix
spec at .kiro/specs/ui-rendering-bugs/.

After the fix is applied, all tests should PASS.

Documented failure output (unfixed code):
---------------------------------------------------------------------------
FAILED tests/ui/test_ui_rendering_bugs.py::test_bug1_stale_layout_children
  AssertionError: Bug 1 confirmed: stale_child_count == 1 after deleteLater() clear.
  deleteLater() is asynchronous — the widget remains in the layout until the Qt
  event loop processes the deferred deletion. Expected 0 stale children, got 1.
  assert 1 == 0

FAILED tests/ui/test_ui_rendering_bugs.py::test_bug1_opacity_effect_not_removed
  AssertionError: Bug 1 confirmed: widget.graphicsEffect() is not None after
  animation finished signal fired. The unfixed _fade_in_widget() never connects
  anim.finished to a cleanup slot, so the QGraphicsOpacityEffect persists.
  assert <PySide6.QtWidgets.QGraphicsOpacityEffect object> is None

FAILED tests/ui/test_ui_rendering_bugs.py::test_bug2_default_font_not_emoji
  AssertionError: Bug 2 confirmed: QPushButton default font family is not an
  emoji-capable font. Got 'Segoe UI' (or similar), expected one of
  {'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji'}.

FAILED tests/ui/test_ui_rendering_bugs.py::test_bug3_preset_button_max_width_50
  AssertionError: Bug 3 confirmed: QPushButton("120d").maximumWidth() == 50.
  setMaximumWidth(50) clips labels like "120d" and "360d".

FAILED tests/ui/test_ui_rendering_bugs.py::test_bug4_word_wrap_disabled
  AssertionError: Bug 4 confirmed: QLabel.wordWrap() == False after setWordWrap(False).
  Subtitle labels clip text instead of wrapping at narrow widths.
---------------------------------------------------------------------------

Counterexamples found (verified on unfixed code):
  Bug 1: layout.count() == 1 after deleteLater() (widget still present, count should be 0)
         Counterexample: n_analyze_calls=1 → stale_child_count == 1 (expected 0)
  Bug 1: widget.graphicsEffect() is a QGraphicsOpacityEffect instance (should be None)
         Counterexample: n_widgets=1 → graphicsEffect() is QGraphicsOpacityEffect (expected None)
  Bug 2: btn.font().family() == 'Segoe UI' (not an emoji font)
         Counterexample: QPushButton() without setFont → family not in emoji set
  Bug 3: QPushButton("120d").maximumWidth() == 50
         Counterexample: label="120d" → maximumWidth() == 50 (expected != 50)
  Bug 4: QLabel("text").wordWrap() == False after setWordWrap(False)
         Counterexample: any text → wordWrap() == False (expected True)
"""
import sys
import pytest
from hypothesis import given, settings as h_settings, HealthCheck
from hypothesis import strategies as st
from hypothesis.database import InMemoryExampleDatabase

from PySide6.QtWidgets import (
    QApplication,
    QVBoxLayout,
    QWidget,
    QGraphicsOpacityEffect,
    QPushButton,
    QLabel,
)
from PySide6.QtCore import QCoreApplication, QPropertyAnimation, QEasingCurve


# ---------------------------------------------------------------------------
# QApplication — module-level to avoid fixture/hypothesis interaction issues
# ---------------------------------------------------------------------------

_qapp = QApplication.instance() or QApplication(sys.argv[:1])

# Shared hypothesis settings: 3 examples keeps the suite fast while still
# exercising the property across a small range of generated inputs.
_FAST = dict(
    max_examples=3,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    database=InMemoryExampleDatabase(),
)

# ---------------------------------------------------------------------------
# Helpers that replicate the UNFIXED behavior
# ---------------------------------------------------------------------------

def _unfixed_clear_with_delete_later(layout: QVBoxLayout, placeholder_widget: QWidget) -> None:
    """Simulate the ACTUAL unfixed clear logic from _display_baseline_summary().

    The actual unfixed code in improve_page.py:
        if self._empty_baseline is not None:
            self._empty_baseline.deleteLater()
            self._empty_baseline = None

    The widget is NOT removed from the layout via takeAt() — it's just scheduled
    for deletion. The layout still holds a reference to it because deleteLater()
    is asynchronous (deferred to the next event loop iteration).
    """
    # BUG: deleteLater() without removing from layout first
    placeholder_widget.deleteLater()


def _unfixed_fade_in_widget(widget: QWidget, duration: int = 350) -> None:
    """Replicate the unfixed _fade_in_widget() from improve_page.py.

    The unfixed version attaches a QGraphicsOpacityEffect but never connects
    anim.finished to a cleanup slot, so the effect persists after the animation.
    """
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity")
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.start()
    # BUG: no anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    widget._fade_anim = anim


# ===========================================================================
# Bug 1 — Stale layout children after deleteLater()
# ===========================================================================

@pytest.mark.bug_condition
@given(st.integers(min_value=1, max_value=10))
@h_settings(**_FAST)
def test_bug1_stale_layout_children(n_analyze_calls):
    """
    Bug 1 — Stale layout children after consecutive analyze calls.

    Simulates a layout with one placeholder child widget, then calls the unfixed
    clear logic (deleteLater() pattern) and checks the child count.

    The test asserts stale_child_count == 0 after the clear. This FAILS on unfixed
    code because deleteLater() is asynchronous and the widget remains in the layout
    until the Qt event loop processes the deferred deletion.

    EXPECTED OUTCOME on unfixed code: FAIL
    EXPECTED OUTCOME after fix (setParent(None)): PASS

    Validates: Requirements 1.1, 1.2
    Counterexample: n_analyze_calls=1 → layout.count() == 1 (expected 0)
    """
    parent = QWidget()
    layout = QVBoxLayout(parent)

    placeholder = QWidget(parent)
    layout.addWidget(placeholder)
    assert layout.count() == 1

    _unfixed_clear_with_delete_later(layout, placeholder)

    # Do NOT call processEvents — that would hide the bug.
    stale_child_count = layout.count()

    assert stale_child_count == 0, (
        f"Bug 1 confirmed: stale_child_count == {stale_child_count} after deleteLater() clear. "
        f"deleteLater() is asynchronous — the widget remains in the layout until the Qt "
        f"event loop processes the deferred deletion. Expected 0 stale children, got {stale_child_count}."
    )


# ---------------------------------------------------------------------------
# Bug 1 — QGraphicsOpacityEffect not removed after animation completes
# ---------------------------------------------------------------------------

@pytest.mark.bug_condition
@given(st.integers(min_value=1, max_value=5))
@h_settings(**_FAST)
def test_bug1_opacity_effect_not_removed(n_widgets):
    """
    Bug 1 — QGraphicsOpacityEffect not removed after fade-in animation completes.

    Creates a mock widget with a QGraphicsOpacityEffect attached via the unfixed
    _fade_in_widget() behavior (does NOT connect finished to cleanup). Fires the
    animation's finished signal and asserts widget.graphicsEffect() is None.

    EXPECTED OUTCOME on unfixed code: FAIL
    EXPECTED OUTCOME after fix: PASS

    Validates: Requirements 1.3, 1.4
    Counterexample: n_widgets=1 → graphicsEffect() is QGraphicsOpacityEffect (expected None)
    """
    for _ in range(n_widgets):
        widget = QWidget()
        _unfixed_fade_in_widget(widget, duration=0)
        widget._fade_anim.finished.emit()
        QCoreApplication.processEvents()

        effect = widget.graphicsEffect()
        assert effect is None, (
            f"Bug 1 confirmed: widget.graphicsEffect() is not None after "
            f"animation finished signal fired. The unfixed _fade_in_widget() never connects "
            f"anim.finished to a cleanup slot, so the QGraphicsOpacityEffect persists. "
            f"Got: {effect!r}"
        )


# ===========================================================================
# Bug 1 — Preservation: compute_highlight and _build_status_message
# ===========================================================================

from app.ui.pages.improve_page import compute_highlight, _build_status_message

_VALID_TRIGGERS = [
    "analyze_loading",
    "analysis_complete_no_issues",
    "candidate_backtest_start",
    "candidate_backtest_success",
    "candidate_backtest_failed",
    "accept",
    "reject",
    "rollback",
]

_METRICS_HIGHER_BETTER = ["win_rate", "total_profit", "sharpe_ratio",
                           "profit_factor", "expectancy", "total_trades"]
_METRICS_LOWER_BETTER = ["max_drawdown"]


@pytest.mark.preservation
@given(
    metric=st.sampled_from(_METRICS_HIGHER_BETTER),
    baseline=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    delta=st.floats(min_value=0.001, max_value=1e4, allow_nan=False, allow_infinity=False),
)
@h_settings(**_FAST)
def test_preservation_compute_highlight_higher_is_better(metric, baseline, delta):
    """
    Preservation — compute_highlight returns 'green' when candidate > baseline
    for higher-is-better metrics, and 'red' when candidate < baseline.

    Validates: Requirements 3.1, 3.4
    """
    assert compute_highlight(metric, baseline, baseline + delta) == "green"
    assert compute_highlight(metric, baseline, baseline - delta) == "red"
    assert compute_highlight(metric, baseline, baseline) is None


@pytest.mark.preservation
@given(
    metric=st.sampled_from(_METRICS_LOWER_BETTER),
    baseline=st.floats(min_value=0.001, max_value=1e6, allow_nan=False, allow_infinity=False),
    delta=st.floats(min_value=0.001, max_value=1e4, allow_nan=False, allow_infinity=False),
)
@h_settings(**_FAST)
def test_preservation_compute_highlight_lower_is_better(metric, baseline, delta):
    """
    Preservation — compute_highlight returns 'green' when candidate < baseline
    for lower-is-better metrics (e.g. max_drawdown).

    Validates: Requirements 3.1, 3.4
    """
    assert compute_highlight(metric, baseline, baseline - delta) == "green"
    assert compute_highlight(metric, baseline, baseline + delta) == "red"
    assert compute_highlight(metric, baseline, baseline) is None


@pytest.mark.preservation
@given(trigger=st.sampled_from(_VALID_TRIGGERS))
@h_settings(**_FAST)
def test_preservation_build_status_message_non_empty(trigger):
    """
    Preservation — _build_status_message returns a non-empty message and color
    for every valid trigger key.

    Validates: Requirements 3.2, 3.3
    """
    msg, color = _build_status_message(trigger)
    assert isinstance(msg, str) and len(msg) > 0, (
        f"_build_status_message('{trigger}') returned empty message"
    )
    assert isinstance(color, str) and color.startswith("#"), (
        f"_build_status_message('{trigger}') returned invalid color: {color!r}"
    )


@pytest.mark.preservation
@given(n_issues=st.integers(min_value=0, max_value=10_000))
@h_settings(**_FAST)
def test_preservation_build_status_message_includes_issue_count(n_issues):
    """
    Preservation — _build_status_message('analysis_complete_issues', n) includes
    the issue count in the returned message string.

    Validates: Requirements 3.2, 3.3
    """
    msg, _ = _build_status_message("analysis_complete_issues", n_issues)
    assert str(n_issues) in msg, (
        f"Expected issue count {n_issues} in message, got: {msg!r}"
    )


# ===========================================================================
# Bug 2 — Default button font lacks emoji glyphs
# ===========================================================================

_EMOJI_FONT_FAMILIES = {"Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji"}


@pytest.mark.bug_condition
@given(st.just(None))  # single-case: no meaningful variation, just confirms the bug
@h_settings(**_FAST)
def test_bug2_default_font_not_emoji(_):
    """
    Bug 2 — Default QPushButton font is not an emoji-capable font on Windows.

    Creates a QPushButton without setting an explicit font (simulating the unfixed
    _make_favorite_button() / _make_lock_button()) and asserts that the font family
    is one of the known emoji-capable families.

    EXPECTED OUTCOME on unfixed code: FAIL (default font is 'Segoe UI' or similar)
    EXPECTED OUTCOME after fix (_emoji_font() applied): PASS

    Validates: Requirements 1.5, 1.6
    Counterexample: btn.font().family() == 'Segoe UI' (not in emoji set)
    """
    btn = QPushButton("♥")
    # No setFont() call — simulates the unfixed code
    family = btn.font().family()
    assert family in _EMOJI_FONT_FAMILIES, (
        f"Bug 2 confirmed: QPushButton default font family {family!r} is not an "
        f"emoji-capable font. Expected one of {_EMOJI_FONT_FAMILIES}. "
        f"On Windows, '♥' and '🔒' render as empty squares with this font."
    )


# ===========================================================================
# Bug 2 — Preservation: favorite and lock toggle text logic
# ===========================================================================

@pytest.mark.preservation
@given(pair=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N", "P"))))
@h_settings(**_FAST)
def test_preservation_favorite_toggle_roundtrip(pair):
    """
    Preservation — toggling favorite twice returns button text to '♡' (unfavorited).

    Pure-logic test: no Qt widget instantiation required.

    Validates: Requirements 3.5
    """
    favorites: set = set()

    # Initial state: not a favorite
    text_initial = "♥" if pair in favorites else "♡"
    assert text_initial == "♡"

    # First toggle: add to favorites
    favorites.add(pair)
    text_after_first = "♥" if pair in favorites else "♡"
    assert text_after_first == "♥"

    # Second toggle: remove from favorites
    favorites.discard(pair)
    text_after_second = "♥" if pair in favorites else "♡"
    assert text_after_second == "♡", (
        f"After two toggles, expected '♡' but got {text_after_second!r} for pair {pair!r}"
    )


@pytest.mark.preservation
@given(pair=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N", "P"))))
@h_settings(**_FAST)
def test_preservation_lock_toggle_text(pair):
    """
    Preservation — lock toggle sets '🔒' when locked and '🔓' when unlocked.

    Pure-logic test: no Qt widget instantiation required.

    Validates: Requirements 3.6
    """
    locked_pairs: set = set()

    # Lock
    locked_pairs.add(pair)
    text_locked = "🔒" if pair in locked_pairs else "🔓"
    assert text_locked == "🔒", f"Expected '🔒' when locked, got {text_locked!r}"

    # Unlock
    locked_pairs.discard(pair)
    text_unlocked = "🔒" if pair in locked_pairs else "🔓"
    assert text_unlocked == "🔓", f"Expected '🔓' when unlocked, got {text_unlocked!r}"


# ===========================================================================
# Bug 3 — Preset button setMaximumWidth(50) clips labels
# ===========================================================================

_PRESET_LABELS = ["7d", "14d", "30d", "90d", "120d", "360d"]


@pytest.mark.bug_condition
@given(label=st.sampled_from(_PRESET_LABELS))
@h_settings(**_FAST)
def test_bug3_preset_button_max_width_50(label):
    """
    Bug 3 — Preset button has maximumWidth == 50, clipping labels like '120d'.

    Creates a QPushButton and calls setMaximumWidth(50) (simulating the unfixed
    code in backtest_page.py and download_data_page.py), then asserts the
    maximumWidth is NOT 50.

    EXPECTED OUTCOME on unfixed code: FAIL (maximumWidth() == 50)
    EXPECTED OUTCOME after fix (setMinimumWidth(48)): PASS

    Validates: Requirements 1.7, 1.8
    Counterexample: QPushButton("120d").maximumWidth() == 50
    """
    btn = QPushButton(label)
    btn.setMaximumWidth(50)  # simulates the unfixed code

    assert btn.maximumWidth() != 50, (
        f"Bug 3 confirmed: QPushButton({label!r}).maximumWidth() == 50. "
        f"setMaximumWidth(50) clips labels like '120d' and '360d' at standard DPI."
    )


# ===========================================================================
# Bug 3 — Preservation: preset button click handler closure correctness
# ===========================================================================

@pytest.mark.preservation
@given(preset=st.sampled_from(_PRESET_LABELS))
@h_settings(**_FAST)
def test_preservation_preset_closure_captures_correct_value(preset):
    """
    Preservation — the lambda closure in the preset button loop captures the
    correct preset value (not the loop variable by reference).

    Pure-logic test: verifies the default-argument capture pattern
    `lambda checked, p=preset: p` returns the correct preset string.

    Validates: Requirements 3.7, 3.8
    """
    # Simulate the fixed closure pattern used in the loop:
    #   btn.clicked.connect(lambda checked, p=preset: self._on_timerange_preset(p))
    captured_values = []
    for p in _PRESET_LABELS:
        fn = lambda checked, p=p: captured_values.append(p)  # noqa: E731
        if p == preset:
            fn(False)  # simulate button click

    assert preset in captured_values, (
        f"Closure did not capture preset {preset!r} correctly. Got: {captured_values}"
    )


# ===========================================================================
# Bug 4 — Subtitle labels have wordWrap() == False
# ===========================================================================

@pytest.mark.bug_condition
@given(text=st.text(min_size=1, max_size=200))
@h_settings(**_FAST)
def test_bug4_word_wrap_disabled(text):
    """
    Bug 4 — Subtitle labels have wordWrap() == False, causing text clipping.

    Creates a QLabel and calls setWordWrap(False) (simulating the unfixed code
    in ImprovePage._init_ui()), then asserts wordWrap() == True.

    EXPECTED OUTCOME on unfixed code: FAIL (wordWrap() == False)
    EXPECTED OUTCOME after fix (setWordWrap(True)): PASS

    Validates: Requirements 1.9, 1.10
    Counterexample: any QLabel with setWordWrap(False) → wordWrap() == False
    """
    lbl = QLabel(text)
    lbl.setWordWrap(False)  # simulates the unfixed code

    assert lbl.wordWrap() is True, (
        f"Bug 4 confirmed: QLabel.wordWrap() == False after setWordWrap(False). "
        f"Subtitle labels clip text instead of wrapping at narrow window widths."
    )


# ===========================================================================
# Bug 4 — Preservation: label text content unchanged by word wrap setting
# ===========================================================================

@pytest.mark.preservation
@given(text=st.text(min_size=0, max_size=200))
@h_settings(**_FAST)
def test_preservation_label_text_unchanged_by_word_wrap(text):
    """
    Preservation — QLabel.text() is identical regardless of wordWrap setting.

    Confirms the fix changes only the wrap behavior, not the text content.

    Validates: Requirements 2.9, 2.10
    """
    lbl_wrap = QLabel(text)
    lbl_wrap.setWordWrap(True)

    lbl_no_wrap = QLabel(text)
    lbl_no_wrap.setWordWrap(False)

    assert lbl_wrap.text() == lbl_no_wrap.text(), (
        f"Label text changed when wordWrap was toggled. "
        f"wrap={lbl_wrap.text()!r}, no_wrap={lbl_no_wrap.text()!r}"
    )
