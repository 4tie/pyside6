"""Property-based tests for CollapsibleTerminal widget using Hypothesis."""
import sys

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from PySide6.QtWidgets import QApplication

from app.ui.widgets.collapsible_terminal import CollapsibleTerminal


# ---------------------------------------------------------------------------
# Session-scoped QApplication fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qt_app():
    """Create (or reuse) a QApplication for the test session."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

# Feature: tab-layout-redesign, Property 1: Toggle round-trip restores original state
@given(st.booleans())
@settings(max_examples=100)
def test_toggle_round_trip(qt_app, initial_expanded):
    """Validates: Requirements 2.2, 2.3"""
    w = CollapsibleTerminal()
    try:
        if initial_expanded:
            w.show_terminal()
        else:
            w.hide_terminal()

        w.toggle()
        w.toggle()

        assert w.is_expanded() == initial_expanded
        expected_label = (
            CollapsibleTerminal.LABEL_EXPANDED
            if initial_expanded
            else CollapsibleTerminal.LABEL_COLLAPSED
        )
        assert w._toggle_btn.text() == expected_label
    finally:
        w.close()


# Feature: tab-layout-redesign, Property 2: show_terminal always results in expanded state
@given(st.booleans())
@settings(max_examples=100)
def test_show_terminal_idempotent(qt_app, initial_expanded):
    """Validates: Requirements 2.4, 7.3"""
    w = CollapsibleTerminal()
    try:
        if initial_expanded:
            w.show_terminal()
        else:
            w.hide_terminal()

        w.show_terminal()

        assert w.is_expanded() is True
        assert w._toggle_btn.text() == CollapsibleTerminal.LABEL_EXPANDED
    finally:
        w.close()


# Feature: tab-layout-redesign, Property 3: Independent toggle state per page
@given(st.booleans(), st.booleans())
@settings(max_examples=100)
def test_instance_independence(qt_app, state_a, state_b):
    """Validates: Requirements 2.5"""
    w_a = CollapsibleTerminal()
    w_b = CollapsibleTerminal()
    try:
        if state_a:
            w_a.show_terminal()
        else:
            w_a.hide_terminal()

        if state_b:
            w_b.show_terminal()
        else:
            w_b.hide_terminal()

        w_a.toggle()

        assert w_b.is_expanded() == state_b
    finally:
        w_a.close()
        w_b.close()


# Feature: tab-layout-redesign, Property 4: Label always reflects expanded state
@given(st.lists(st.sampled_from(["toggle", "show", "hide"]), min_size=1, max_size=20))
@settings(max_examples=100)
def test_label_state_consistency(qt_app, ops):
    """Validates: Requirements 2.1, 2.2, 2.3"""
    w = CollapsibleTerminal()
    try:
        for op in ops:
            if op == "toggle":
                w.toggle()
            elif op == "show":
                w.show_terminal()
            else:
                w.hide_terminal()

            expected_label = (
                CollapsibleTerminal.LABEL_EXPANDED
                if w.is_expanded()
                else CollapsibleTerminal.LABEL_COLLAPSED
            )
            assert w._toggle_btn.text() == expected_label
    finally:
        w.close()
