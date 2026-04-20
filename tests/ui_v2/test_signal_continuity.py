"""Signal continuity test — Property P2.

Verifies that every Qt signal connected in ``MainWindow.__init__`` is also
connected in ``ModernMainWindow.__init__`` (or its ``_wire_signals`` helper).

Property P2: Signal Continuity — every signal connected in ``MainWindow``
must also be connected in ``ModernMainWindow``.

**Validates: Requirements 1.8, 2.4**
"""
import inspect
import re

from app.ui.main_window import MainWindow
from app.ui_v2.main_window import ModernMainWindow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_connect_calls(source: str) -> list[str]:
    """Return a sorted list of unique ``.connect(`` call sites from *source*.

    Each entry is the full ``<receiver>.connect(`` token (everything up to and
    including the opening parenthesis), stripped of leading whitespace.  This
    gives a stable, human-readable identifier for each connection.

    Args:
        source: Python source code as a string.

    Returns:
        Sorted list of unique connect-call tokens found in the source.
    """
    # Match anything that ends with .connect( — captures the full LHS
    pattern = re.compile(r"([\w.\[\]()\"']+\.connect\()")
    return sorted(set(m.group(1) for m in pattern.finditer(source)))


def _method_source(*methods) -> str:
    """Concatenate the source of one or more methods into a single string.

    Args:
        *methods: Bound or unbound method objects.

    Returns:
        Concatenated source code string.
    """
    return "\n".join(inspect.getsource(m) for m in methods)


# ---------------------------------------------------------------------------
# Source extraction
# ---------------------------------------------------------------------------


def _get_main_window_source() -> str:
    """Return the source of ``MainWindow.__init__``."""
    return inspect.getsource(MainWindow.__init__)


def _get_modern_window_source() -> str:
    """Return the combined source of ``ModernMainWindow.__init__`` and
    ``ModernMainWindow._wire_signals``.

    ``_wire_signals`` is the dedicated helper that mirrors the wiring done
    inline in the original ``MainWindow.__init__``.
    """
    return _method_source(
        ModernMainWindow.__init__,
        ModernMainWindow._wire_signals,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSignalContinuity:
    """Property P2 — Signal Continuity.

    Every signal connected in ``MainWindow`` must also be connected in
    ``ModernMainWindow``.

    **Validates: Requirements 1.8, 2.4**
    """

    def test_settings_saved_signal_connected_in_modern(self):
        """``settings_state.settings_saved`` must be connected in ModernMainWindow.

        In MainWindow:
            self.settings_state.settings_saved.connect(self._on_settings_saved)

        **Validates: Requirements 1.8, 2.4**
        """
        modern_src = _get_modern_window_source()
        assert "settings_saved.connect(" in modern_src, (
            "ModernMainWindow does not connect settings_state.settings_saved. "
            "Expected a call matching 'settings_saved.connect(' in "
            "__init__ or _wire_signals."
        )

    def test_loop_completed_signal_connected_in_modern(self):
        """``loop_completed`` signal must be connected in ModernMainWindow.

        In MainWindow:
            self.loop_page.loop_completed.connect(self._on_loop_completed)

        ModernMainWindow uses backtest_page.loop_completed (the equivalent
        page in the v2 layout).

        **Validates: Requirements 1.8, 2.4**
        """
        modern_src = _get_modern_window_source()
        assert "loop_completed.connect(" in modern_src, (
            "ModernMainWindow does not connect loop_completed. "
            "Expected a call matching 'loop_completed.connect(' in "
            "__init__ or _wire_signals."
        )

    def test_ai_service_connect_backtest_service_called_in_modern(self):
        """``ai_service.connect_backtest_service`` must be called in ModernMainWindow.

        In MainWindow:
            self.ai_service.connect_backtest_service(backtest_service)

        **Validates: Requirements 1.8, 2.4**
        """
        modern_src = _get_modern_window_source()
        assert "connect_backtest_service(" in modern_src, (
            "ModernMainWindow does not call ai_service.connect_backtest_service. "
            "Expected 'connect_backtest_service(' in __init__ or _wire_signals."
        )

    def test_all_main_window_connect_calls_present_in_modern(self):
        """Every ``.connect(`` call site in MainWindow.__init__ has a
        corresponding connection in ModernMainWindow.

        This is the comprehensive P2 check: we enumerate the signal names
        (the attribute immediately before ``.connect(``) from MainWindow and
        assert each appears in the ModernMainWindow source.

        **Validates: Requirements 1.8, 2.4**
        """
        orig_src = _get_main_window_source()
        modern_src = _get_modern_window_source()

        # Extract just the signal attribute names (the word before .connect()
        # e.g. "settings_saved" from "settings_state.settings_saved.connect("
        signal_name_pattern = re.compile(r"(\w+)\.connect\(")
        orig_signal_names = set(signal_name_pattern.findall(orig_src))

        missing = []
        for signal_name in sorted(orig_signal_names):
            if f"{signal_name}.connect(" not in modern_src:
                missing.append(signal_name)

        assert not missing, (
            "The following signal(s) connected in MainWindow.__init__ are "
            "NOT connected in ModernMainWindow.__init__ / _wire_signals:\n"
            + "\n".join(f"  - {s}.connect(...)" for s in missing)
        )

    def test_main_window_has_expected_signal_connections(self):
        """Sanity-check: MainWindow.__init__ contains the three known signal
        connections so that the continuity tests are meaningful.

        If this test fails it means MainWindow was refactored and the
        continuity tests need updating.
        """
        orig_src = _get_main_window_source()

        assert "settings_saved.connect(" in orig_src, (
            "MainWindow.__init__ no longer connects settings_saved — "
            "update the continuity tests."
        )
        assert "loop_completed.connect(" in orig_src, (
            "MainWindow.__init__ no longer connects loop_completed — "
            "update the continuity tests."
        )
        assert "connect_backtest_service(" in orig_src, (
            "MainWindow.__init__ no longer calls connect_backtest_service — "
            "update the continuity tests."
        )

    def test_modern_window_wire_signals_method_exists(self):
        """``ModernMainWindow._wire_signals`` must exist as a dedicated method.

        The design document specifies that signal wiring is extracted into
        ``_wire_signals`` to mirror the original ``MainWindow.__init__`` wiring.
        """
        assert hasattr(ModernMainWindow, "_wire_signals"), (
            "ModernMainWindow is missing the _wire_signals method. "
            "Signal wiring should be in a dedicated _wire_signals helper."
        )
        assert callable(ModernMainWindow._wire_signals), (
            "ModernMainWindow._wire_signals is not callable."
        )

    def test_modern_window_on_settings_saved_handler_exists(self):
        """``ModernMainWindow._on_settings_saved`` handler must exist.

        MainWindow defines ``_on_settings_saved`` as the slot for
        ``settings_saved``; ModernMainWindow must provide the same handler.
        """
        assert hasattr(ModernMainWindow, "_on_settings_saved"), (
            "ModernMainWindow is missing _on_settings_saved handler."
        )
        assert callable(ModernMainWindow._on_settings_saved), (
            "ModernMainWindow._on_settings_saved is not callable."
        )
