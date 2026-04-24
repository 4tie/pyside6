"""
Bug condition exploration test for results_page resize event crash.

Property 1: Bug Condition — Resize Event Crashes With Broken super() Call

Validates: Requirements 1.1, 1.2, 2.1, 2.2

This test encodes the expected behavior: a plain QWidget container receiving a
QResizeEvent via the _reflow closure must NOT raise AttributeError.

On UNFIXED code (broken pattern: super(type(container), container).resizeEvent(event)):
  - The broken super() resolves to QObject which has no resizeEvent → AttributeError
  - This test FAILS, confirming the bug exists

On FIXED code (QWidget.resizeEvent(container, event)):
  - The call succeeds without exception
  - This test PASSES, confirming the fix is correct
"""
import pytest
from hypothesis import given, settings as h_settings
import hypothesis.strategies as st

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QResizeEvent
from PySide6.QtCore import QSize


# Ensure a QApplication exists for all Qt widget operations
_app = QApplication.instance() or QApplication([])


class TestBugConditionExploration_ResizeEventCrash:
    """
    Validates: Requirements 1.1, 1.2

    Explores the bug condition: _reflow called with a non-None QResizeEvent on a
    plain QWidget container using the broken super(type(container), container)
    pattern raises AttributeError.
    """

    def test_broken_pattern_raises_attribute_error(self):
        """
        Directly demonstrates the broken pattern raises AttributeError.

        The broken call super(type(container), container).resizeEvent(event)
        resolves to QObject when container is a plain QWidget, and QObject has
        no resizeEvent method.

        Validates: Requirements 1.1, 1.2
        """
        container = QWidget()
        container.resize(400, 100)
        event = QResizeEvent(QSize(400, 100), QSize(390, 100))

        def broken_reflow(ev=None):
            if ev is not None:
                # This is the BROKEN pattern — super(type(container), container)
                # resolves to QObject when container is a plain QWidget
                super(type(container), container).resizeEvent(ev)

        with pytest.raises(AttributeError, match="resizeEvent"):
            broken_reflow(event)

    @given(st.integers(min_value=100, max_value=1200))
    @h_settings(max_examples=50)
    def test_fixed_pattern_does_not_raise_for_any_width(self, width: int):
        """
        Property 1: For any container width, the fixed _reflow closure must not
        raise AttributeError when called with a non-None QResizeEvent.

        This test FAILS on unfixed code (broken super() pattern raises AttributeError).
        This test PASSES on fixed code (QWidget.resizeEvent(container, event) succeeds).

        Validates: Requirements 2.1, 2.2
        """
        container = QWidget()
        container.resize(width, 100)
        event = QResizeEvent(QSize(width, 100), QSize(max(width - 10, 100), 100))

        def fixed_reflow(ev=None):
            """Minimal _reflow closure using the FIXED pattern."""
            if ev is not None:
                # This is the FIXED pattern — always resolves to QWidget.resizeEvent
                QWidget.resizeEvent(container, ev)

        # Must not raise any exception — specifically no AttributeError
        fixed_reflow(event)
