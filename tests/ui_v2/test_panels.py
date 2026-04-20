"""Unit tests for dockable panels in app/ui_v2/panels/.

Covers:
- TerminalPanel: dock areas, features, .terminal attribute
- AiPanel: dock areas, features, inner widget
- ResultsPanel: dock areas, features, .results_widget attribute

Requirements: 10.1, 10.2, 15.1, 15.5, 4.4, 5.1
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget

from app.ui_v2.panels.terminal_panel import TerminalPanel
from app.ui_v2.panels.results_panel import ResultsPanel
from app.ui.widgets.terminal_widget import TerminalWidget
from app.ui.widgets.backtest_results_widget import BacktestResultsWidget


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings_state():
    """Return a minimal mock SettingsState for AiPanel construction."""
    from app.core.models.settings_models import AppSettings, AISettings
    from unittest.mock import MagicMock

    settings = MagicMock()
    settings.current_settings = MagicMock()
    settings.current_settings.ai = AISettings()
    settings.ai_settings_changed = MagicMock()
    settings.ai_settings_changed.connect = MagicMock()
    return settings


# ===========================================================================
# TerminalPanel
# ===========================================================================


class TestTerminalPanel:
    """Tests for TerminalPanel (Requirements 10.1, 10.2)."""

    @pytest.fixture
    def panel(self, qtbot):
        w = TerminalPanel()
        qtbot.addWidget(w)
        return w

    def test_is_qdockwidget(self, panel):
        """TerminalPanel is a QDockWidget subclass."""
        assert isinstance(panel, QDockWidget)

    def test_title(self, panel):
        """TerminalPanel has the title 'Terminal'."""
        assert panel.windowTitle() == "Terminal"

    def test_object_name(self, panel):
        """TerminalPanel has objectName 'TerminalPanel'."""
        assert panel.objectName() == "TerminalPanel"

    def test_allowed_areas_bottom(self, panel):
        """TerminalPanel allows docking to the bottom area."""
        assert panel.allowedAreas() & Qt.BottomDockWidgetArea

    def test_allowed_areas_top(self, panel):
        """TerminalPanel allows docking to the top area."""
        assert panel.allowedAreas() & Qt.TopDockWidgetArea

    def test_not_allowed_left(self, panel):
        """TerminalPanel does not allow docking to the left area."""
        assert not (panel.allowedAreas() & Qt.LeftDockWidgetArea)

    def test_not_allowed_right(self, panel):
        """TerminalPanel does not allow docking to the right area."""
        assert not (panel.allowedAreas() & Qt.RightDockWidgetArea)

    def test_feature_closable(self, panel):
        """TerminalPanel has the DockWidgetClosable feature."""
        assert panel.features() & QDockWidget.DockWidgetClosable

    def test_feature_movable(self, panel):
        """TerminalPanel has the DockWidgetMovable feature."""
        assert panel.features() & QDockWidget.DockWidgetMovable

    def test_feature_no_floating(self, panel):
        """TerminalPanel does not have the DockWidgetFloatable feature."""
        assert not (panel.features() & QDockWidget.DockWidgetFloatable)

    def test_terminal_attribute_exists(self, panel):
        """TerminalPanel exposes a .terminal attribute."""
        assert hasattr(panel, "terminal")

    def test_terminal_is_terminal_widget(self, panel):
        """TerminalPanel.terminal is a TerminalWidget instance."""
        assert isinstance(panel.terminal, TerminalWidget)

    def test_terminal_is_inner_widget(self, panel):
        """TerminalPanel.terminal is the QDockWidget's inner widget."""
        assert panel.widget() is panel.terminal


# ===========================================================================
# AiPanel
# ===========================================================================


