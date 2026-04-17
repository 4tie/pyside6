"""
Tests for the Improve Tab UX feature.

Covers:
- Pure helper functions (_build_banner_message, _build_status_message)
- StepIndicator widget
- ContextBanner widget
- EmptyStatePanel widget
- ImprovePage button text, tooltips, subtitle labels
- No-configuration guard

Property tests use hypothesis.
Each property test is tagged with:
  # Feature: improve-tab-ux, Property {N}: {property_text}
"""
import sys
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# QApplication fixture (session-scoped so Qt is initialised once)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def qapp():
    """Provide a QApplication instance for the entire test session."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


# ---------------------------------------------------------------------------
# Helpers to build a minimal mock SettingsState
# ---------------------------------------------------------------------------


def _make_settings_state(user_data_path: str = "/some/valid/path"):
    """Return a MagicMock that quacks like SettingsState."""
    settings_obj = MagicMock()
    settings_obj.user_data_path = user_data_path

    settings_service = MagicMock()
    settings_service.load_settings.return_value = settings_obj

    state = MagicMock()
    state.settings_service = settings_service
    state.settings_changed = MagicMock()
    state.settings_changed.connect = MagicMock()
    return state


def _make_page(qapp, user_data_path: str = "/some/valid/path"):
    """Create an ImprovePage with a mocked SettingsState."""
    state = _make_settings_state(user_data_path=user_data_path)
    with (
        patch("app.ui.pages.improve_page.ImproveService") as mock_improve,
        patch("app.ui.pages.improve_page.BacktestService"),
        patch("app.ui.pages.improve_page.ResultsDiagnosisService"),
        patch("app.ui.pages.improve_page.RuleSuggestionService"),
    ):
        mock_improve.return_value.get_available_strategies.return_value = []
        mock_improve.return_value.get_strategy_runs.return_value = []
        from app.ui.pages.improve_page import ImprovePage
        return ImprovePage(state)


# ===========================================================================
# Task 1 — Pure helper functions
# ===========================================================================


class TestBuildBannerMessage:
    """Tests for _build_banner_message."""

    def test_returns_string_for_each_step(self):
        from app.ui.pages.improve_page import _build_banner_message, BANNER_MESSAGES
        for step in range(1, 6):
            result = _build_banner_message(step)
            assert isinstance(result, str)
            assert len(result) > 0

    def test_matches_banner_messages_dict(self):
        from app.ui.pages.improve_page import _build_banner_message, BANNER_MESSAGES
        for step in range(1, 6):
            assert _build_banner_message(step) == BANNER_MESSAGES[step]

    # Feature: improve-tab-ux, Property 2: Banner message matches active step
    @given(step=st.integers(min_value=1, max_value=5))
    @settings(max_examples=100)
    def test_property2_banner_message_matches_active_step(self, step):
        """Property 2: Banner message matches active step.

        Validates: Requirements 2.2, 2.3
        """
        from app.ui.pages.improve_page import _build_banner_message, BANNER_MESSAGES
        assert _build_banner_message(step) == BANNER_MESSAGES[step]


class TestBuildStatusMessage:
    """Tests for _build_status_message."""

    def test_analyze_loading(self):
        from app.ui.pages.improve_page import _build_status_message, _C_GREEN
        msg, color = _build_status_message("analyze_loading")
        assert "⏳" in msg
        assert color == _C_GREEN

    def test_analysis_complete_issues_contains_count(self):
        from app.ui.pages.improve_page import _build_status_message
        msg, _ = _build_status_message("analysis_complete_issues", n_issues=7)
        assert "7" in msg

    def test_analysis_complete_no_issues(self):
        from app.ui.pages.improve_page import _build_status_message, _C_GREEN_LIGHT
        msg, color = _build_status_message("analysis_complete_no_issues")
        assert "no issues" in msg.lower() or "healthy" in msg.lower()
        assert color == _C_GREEN_LIGHT

    def test_candidate_backtest_start(self):
        from app.ui.pages.improve_page import _build_status_message, _C_GREEN
        msg, color = _build_status_message("candidate_backtest_start")
        assert "⏳" in msg
        assert color == _C_GREEN

    def test_candidate_backtest_success(self):
        from app.ui.pages.improve_page import _build_status_message, _C_GREEN_LIGHT
        msg, color = _build_status_message("candidate_backtest_success")
        assert "✅" in msg
        assert color == _C_GREEN_LIGHT

    def test_candidate_backtest_failed(self):
        from app.ui.pages.improve_page import _build_status_message, _C_RED_LIGHT
        msg, color = _build_status_message("candidate_backtest_failed")
        assert "❌" in msg
        assert color == _C_RED_LIGHT

    def test_accept(self):
        from app.ui.pages.improve_page import _build_status_message, _C_GREEN_LIGHT
        msg, color = _build_status_message("accept")
        assert "✅" in msg
        assert color == _C_GREEN_LIGHT

    def test_reject(self):
        from app.ui.pages.improve_page import _build_status_message, _C_YELLOW
        msg, color = _build_status_message("reject")
        assert "↩" in msg
        assert color == _C_YELLOW

    def test_rollback(self):
        from app.ui.pages.improve_page import _build_status_message, _C_YELLOW
        msg, color = _build_status_message("rollback")
        assert "↩" in msg
        assert color == _C_YELLOW

    # Feature: improve-tab-ux, Property 4: Status message includes issue count
    @given(n_issues=st.integers(min_value=1, max_value=10000))
    @settings(max_examples=100)
    def test_property4_status_message_includes_issue_count(self, n_issues):
        """Property 4: Status message includes issue count.

        Validates: Requirements 7.2
        """
        from app.ui.pages.improve_page import _build_status_message
        msg, _ = _build_status_message("analysis_complete_issues", n_issues)
        assert str(n_issues) in msg


# ===========================================================================
# Task 2 — StepIndicator widget
# ===========================================================================


class TestStepIndicator:
    """Tests for StepIndicator widget."""

    def test_initial_active_step_is_1(self, qapp):
        from app.ui.pages.improve_page import StepIndicator
        widget = StepIndicator()
        labels = widget._node_labels
        assert len(labels) == 5
        # Active node (1) should have bold styling
        active_style = labels[0].styleSheet()
        assert "bold" in active_style or "font-weight" in active_style

    def test_set_active_step_marks_correct_node(self, qapp):
        from app.ui.pages.improve_page import StepIndicator
        widget = StepIndicator()
        for active in range(1, 6):
            widget.set_active_step(active)
            labels = widget._node_labels
            for i, lbl in enumerate(labels):
                step_num = i + 1
                style = lbl.styleSheet()
                text = lbl.text()
                if step_num < active:
                    assert "✓" in text, (
                        f"Step {step_num} should have ✓ prefix when active={active}"
                    )
                elif step_num == active:
                    assert "bold" in style or "font-weight" in style, (
                        f"Step {step_num} should be bold when active={active}"
                    )
                else:
                    assert "✓" not in text, (
                        f"Step {step_num} should not have ✓ when active={active}"
                    )

    def test_reset_to_step_1_after_step_5(self, qapp):
        from app.ui.pages.improve_page import StepIndicator
        widget = StepIndicator()
        widget.set_active_step(5)
        widget.set_active_step(1)
        labels = widget._node_labels
        # Node 1 should be active (bold)
        assert "bold" in labels[0].styleSheet() or "font-weight" in labels[0].styleSheet()
        # Nodes 2-5 should be pending (no checkmark)
        for lbl in labels[1:]:
            assert "✓" not in lbl.text()

    # Feature: improve-tab-ux, Property 1: Step indicator resets after accept or reject
    @given(initial_step=st.integers(min_value=1, max_value=5))
    @settings(max_examples=50)
    def test_property1_step_indicator_resets_after_accept_or_reject(self, qapp, initial_step):
        """Property 1: Step indicator resets after accept or reject.

        Validates: Requirements 1.8
        """
        from app.ui.pages.improve_page import StepIndicator
        widget = StepIndicator()
        widget.set_active_step(initial_step)
        # Simulate accept/reject → reset to step 1
        widget.set_active_step(1)
        labels = widget._node_labels
        # Node 1 is active
        assert "bold" in labels[0].styleSheet() or "font-weight" in labels[0].styleSheet()
        # All other nodes are pending
        for lbl in labels[1:]:
            assert "✓" not in lbl.text()


# ===========================================================================
# Task 3 — ContextBanner widget
# ===========================================================================


class TestContextBanner:
    """Tests for ContextBanner widget."""

    def test_set_step_updates_label_text(self, qapp):
        from app.ui.pages.improve_page import ContextBanner, BANNER_MESSAGES
        banner = ContextBanner()
        for step in range(1, 6):
            banner.set_step(step)
            assert banner._msg_lbl.text() == BANNER_MESSAGES[step]

    def test_dismiss_hides_widget(self, qapp):
        from app.ui.pages.improve_page import ContextBanner
        banner = ContextBanner()
        banner.show()
        banner._dismiss_btn.click()
        assert not banner.isVisible()
        assert banner.is_dismissed()

    def test_set_step_after_dismiss_does_not_change_text(self, qapp):
        from app.ui.pages.improve_page import ContextBanner, BANNER_MESSAGES
        banner = ContextBanner()
        banner.set_step(1)
        original_text = banner._msg_lbl.text()
        banner._dismiss_btn.click()
        banner.set_step(3)
        assert banner._msg_lbl.text() == original_text

    def test_set_step_after_dismiss_does_not_show_widget(self, qapp):
        from app.ui.pages.improve_page import ContextBanner
        banner = ContextBanner()
        banner._dismiss_btn.click()
        banner.set_step(2)
        assert not banner.isVisible()

    def test_is_dismissed_false_initially(self, qapp):
        from app.ui.pages.improve_page import ContextBanner
        banner = ContextBanner()
        assert not banner.is_dismissed()

    # Feature: improve-tab-ux, Property 3: Dismissed banner stays hidden across all step changes
    @given(steps=st.lists(st.integers(min_value=1, max_value=5), min_size=1, max_size=20))
    @settings(max_examples=100)
    def test_property3_dismissed_banner_stays_hidden(self, qapp, steps):
        """Property 3: Dismissed banner stays hidden across all step changes.

        Validates: Requirements 2.5
        """
        from app.ui.pages.improve_page import ContextBanner
        banner = ContextBanner()
        banner.show()
        banner._dismiss_btn.click()
        for step in steps:
            banner.set_step(step)
            assert not banner.isVisible()


# ===========================================================================
# Task 4 — EmptyStatePanel widget
# ===========================================================================


class TestEmptyStatePanel:
    """Tests for EmptyStatePanel widget."""

    def test_icon_text_hint_labels_present(self, qapp):
        from app.ui.pages.improve_page import EmptyStatePanel
        panel = EmptyStatePanel("📊", "No run loaded yet", "Click Analyze to start.")
        assert panel._icon_lbl.text() == "📊"
        assert panel._text_lbl.text() == "No run loaded yet"
        assert panel._hint_lbl.text() == "Click Analyze to start."

    def test_minimum_height(self, qapp):
        from app.ui.pages.improve_page import EmptyStatePanel
        panel = EmptyStatePanel("🔍", "Issues here", "Hint text")
        assert panel.minimumHeight() >= 80

    def test_various_icons_and_texts(self, qapp):
        from app.ui.pages.improve_page import EmptyStatePanel
        cases = [
            ("🔍", "Issues will appear here after analysis", "Click Analyze to scan your backtest results."),
            ("💡", "Suggestions will appear here after analysis", "Each suggestion targets a specific performance issue."),
            ("⚙️", "No changes applied yet", "Click Apply on a suggestion above to start building your candidate."),
            ("⚖️", "Comparison will appear after the candidate backtest", "Apply suggestions and run the candidate backtest to see results here."),
        ]
        for icon, text, hint in cases:
            panel = EmptyStatePanel(icon, text, hint)
            assert panel._icon_lbl.text() == icon
            assert panel._text_lbl.text() == text
            assert panel._hint_lbl.text() == hint


# ===========================================================================
# Task 7 — Button text and tooltip values
# ===========================================================================


class TestImprovePageButtonsAndTooltips:
    """Tests for button text and tooltip values on ImprovePage."""

    @pytest.fixture()
    def page(self, qapp):
        """Create an ImprovePage with a mocked SettingsState."""
        p = _make_page(qapp)
        yield p
        p.deleteLater()

    def test_analyze_btn_text(self, page):
        assert page.analyze_btn.text() == "⚡ Analyze Run"

    def test_load_latest_btn_text(self, page):
        assert page.load_latest_btn.text() == "↓ Load Latest Run"

    def test_accept_btn_text(self, page):
        assert page.accept_btn.text() == "✅ Accept & Save"

    def test_reject_btn_text(self, page):
        assert page.reject_btn.text() == "✕ Reject & Discard"

    def test_rollback_btn_text(self, page):
        assert page.rollback_btn.text() == "↩ Rollback to Previous"

    def test_strategy_combo_tooltip(self, page):
        assert "strategy" in page.strategy_combo.toolTip().lower()

    def test_run_combo_tooltip(self, page):
        assert "run" in page.run_combo.toolTip().lower()

    def test_analyze_btn_tooltip(self, page):
        assert len(page.analyze_btn.toolTip()) > 0

    def test_load_latest_btn_tooltip(self, page):
        assert len(page.load_latest_btn.toolTip()) > 0

    def test_accept_btn_tooltip(self, page):
        assert len(page.accept_btn.toolTip()) > 0

    def test_reject_btn_tooltip(self, page):
        assert len(page.reject_btn.toolTip()) > 0

    def test_rollback_btn_tooltip(self, page):
        assert len(page.rollback_btn.toolTip()) > 0


# ===========================================================================
# Task 8 — Subtitle label text
# ===========================================================================


class TestSubtitleLabels:
    """Tests for subtitle labels in group boxes."""

    @pytest.fixture()
    def page(self, qapp):
        p = _make_page(qapp)
        yield p
        p.deleteLater()

    def _first_label_text(self, layout) -> str:
        """Return the text of the first QLabel in a layout."""
        from PySide6.QtWidgets import QLabel
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), QLabel):
                return item.widget().text()
        return ""

    def test_issues_group_subtitle(self, page):
        text = self._first_label_text(page._issues_layout)
        assert "Issues found" in text or "baseline run" in text

    def test_suggestions_group_subtitle(self, page):
        text = self._first_label_text(page._suggestions_layout)
        assert "Rule-based" in text or "parameter changes" in text

    def test_candidate_group_subtitle(self, page):
        text = self._first_label_text(page._candidate_layout)
        assert "Parameters" in text or "changed from the baseline" in text

    def test_comparison_group_subtitle(self, page):
        text = self._first_label_text(page._comparison_layout)
        assert "Side-by-side" in text or "baseline and candidate" in text


# ===========================================================================
# Task 14 — No-configuration guard
# ===========================================================================


class TestNoConfigGuard:
    """Tests for the no-configuration guard."""

    def test_banner_visible_when_no_path(self, qapp):
        page = _make_page(qapp, "")
        assert not page._no_config_banner.isHidden()
        page.deleteLater()

    def test_banner_hidden_when_path_set(self, qapp):
        page = _make_page(qapp, "/valid/path")
        assert page._no_config_banner.isHidden()
        page.deleteLater()

    def test_controls_disabled_when_no_path(self, qapp):
        page = _make_page(qapp, "")
        assert not page.strategy_combo.isEnabled()
        assert not page.run_combo.isEnabled()
        assert not page.load_latest_btn.isEnabled()
        assert not page.analyze_btn.isEnabled()
        page.deleteLater()

    def test_controls_enabled_when_path_set(self, qapp):
        page = _make_page(qapp, "/valid/path")
        assert page.strategy_combo.isEnabled()
        assert page.run_combo.isEnabled()
        assert page.load_latest_btn.isEnabled()
        page.deleteLater()

    # Feature: improve-tab-ux, Property 5: Controls disabled when user_data_path is unconfigured
    @given(user_data_path=st.one_of(st.just(""), st.just(None), st.text(max_size=0)))
    @settings(max_examples=50)
    def test_property5_controls_disabled_when_unconfigured(self, qapp, user_data_path):
        """Property 5: Controls disabled when user_data_path is unconfigured.

        Validates: Requirements 8.3
        """
        path = user_data_path or ""
        page = _make_page(qapp, path)
        assert not page.strategy_combo.isEnabled()
        assert not page.run_combo.isEnabled()
        assert not page.load_latest_btn.isEnabled()
        assert not page.analyze_btn.isEnabled()
        page.deleteLater()