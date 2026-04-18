# Feature: pair-favorites
"""
Property-based tests for PairsSelectorDialog favorites functionality.
"""
import sys
import pytest
from unittest.mock import MagicMock, patch
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

import app.ui.dialogs.pairs_selector_dialog as _dialog_module
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


def _make_dialog(pairs, selected=None, favorites=None, max_open_trades=1):
    """Create a PairsSelectorDialog with ONLY the given pairs (no BINANCE list).

    Patches BINANCE_USDT_PAIRS to [] so all_pairs == sorted(set(pairs)).
    This keeps widget count small and prevents Qt emoji-button crashes in tests.
    """
    with patch.object(_dialog_module, "BINANCE_USDT_PAIRS", []):
        dialog = PairsSelectorDialog(
            favorites=favorites or [],
            selected=selected or [],
            settings_state=_make_mock_state(),
            max_open_trades=max_open_trades,
        )
    return dialog


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


# ===========================================================================
# Task 9: Property-based tests for _randomize_pairs logic
# ===========================================================================

# ---------------------------------------------------------------------------
# Property 2: Lock preservation
# ---------------------------------------------------------------------------

@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    pairs=_pair_strategy,
    locked_indices=st.lists(st.integers(min_value=0, max_value=9), unique=True),
    max_open_trades=st.integers(min_value=1, max_value=10),
)
def test_randomize_lock_preservation(qt_app, pairs, locked_indices, max_open_trades):
    """Property 2: Lock preservation — locked visible pairs always appear in selection.

    For any pairs list, any locked subset, and any max_open_trades, every pair
    that is both locked and visible must be present in dialog.selected after
    calling _randomize_pairs().

    Validates: Requirement 4.1
    """
    locked = [pairs[i] for i in locked_indices if i < len(pairs)]

    dialog = _make_dialog(pairs, max_open_trades=max_open_trades)

    dialog.locked_pairs = set(locked)
    dialog._randomize_pairs()

    visible_pairs = {
        p for p in dialog.all_pairs
        if p in dialog.row_widgets and dialog.row_widgets[p].isVisible()
    }
    locked_visible = set(locked) & visible_pairs

    for pair in locked_visible:
        assert pair in dialog.selected, (
            f"Locked visible pair {pair!r} missing from selection after randomize. "
            f"locked_pairs={locked}, selected={dialog.selected}"
        )

    dialog.close()


# ---------------------------------------------------------------------------
# Property 3: Selection size equals max_open_trades when pool is large enough
# ---------------------------------------------------------------------------

@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(pairs=_pair_strategy)
def test_randomize_selection_size_equals_max_open_trades(qt_app, pairs):
    """Property 3: Selection size equals max_open_trades when pool is large enough.

    With no locked pairs and max_open_trades <= len(pairs), the selection after
    _randomize_pairs() must contain exactly max_open_trades pairs.

    Validates: Requirements 4.2, 4.6
    """
    max_open_trades = len(pairs)  # pool == max_open_trades, always large enough

    dialog = _make_dialog(pairs, max_open_trades=max_open_trades)

    # No locked pairs — entire visible set is the pool
    dialog.locked_pairs = set()
    dialog._randomize_pairs()

    visible_count = sum(
        1 for p in dialog.all_pairs
        if p in dialog.row_widgets and dialog.row_widgets[p].isVisible()
        and p in pairs
    )

    # Only assert when there are enough visible pairs from our list
    if visible_count >= max_open_trades:
        assert len(dialog.selected) == max_open_trades, (
            f"Expected {max_open_trades} selected pairs, got {len(dialog.selected)}. "
            f"pairs={pairs}, selected={dialog.selected}"
        )

    dialog.close()


# ---------------------------------------------------------------------------
# Property 4: All pool pairs included when pool < slots
# ---------------------------------------------------------------------------

@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    pairs=_pair_strategy,
    locked_indices=st.lists(st.integers(min_value=0, max_value=9), unique=True),
)
def test_randomize_all_pool_included_when_pool_smaller_than_slots(qt_app, pairs, locked_indices):
    """Property 4: All pool pairs included when pool < slots_needed.

    When max_open_trades is larger than the total number of visible pairs,
    every unlocked visible pair must appear in the selection.

    Validates: Requirement 4.3
    """
    locked = [pairs[i] for i in locked_indices if i < len(pairs)]
    # Use a max_open_trades larger than all pairs to guarantee pool < slots
    max_open_trades = len(pairs) + 10

    dialog = _make_dialog(pairs, max_open_trades=max_open_trades)

    dialog.locked_pairs = set(locked)
    dialog._randomize_pairs()

    visible_pairs = [
        p for p in dialog.all_pairs
        if p in dialog.row_widgets and dialog.row_widgets[p].isVisible()
    ]
    pool = [p for p in visible_pairs if p not in dialog.locked_pairs]

    for pair in pool:
        assert pair in dialog.selected, (
            f"Pool pair {pair!r} missing from selection when pool < slots. "
            f"pool={pool}, selected={dialog.selected}"
        )

    dialog.close()


