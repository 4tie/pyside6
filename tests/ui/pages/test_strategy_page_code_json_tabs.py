"""Tests for the Code and JSON viewer tabs in StrategyPage."""
import json

import pytest
from PySide6.QtCore import Qt

from app.app_state.settings_state import SettingsState


@pytest.fixture()
def user_data(tmp_path):
    """Minimal user_data with one strategy that has both .py and .json, and one without .json."""
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir()

    (strategies_dir / "TestStrategy.py").write_text(
        "# Test Strategy\nclass TestStrategy:\n    pass\n",
        encoding="utf-8",
    )
    (strategies_dir / "TestStrategy.json").write_text(
        json.dumps({"strategy_name": "TestStrategy", "params": {"stoploss": {"stoploss": -0.1}}}),
        encoding="utf-8",
    )
    (strategies_dir / "NoJsonStrategy.py").write_text(
        "class NoJsonStrategy:\n    pass\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture()
def strategy_page(qtbot, user_data):
    from app.ui.pages.strategy_page import StrategyPage

    settings_state = SettingsState()
    settings_state.load_settings()
    settings_state.current_settings.user_data_path = str(user_data)

    page = StrategyPage(settings_state)
    qtbot.addWidget(page)
    return page


def _select(strategy_page, name: str) -> None:
    lst = strategy_page._strategy_list
    for i in range(lst.count()):
        item = lst.item(i)
        if item.data(Qt.UserRole) == name:
            lst.setCurrentItem(item)
            return
    raise ValueError(f"{name!r} not found in strategy list")


# ---------------------------------------------------------------------------
# Tab presence & order
# ---------------------------------------------------------------------------

def test_code_tab_exists(strategy_page):
    labels = [strategy_page._detail_tabs.tabText(i) for i in range(strategy_page._detail_tabs.count())]
    assert "Code" in labels


def test_json_tab_exists(strategy_page):
    labels = [strategy_page._detail_tabs.tabText(i) for i in range(strategy_page._detail_tabs.count())]
    assert "JSON" in labels


def test_tab_order(strategy_page):
    labels = [strategy_page._detail_tabs.tabText(i) for i in range(strategy_page._detail_tabs.count())]
    assert labels.index("Code") < labels.index("JSON")
    assert labels.index("JSON") < labels.index("History")


# ---------------------------------------------------------------------------
# Viewer properties
# ---------------------------------------------------------------------------

def test_code_viewer_is_readonly(strategy_page):
    assert strategy_page._code_viewer.isReadOnly()


def test_json_viewer_is_readonly(strategy_page):
    assert strategy_page._json_viewer.isReadOnly()


# ---------------------------------------------------------------------------
# Content loading
# ---------------------------------------------------------------------------

def test_code_viewer_loads_py_content(qtbot, strategy_page):
    strategy_page.refresh()
    _select(strategy_page, "TestStrategy")
    qtbot.wait(50)
    content = strategy_page._code_viewer.toPlainText()
    assert "# Test Strategy" in content
    assert "class TestStrategy:" in content


def test_json_viewer_loads_json_content(qtbot, strategy_page):
    strategy_page.refresh()
    _select(strategy_page, "TestStrategy")
    qtbot.wait(50)
    content = strategy_page._json_viewer.toPlainText()
    assert "TestStrategy" in content
    assert "stoploss" in content


def test_json_viewer_pretty_prints(qtbot, strategy_page):
    strategy_page.refresh()
    _select(strategy_page, "TestStrategy")
    qtbot.wait(50)
    content = strategy_page._json_viewer.toPlainText()
    assert "\n" in content  # indented = multi-line


def test_json_viewer_missing_json_shows_message(qtbot, strategy_page):
    strategy_page.refresh()
    _select(strategy_page, "NoJsonStrategy")
    qtbot.wait(50)
    content = strategy_page._json_viewer.toPlainText()
    assert "No JSON file found" in content


def test_switching_strategy_updates_code_viewer(qtbot, strategy_page):
    strategy_page.refresh()
    _select(strategy_page, "TestStrategy")
    qtbot.wait(50)
    first = strategy_page._code_viewer.toPlainText()

    _select(strategy_page, "NoJsonStrategy")
    qtbot.wait(50)
    second = strategy_page._code_viewer.toPlainText()

    assert first != second
    assert "NoJsonStrategy" in second
