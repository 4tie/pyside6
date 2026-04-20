"""Unit tests for the v2 shell components.

Covers:
- NavSidebar: nav items, set_active, collapse toggle, signal emission
- HeaderBar: set_page_title, theme toggle, signal emission
- AppStatusBar: set_status, auto-clear timer, level colours

Requirements: 2.1, 2.3, 2.6, 2.7, 3.2, 9.1, 16.2, 18.1, 18.5
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt

from app.ui_v2.shell.sidebar import NavSidebar, NavItem, _NAV_ITEMS, _COLLAPSED_WIDTH, _EXPANDED_WIDTH
from app.ui_v2.shell.header_bar import HeaderBar
from app.ui_v2.shell.status_bar import AppStatusBar
from app.ui_v2.theme import ThemeMode


# ===========================================================================
# NavSidebar
# ===========================================================================


class TestNavSidebar:
    """Tests for NavSidebar."""

    @pytest.fixture
    def sidebar(self, qtbot):
        w = NavSidebar()
        qtbot.addWidget(w)
        w.show()
        return w

    def test_has_six_nav_items(self, sidebar):
        """Sidebar contains exactly six nav items."""
        assert len(sidebar._items) == 6

    def test_nav_item_page_ids(self, sidebar):
        """Sidebar contains items for all expected page ids."""
        expected = {"dashboard", "backtest", "optimize", "download", "strategy", "settings"}
        assert set(sidebar._items.keys()) == expected

    def test_nav_items_in_correct_order(self, sidebar):
        """Nav items are in the order defined by _NAV_ITEMS."""
        expected_order = [pid for pid, _, _ in _NAV_ITEMS]
        assert list(sidebar._items.keys()) == expected_order

    def test_initial_object_name_is_nav_item(self, sidebar):
        """All items start with objectName 'nav_item'."""
        for item in sidebar._items.values():
            assert item.objectName() == "nav_item"

    def test_set_active_updates_active_item(self, sidebar):
        """set_active sets objectName to 'nav_item_active' for the target item."""
        sidebar.set_active("backtest")
        assert sidebar._items["backtest"].objectName() == "nav_item_active"

    def test_set_active_clears_other_items(self, sidebar):
        """set_active resets all other items to 'nav_item'."""
        sidebar.set_active("optimize")
        for pid, item in sidebar._items.items():
            if pid == "optimize":
                assert item.objectName() == "nav_item_active"
            else:
                assert item.objectName() == "nav_item"

    def test_set_active_can_switch_between_pages(self, sidebar):
        """set_active can be called multiple times to switch active page."""
        sidebar.set_active("dashboard")
        assert sidebar._items["dashboard"].objectName() == "nav_item_active"
        sidebar.set_active("settings")
        assert sidebar._items["settings"].objectName() == "nav_item_active"
        assert sidebar._items["dashboard"].objectName() == "nav_item"

    def test_nav_item_clicked_signal_emitted(self, qtbot, sidebar):
        """Clicking a nav item emits nav_item_clicked with the correct page id."""
        with qtbot.waitSignal(sidebar.nav_item_clicked, timeout=1000) as blocker:
            sidebar._items["backtest"].click()
        assert blocker.args == ["backtest"]

    def test_nav_item_clicked_for_each_page(self, qtbot, sidebar):
        """nav_item_clicked emits the correct page id for each item."""
        for page_id in sidebar._items:
            received = []
            sidebar.nav_item_clicked.connect(received.append)
            sidebar._items[page_id].click()
            sidebar.nav_item_clicked.disconnect()
            assert page_id in received

    def test_initial_width_is_expanded(self, sidebar):
        """Sidebar starts at expanded width."""
        assert sidebar.width() == _EXPANDED_WIDTH

    def test_collapse_toggle_reduces_max_width(self, qtbot, sidebar):
        """Clicking the collapse toggle starts the collapse animation."""
        assert not sidebar.is_collapsed()
        sidebar._toggle_btn.click()
        assert sidebar.is_collapsed()

    def test_expand_toggle_restores_expanded_state(self, qtbot, sidebar):
        """Clicking toggle twice returns to expanded state."""
        sidebar._toggle_btn.click()  # collapse
        sidebar._toggle_btn.click()  # expand
        assert not sidebar.is_collapsed()

    def test_collapse_hides_labels(self, sidebar):
        """Collapsing hides text labels on all nav items."""
        sidebar._toggle_btn.click()
        for item in sidebar._items.values():
            assert not item._text_lbl.isVisible()

    def test_expand_shows_labels(self, sidebar):
        """Expanding shows text labels on all nav items."""
        sidebar._toggle_btn.click()  # collapse
        sidebar._toggle_btn.click()  # expand
        for item in sidebar._items.values():
            assert item._text_lbl.isVisible()


# ===========================================================================
# NavItem
# ===========================================================================


class TestNavItem:
    """Tests for the NavItem inner class."""

    @pytest.fixture
    def item(self, qtbot):
        w = NavItem(icon="🏠", label="Dashboard", page_id="dashboard")
        qtbot.addWidget(w)
        w.show()
        return w

    def test_page_id_stored(self, item):
        """NavItem stores the page_id attribute."""
        assert item.page_id == "dashboard"

    def test_default_object_name(self, item):
        """NavItem starts with objectName 'nav_item'."""
        assert item.objectName() == "nav_item"

    def test_accessible_name(self, item):
        """NavItem has accessible name set to the label."""
        assert item.accessibleName() == "Dashboard"

    def test_tooltip(self, item):
        """NavItem has tooltip set to the label."""
        assert item.toolTip() == "Dashboard"

    def test_show_label_false_hides_text(self, item):
        """show_label(False) hides the text label."""
        item.show_label(False)
        assert not item._text_lbl.isVisible()

    def test_show_label_true_shows_text(self, item):
        """show_label(True) shows the text label."""
        item.show_label(False)
        item.show_label(True)
        assert item._text_lbl.isVisible()

    def test_icon_label_always_visible(self, item):
        """Icon label remains visible after show_label(False)."""
        item.show_label(False)
        assert item._icon_lbl.isVisible()


# ===========================================================================
# HeaderBar
# ===========================================================================


class TestHeaderBar:
    """Tests for HeaderBar."""

    @pytest.fixture
    def header(self, qtbot):
        w = HeaderBar()
        qtbot.addWidget(w)
        w.show()
        return w

    def test_fixed_height(self, header):
        """HeaderBar has a fixed height of 48 px."""
        assert header.height() == 48

    def test_initial_page_title(self, header):
        """HeaderBar shows 'Dashboard' as the initial page title."""
        assert header._page_title_lbl.text() == "Dashboard"

    def test_set_page_title_updates_label(self, header):
        """set_page_title updates the breadcrumb label."""
        header.set_page_title("Backtest")
        assert header._page_title_lbl.text() == "Backtest"

    def test_set_page_title_arbitrary_string(self, header):
        """set_page_title accepts any string."""
        header.set_page_title("My Custom Page")
        assert header._page_title_lbl.text() == "My Custom Page"

    def test_initial_theme_is_dark(self, header):
        """HeaderBar starts in dark mode."""
        assert header.current_theme_mode() == ThemeMode.DARK

    def test_theme_toggle_switches_to_light(self, header):
        """Clicking theme toggle switches to light mode."""
        header._theme_btn.click()
        assert header.current_theme_mode() == ThemeMode.LIGHT

    def test_theme_toggle_cycles_back_to_dark(self, header):
        """Clicking theme toggle twice returns to dark mode."""
        header._theme_btn.click()
        header._theme_btn.click()
        assert header.current_theme_mode() == ThemeMode.DARK

    def test_theme_changed_signal_emitted(self, qtbot, header):
        """theme_changed signal is emitted when theme is toggled."""
        with qtbot.waitSignal(header.theme_changed, timeout=1000) as blocker:
            header._theme_btn.click()
        assert blocker.args[0] == ThemeMode.LIGHT

    def test_command_palette_signal_emitted(self, qtbot, header):
        """command_palette_requested signal is emitted when 🔍 is clicked."""
        with qtbot.waitSignal(header.command_palette_requested, timeout=1000):
            header._cmd_btn.click()

    def test_settings_signal_emitted(self, qtbot, header):
        """settings_requested signal is emitted when ⚙ is clicked."""
        with qtbot.waitSignal(header.settings_requested, timeout=1000):
            header._settings_btn.click()

    def test_page_title_object_name(self, header):
        """Page title label has objectName 'page_title' for QSS styling."""
        assert header._page_title_lbl.objectName() == "page_title"

    def test_theme_toggle_applies_stylesheet(self, header, qtbot):
        """Theme toggle calls QApplication.setStyleSheet."""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        header._theme_btn.click()
        # After toggle, stylesheet should be non-empty
        assert len(app.styleSheet()) > 0


# ===========================================================================
# AppStatusBar
# ===========================================================================


class TestAppStatusBar:
    """Tests for AppStatusBar."""

    @pytest.fixture
    def status_bar(self, qtbot):
        w = AppStatusBar()
        qtbot.addWidget(w)
        w.show()
        return w

    def test_fixed_height(self, status_bar):
        """AppStatusBar has a fixed height of 24 px."""
        assert status_bar.height() == 24

    def test_initial_message_is_empty(self, status_bar):
        """AppStatusBar starts with no message displayed."""
        assert status_bar._msg_lbl.text() == ""

    def test_set_status_displays_message(self, status_bar):
        """set_status displays the provided message."""
        status_bar.set_status("Backtest running")
        assert status_bar._msg_lbl.text() == "Backtest running"

    def test_set_status_displays_timestamp(self, status_bar):
        """set_status populates the timestamp label."""
        status_bar.set_status("Test message")
        assert status_bar._ts_lbl.text() != ""

    def test_set_status_default_level_is_info(self, status_bar):
        """set_status with no level argument defaults to 'info'."""
        status_bar.set_status("Hello")
        # Info colour should be in the stylesheet
        assert "#d4d4d4" in status_bar._msg_lbl.styleSheet()

    def test_set_status_error_level(self, status_bar):
        """set_status with level='error' applies error colour."""
        status_bar.set_status("Something failed", level="error")
        assert "#f44747" in status_bar._msg_lbl.styleSheet()

    def test_set_status_success_level(self, status_bar):
        """set_status with level='success' applies success colour."""
        status_bar.set_status("Done!", level="success")
        assert "#4ec9a0" in status_bar._msg_lbl.styleSheet()

    def test_set_status_warning_level(self, status_bar):
        """set_status with level='warning' applies warning colour."""
        status_bar.set_status("Watch out", level="warning")
        assert "#ce9178" in status_bar._msg_lbl.styleSheet()

    def test_set_status_unknown_level_falls_back_to_info(self, status_bar):
        """set_status with an unknown level falls back to info colour."""
        status_bar.set_status("Hmm", level="unknown_level")
        assert "#d4d4d4" in status_bar._msg_lbl.styleSheet()

    def test_auto_clear_timer_is_single_shot(self, status_bar):
        """The auto-clear timer is configured as single-shot."""
        assert status_bar._clear_timer.isSingleShot()

    def test_auto_clear_timer_interval(self, status_bar):
        """The auto-clear timer interval is 10 000 ms."""
        assert status_bar._clear_timer.interval() == 10_000

    def test_set_status_starts_timer(self, status_bar):
        """set_status starts the auto-clear timer."""
        status_bar.set_status("Running")
        assert status_bar._clear_timer.isActive()

    def test_clear_message_empties_labels(self, status_bar):
        """_clear_message empties both the message and timestamp labels."""
        status_bar.set_status("Something")
        status_bar._clear_message()
        assert status_bar._msg_lbl.text() == ""
        assert status_bar._ts_lbl.text() == ""

    def test_set_status_restarts_timer_on_second_call(self, status_bar):
        """Calling set_status twice restarts the timer."""
        status_bar.set_status("First")
        status_bar.set_status("Second")
        # Timer should still be active (restarted)
        assert status_bar._clear_timer.isActive()
        assert status_bar._msg_lbl.text() == "Second"
