# Feature: pair-favorites
"""
Property-based tests for PairsSelectorDialog favorites functionality.
"""
import sys
import pytest
from unittest.mock import MagicMock
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.ui.dialogs.pairs_selector_dialog import PairsSelectorDialog


# ---------------------------------------------------------------------------
# Shared pair strategy — fixed small alphabet for fast tests
# ---------------------------------------------------------------------------

_pair_strategy = st.lists(
    st.sampled_from([
        "BTC/USDT", "ETH/USDT", "ADA/USDT", "SOL/USDT", "XRP/USDT",
        "DOT/USDT", "LINK/USDT", "AVAX/USDT", "MATIC/USDT", "BNB/USDT",
    ]),
    min_size=1, max_size=10, unique=True,
)


# ---------------------------------------------------------------------------
# Session-scoped QApplication fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qt_app():
    """Create (or reuse) a QApplication for the test session.

    PairsSelectorDialog is a QDialog, so a QApplication must exist before
    any QWidget is instantiated.
    """
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_mock_state():
    """Return a fresh MagicMock that mimics SettingsState without disk I/O."""
    state = MagicMock()
    state.toggle_favorite_pair = MagicMock()
    return state


def _get_visible_order(dialog):
    """Return the list of pairs in their current visible layout order."""
    widget_to_pair = {v: k for k, v in dialog.row_widgets.items()}
    order = []
    for i in range(dialog.checkboxes_layout.count()):
        item = dialog.checkboxes_layout.itemAt(i)
        if item and item.widget():
            pair = widget_to_pair.get(item.widget())
            if pair and dialog.row_widgets[pair].isVisible():
                order.append(pair)
    return order


# ---------------------------------------------------------------------------
# Property 1: Every pair has a FavoriteButton
# ---------------------------------------------------------------------------

@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(pairs=_pair_strategy)
def test_every_pair_has_a_favorite_button(qt_app, pairs):
    """Property 1: Every pair has a FavoriteButton.

    For any list of pairs passed as favorites (so they all appear in all_pairs),
    the dialog must have exactly one FavoriteButton per pair in all_pairs.

    Validates: Requirements 1.1, 1.5
    """
    mock_state = _make_mock_state()

    # Pass pairs as favorites so they are guaranteed to be in all_pairs
    dialog = PairsSelectorDialog(
        favorites=pairs,
        selected=[],
        settings_state=mock_state,
    )

    assert len(dialog.fav_buttons) == len(dialog.all_pairs), (
        f"Expected {len(dialog.all_pairs)} fav_buttons, "
        f"got {len(dialog.fav_buttons)}"
    )

    dialog.close()


# ---------------------------------------------------------------------------
# Property 2: FavoriteButton text reflects favorites state
# ---------------------------------------------------------------------------

@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(pairs=_pair_strategy)
def test_favorite_button_text_reflects_favorites_state(qt_app, pairs):
    """Property 2: FavoriteButton text reflects favorites state.

    For any pairs list and any favorites subset, each button text must be
    "♥" iff the pair is in favorites, and "♡" otherwise.

    Validates: Requirements 1.2, 1.3
    """
    mock_state = _make_mock_state()
    favorites = [p for i, p in enumerate(pairs) if i % 2 == 0]

    dialog = PairsSelectorDialog(
        favorites=favorites,
        selected=[],
        settings_state=mock_state,
    )

    favorites_set = set(favorites)
    for pair in dialog.all_pairs:
        if pair not in dialog.fav_buttons:
            continue
        btn_text = dialog.fav_buttons[pair].text()
        if pair in favorites_set:
            assert btn_text == "♥", (
                f"Pair {pair!r} is in favorites but button shows {btn_text!r}"
            )
        else:
            assert btn_text == "♡", (
                f"Pair {pair!r} is not in favorites but button shows {btn_text!r}"
            )

    dialog.close()


# ---------------------------------------------------------------------------
# Property 3: Toggle adds then removes (round-trip)
# ---------------------------------------------------------------------------

@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(pairs=_pair_strategy)
def test_toggle_adds_then_removes_round_trip(qt_app, pairs):
    """Property 3: Toggle adds then removes (round-trip).

    For any pair not currently in favorites, clicking its button once adds it;
    clicking again removes it. toggle_favorite_pair is called exactly twice.

    Validates: Requirements 2.1, 2.2, 2.3
    """
    mock_state = _make_mock_state()
    target_pair = pairs[0]

    dialog = PairsSelectorDialog(
        favorites=[],
        selected=[],
        settings_state=mock_state,
    )

    assert target_pair not in dialog.favorites, (
        f"{target_pair!r} should not be in favorites initially"
    )

    # First click — should add
    dialog._on_favorite_clicked(target_pair)
    assert target_pair in dialog.favorites, (
        f"{target_pair!r} should be in favorites after first click"
    )

    # Second click — should remove
    dialog._on_favorite_clicked(target_pair)
    assert target_pair not in dialog.favorites, (
        f"{target_pair!r} should not be in favorites after second click"
    )

    assert mock_state.toggle_favorite_pair.call_count == 2, (
        f"Expected toggle_favorite_pair called exactly twice, "
        f"got {mock_state.toggle_favorite_pair.call_count}"
    )

    dialog.close()


# ---------------------------------------------------------------------------
# Property 4: Favorites-first ordering
# ---------------------------------------------------------------------------

@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(pairs=_pair_strategy)
def test_favorites_first_ordering(qt_app, pairs):
    """Property 4: Displayed order is favorites-first, alphabetical within groups.

    For any pairs list and favorites subset, the visible row order must equal
    sorted(visible ∩ favorites) + sorted(visible − favorites).

    Validates: Requirements 2.4, 2.5, 4.1, 4.2, 4.3, 4.4
    """
    mock_state = _make_mock_state()
    favorites = [p for i, p in enumerate(pairs) if i % 2 == 0]

    dialog = PairsSelectorDialog(
        favorites=favorites,
        selected=[],
        settings_state=mock_state,
    )

    visible_order = _get_visible_order(dialog)
    favorites_set = set(favorites)

    expected_order = (
        sorted(p for p in visible_order if p in favorites_set)
        + sorted(p for p in visible_order if p not in favorites_set)
    )

    assert visible_order == expected_order, (
        f"Expected order: {expected_order}\n"
        f"Actual order:   {visible_order}"
    )

    dialog.close()