# ---------------------------------------------------------------------------
# Property 5: Only locked pairs selected when slots_needed <= 0
# ---------------------------------------------------------------------------

@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(pairs=_pair_strategy)
def test_randomize_only_locked_when_slots_needed_zero_or_less(qt_app, pairs):
    """Property 5: Only locked visible pairs selected when slots_needed <= 0.

    When len(locked_visible) >= max_open_trades, slots_needed <= 0 and the
    selection must equal exactly the locked visible pairs.

    Validates: Requirement 4.4
    """
    # Lock all pairs so slots_needed = max_open_trades - len(pairs) <= 0
    max_open_trades = max(1, len(pairs) - 1)  # always <= len(locked)

    dialog = _make_dialog(pairs, max_open_trades=max_open_trades)

    dialog.locked_pairs = set(pairs)  # lock everything
    dialog._randomize_pairs()

    visible_pairs = {
        p for p in dialog.all_pairs
        if p in dialog.row_widgets and dialog.row_widgets[p].isVisible()
    }
    locked_visible = set(pairs) & visible_pairs

    assert dialog.selected == locked_visible, (
        f"Expected selection == locked_visible={locked_visible}, "
        f"got selected={dialog.selected}"
    )

    dialog.close()


# ---------------------------------------------------------------------------
# Property 6: No duplicates in selection
# ---------------------------------------------------------------------------

@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    pairs=_pair_strategy,
    locked_indices=st.lists(st.integers(min_value=0, max_value=9), unique=True),
    max_open_trades=st.integers(min_value=1, max_value=10),
)
def test_randomize_no_duplicates_in_selection(qt_app, pairs, locked_indices, max_open_trades):
    """Property 6: No duplicates in selection.

    After _randomize_pairs(), get_selected_pairs() must return a list with no
    duplicate entries.

    Validates: Requirement 4.7
    """
    locked = [pairs[i] for i in locked_indices if i < len(pairs)]

    dialog = _make_dialog(pairs, max_open_trades=max_open_trades)

    dialog.locked_pairs = set(locked)
    dialog._randomize_pairs()

    selected_list = dialog.get_selected_pairs()
    assert len(selected_list) == len(set(selected_list)), (
        f"Duplicates found in get_selected_pairs(): {selected_list}"
    )

    dialog.close()


# ---------------------------------------------------------------------------
# Property 7: Selection is a subset of all_pairs
# ---------------------------------------------------------------------------

@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    pairs=_pair_strategy,
    locked_indices=st.lists(st.integers(min_value=0, max_value=9), unique=True),
    max_open_trades=st.integers(min_value=1, max_value=10),
)
def test_randomize_selection_subset_of_all_pairs(qt_app, pairs, locked_indices, max_open_trades):
    """Property 7: Selection is a subset of all_pairs.

    After _randomize_pairs(), every pair in dialog.selected must be present in
    dialog.all_pairs.

    Validates: Requirement 4.5
    """
    locked = [pairs[i] for i in locked_indices if i < len(pairs)]

    dialog = _make_dialog(pairs, max_open_trades=max_open_trades)

    dialog.locked_pairs = set(locked)
    dialog._randomize_pairs()

    assert dialog.selected.issubset(set(dialog.all_pairs)), (
        f"Selection contains pairs not in all_pairs. "
        f"extra={dialog.selected - set(dialog.all_pairs)}"
    )

    dialog.close()


# ===========================================================================
# Task 10: Property-based tests for lock toggle behaviour
# ===========================================================================

# ---------------------------------------------------------------------------
# Property 8: Locking a pair adds it to locked_pairs and checks it
# ---------------------------------------------------------------------------

@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(pairs=_pair_strategy)
def test_lock_adds_to_locked_pairs_and_checks_checkbox(qt_app, pairs):
    """Property 8: Locking a pair adds it to locked_pairs and checks its checkbox.

    For any pairs list, clicking the lock button on an unlocked pair must add
    that pair to locked_pairs and ensure its checkbox is checked.

    Validates: Requirements 3.2, 3.3
    """
    target = pairs[0]

    dialog = _make_dialog(pairs)

    # Ensure pair starts unlocked
    dialog.locked_pairs.discard(target)
    dialog.checkboxes[target].setChecked(False)

    dialog._on_lock_clicked(target)

    assert target in dialog.locked_pairs, (
        f"{target!r} should be in locked_pairs after locking"
    )
    assert dialog.checkboxes[target].isChecked(), (
        f"{target!r} checkbox should be checked after locking"
    )

    dialog.close()