class TestAiPanel:
    """Tests for AiPanel (Requirements 15.1, 15.5)."""

    @pytest.fixture
    def panel(self, qtbot):
        from app.ui_v2.panels.ai_panel import AiPanel
        settings_state = _make_settings_state()
        w = AiPanel(settings_state=settings_state)
        qtbot.addWidget(w)
        return w

    def test_is_qdockwidget(self, panel):
        """AiPanel is a QDockWidget subclass."""
        assert isinstance(panel, QDockWidget)

    def test_title(self, panel):
        """AiPanel has the title 'AI Chat'."""
        assert panel.windowTitle() == "AI Chat"

    def test_object_name(self, panel):
        """AiPanel has objectName 'AiPanel'."""
        assert panel.objectName() == "AiPanel"

    def test_allowed_areas_right(self, panel):
        """AiPanel allows docking to the right area."""
        assert panel.allowedAreas() & Qt.RightDockWidgetArea

    def test_allowed_areas_left(self, panel):
        """AiPanel allows docking to the left area."""
        assert panel.allowedAreas() & Qt.LeftDockWidgetArea

    def test_not_allowed_top(self, panel):
        """AiPanel does not allow docking to the top area."""
        assert not (panel.allowedAreas() & Qt.TopDockWidgetArea)

    def test_not_allowed_bottom(self, panel):
        """AiPanel does not allow docking to the bottom area."""
        assert not (panel.allowedAreas() & Qt.BottomDockWidgetArea)

    def test_feature_closable(self, panel):
        """AiPanel has the DockWidgetClosable feature."""
        assert panel.features() & QDockWidget.DockWidgetClosable

    def test_feature_movable(self, panel):
        """AiPanel has the DockWidgetMovable feature."""
        assert panel.features() & QDockWidget.DockWidgetMovable

    def test_feature_no_floating(self, panel):
        """AiPanel does not have the DockWidgetFloatable feature."""
        assert not (panel.features() & QDockWidget.DockWidgetFloatable)

    def test_has_inner_widget(self, panel):
        """AiPanel has a non-None inner widget."""
        assert panel.widget() is not None


# ===========================================================================
# ResultsPanel
# ===========================================================================


class TestResultsPanel:
    """Tests for ResultsPanel (Requirements 4.4, 5.1)."""

    @pytest.fixture
    def panel(self, qtbot):
        w = ResultsPanel()
        qtbot.addWidget(w)
        return w

    def test_is_qdockwidget(self, panel):
        """ResultsPanel is a QDockWidget subclass."""
        assert isinstance(panel, QDockWidget)

    def test_title(self, panel):
        """ResultsPanel has the title 'Results'."""
        assert panel.windowTitle() == "Results"

    def test_object_name(self, panel):
        """ResultsPanel has objectName 'ResultsPanel'."""
        assert panel.objectName() == "ResultsPanel"

    def test_allowed_areas_right(self, panel):
        """ResultsPanel allows docking to the right area."""
        assert panel.allowedAreas() & Qt.RightDockWidgetArea

    def test_allowed_areas_bottom(self, panel):
        """ResultsPanel allows docking to the bottom area."""
        assert panel.allowedAreas() & Qt.BottomDockWidgetArea

    def test_not_allowed_top(self, panel):
        """ResultsPanel does not allow docking to the top area."""
        assert not (panel.allowedAreas() & Qt.TopDockWidgetArea)

    def test_not_allowed_left(self, panel):
        """ResultsPanel does not allow docking to the left area."""
        assert not (panel.allowedAreas() & Qt.LeftDockWidgetArea)

    def test_feature_closable(self, panel):
        """ResultsPanel has the DockWidgetClosable feature."""
        assert panel.features() & QDockWidget.DockWidgetClosable

    def test_feature_movable(self, panel):
        """ResultsPanel has the DockWidgetMovable feature."""
        assert panel.features() & QDockWidget.DockWidgetMovable

    def test_feature_no_floating(self, panel):
        """ResultsPanel does not have the DockWidgetFloatable feature."""
        assert not (panel.features() & QDockWidget.DockWidgetFloatable)

    def test_results_widget_attribute_exists(self, panel):
        """ResultsPanel exposes a .results_widget attribute."""
        assert hasattr(panel, "results_widget")

    def test_results_widget_is_backtest_results_widget(self, panel):
        """ResultsPanel.results_widget is a BacktestResultsWidget instance."""
        assert isinstance(panel.results_widget, BacktestResultsWidget)

    def test_results_widget_is_inner_widget(self, panel):
        """ResultsPanel.results_widget is the QDockWidget's inner widget."""
        assert panel.widget() is panel.results_widget
