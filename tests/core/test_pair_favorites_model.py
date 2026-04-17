# Feature: pair-favorites, Property 6: Legacy migration produces deduplicated union
"""
Tests for AppSettings.favorite_pairs field and legacy migration validator.
"""
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.models.settings_models import AppSettings


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_favorite_pairs_defaults_to_empty():
    """AppSettings() should default favorite_pairs to an empty list."""
    app_settings = AppSettings()
    assert app_settings.favorite_pairs == []


def test_favorite_pairs_no_raise_without_field():
    """AppSettings(**{}) should not raise even when favorite_pairs is absent."""
    app_settings = AppSettings(**{})
    assert isinstance(app_settings.favorite_pairs, list)


def test_favorite_pairs_top_level():
    """AppSettings should expose favorite_pairs as a direct attribute, not nested."""
    app_settings = AppSettings()
    # Attribute exists directly on the model
    assert hasattr(app_settings, "favorite_pairs")
    # It is NOT nested inside any sub-preferences model
    assert not hasattr(app_settings.backtest_preferences, "favorite_pairs")
    assert not hasattr(app_settings.optimize_preferences, "favorite_pairs")
    assert not hasattr(app_settings.download_preferences, "favorite_pairs")


# ---------------------------------------------------------------------------
# Property-based test — Property 6
# ---------------------------------------------------------------------------

_pair_list = st.lists(
    st.text(
        min_size=1,
        max_size=10,
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            whitelist_characters="/",
        ),
    ),
    max_size=5,
)


@settings(max_examples=100)
@given(
    backtest_pairs=_pair_list,
    optimize_pairs=_pair_list,
    download_pairs=_pair_list,
)
def test_legacy_migration_deduplicated_union(
    backtest_pairs: list[str],
    optimize_pairs: list[str],
    download_pairs: list[str],
) -> None:
    """Property 6: Legacy migration produces deduplicated union.

    Build a raw dict with per-section paired_favorites and NO top-level
    favorite_pairs, load AppSettings, and assert that favorite_pairs is the
    deduplicated union of all three lists with no duplicates.

    Validates: Requirements 5.4
    """
    raw: dict = {
        "backtest_preferences": {"paired_favorites": backtest_pairs},
        "optimize_preferences": {"paired_favorites": optimize_pairs},
        "download_preferences": {"paired_favorites": download_pairs},
    }

    app_settings = AppSettings(**raw)
    result = app_settings.favorite_pairs

    # No duplicates
    assert len(result) == len(set(result)), (
        f"Duplicates found in favorite_pairs: {result}"
    )

    # Every pair from all three source lists appears in the result
    all_source_pairs = set(backtest_pairs) | set(optimize_pairs) | set(download_pairs)
    for pair in all_source_pairs:
        assert pair in result, (
            f"Pair {pair!r} from source lists is missing from favorite_pairs: {result}"
        )

    # Every pair in the result came from one of the three source lists
    for pair in result:
        assert pair in all_source_pairs, (
            f"Pair {pair!r} in favorite_pairs did not come from any source list"
        )