# ---------------------------------------------------------------------------
# Property 9: Unlocking removes from locked_pairs without changing checkbox
# ---------------------------------------------------------------------------

@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    pairs=_pair_strategy,
    initial_checked=st.booleans(),
)
def test_unlock_removes_from_locked_pairs_without_changing_checkbox(qt_app, pairs, initial_checked):
    """Property 9: Unlocking a pair removes it from locked_pairs without changing checkbox.

    For any pairs list and any initial checkbox state, unlocking a locked pair
    must remove it from locked_pairs while leaving the checkbox state unchanged.

    Validates: Requirements 3.4, 3.5
    """
    target = pairs[0]

    dialog = _make_dialog(pairs)

    # Manually set up locked state
    dialog.locked_pairs.add(target)
    dialog.lock_buttons[target].setText("🔒")
    dialog.checkboxes[target].setChecked(initial_checked)

    dialog._on_lock_clicked(target)

    assert target not in dialog.locked_pairs, (
        f"{target!r} should not be in locked_pairs after unlocking"
    )
    assert dialog.checkboxes[target].isChecked() == initial_checked, (
        f"Checkbox state should remain {initial_checked} after unlocking {target!r}"
    )

    dialog.close()


# ---------------------------------------------------------------------------
# Property 10: Lock button icon reflects lock state
# ---------------------------------------------------------------------------

@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    pairs=_pair_strategy,
    toggle_count=st.integers(min_value=1, max_value=6),
)
def test_lock_button_icon_reflects_lock_state(qt_app, pairs, toggle_count):
    """Property 10: Lock button icon always reflects the current lock state.

    After each toggle, the lock button text must be "🔒" iff the pair is in
    locked_pairs, and "🔓" otherwise.

    Validates: Requirement 3.1
    """
    target = pairs[0]

    dialog = _make_dialog(pairs)

    for _ in range(toggle_count):
        dialog._on_lock_clicked(target)
        is_locked = target in dialog.locked_pairs
        expected_icon = "🔒" if is_locked else "🔓"
        actual_icon = dialog.lock_buttons[target].text()
        assert actual_icon == expected_icon, (
            f"After toggle: expected icon {expected_icon!r}, got {actual_icon!r}. "
            f"is_locked={is_locked}"
        )

    dialog.close()


# ===========================================================================
# Task 11: Unit tests for edge cases
# ===========================================================================

def test_default_max_open_trades_is_one(qt_app):
    """11.1: Default max_open_trades is 1 when constructor argument is omitted.

    Validates: Requirement 1.2
    """
    dialog = _make_dialog(["BTC/USDT"])
    assert dialog.max_open_trades == 1, (
        f"Expected max_open_trades=1 by default, got {dialog.max_open_trades}"
    )
    dialog.close()


def test_max_open_trades_zero_clamped_to_one(qt_app):
    """11.2: max_open_trades=0 is clamped to 1.

    Validates: Requirement 4.8
    """
    dialog = _make_dialog(["BTC/USDT"], max_open_trades=0)
    assert dialog.max_open_trades == 1, (
        f"Expected max_open_trades clamped to 1, got {dialog.max_open_trades}"
    )
    dialog.close()


def test_locked_pairs_empty_on_construction(qt_app):
    """11.3: locked_pairs is empty on fresh dialog construction.

    Validates: Requirement 6.1
    """
    dialog = _make_dialog(["BTC/USDT"])
    assert dialog.locked_pairs == set(), (
        f"Expected locked_pairs to be empty, got {dialog.locked_pairs}"
    )
    dialog.close()


def test_custom_pair_gets_unlocked_lock_button(qt_app):
    """11.4: Custom pair gets a lock button in unlocked state after _on_add_custom.

    Validates: Requirement 5.2
    """
    dialog = _make_dialog(["BTC/USDT"])

    dialog.custom_input.setText("CUSTOM/USDT")
    dialog._on_add_custom()

    assert "CUSTOM/USDT" in dialog.lock_buttons, (
        "CUSTOM/USDT should have a lock button after _on_add_custom"
    )
    assert dialog.lock_buttons["CUSTOM/USDT"].text() == "🔓", (
        f"New custom pair lock button should show '🔓', "
        f"got {dialog.lock_buttons['CUSTOM/USDT'].text()!r}"
    )
    dialog.close()


def test_randomize_button_label_includes_max_open_trades(qt_app):
    """11.5: Randomize button label equals f"🎲 Randomize ({max_open_trades})".

    Validates: Property 1 (Requirement 2.1)
    """
    dialog = _make_dialog(["BTC/USDT"], max_open_trades=5)
    expected = "🎲 Randomize (5)"
    assert dialog.randomize_btn.text() == expected, (
        f"Expected randomize button text {expected!r}, "
        f"got {dialog.randomize_btn.text()!r}"
    )
    dialog.close()
