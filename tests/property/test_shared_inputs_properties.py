"""Property-based tests for the shared-inputs feature.

Properties covered:
  Property 1 — Migration priority is respected
    Validates: Requirements 1.3
"""

from __future__ import annotations

from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.core.models.settings_models import AppSettings

# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------

_SIX_FIELDS = (
    "default_timeframe",
    "default_timerange",
    "last_timerange_preset",
    "default_pairs",
    "dry_run_wallet",
    "max_open_trades",
)

_field_values_st = st.fixed_dictionaries(
    {},
    optional={
        "default_timeframe": st.sampled_from(["1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d"]),
        "default_timerange": st.text(max_size=20),
        "last_timerange_preset": st.text(max_size=10),
        "default_pairs": st.text(max_size=60),
        "dry_run_wallet": st.floats(
            min_value=0.01, max_value=1_000_000.0, allow_nan=False, allow_infinity=False
        ),
        "max_open_trades": st.integers(min_value=1, max_value=100),
    },
)


# ---------------------------------------------------------------------------
# Property 1: Migration priority is respected
# Validates: Requirements 1.3
# ---------------------------------------------------------------------------


@given(
    download=_field_values_st,
    backtest=_field_values_st,
    optimizer=_field_values_st,
)
@h_settings(max_examples=200)
def test_migration_priority_respected(
    download: dict,
    backtest: dict,
    optimizer: dict,
) -> None:
    """**Validates: Requirements 1.3**

    For any combination of optimizer_preferences, backtest_preferences, and
    download_preferences dicts each containing a subset of the six shared fields,
    constructing AppSettings without a shared_inputs key produces shared_inputs
    values matching optimizer > backtest > download priority.
    """
    raw = {
        "download_preferences": download,
        "backtest_preferences": backtest,
        "optimizer_preferences": optimizer,
    }
    settings = AppSettings(**raw)
    si = settings.shared_inputs

    for field in _SIX_FIELDS:
        # Determine expected value: optimizer wins, then backtest, then download, then default
        if field in optimizer:
            expected = optimizer[field]
        elif field in backtest:
            expected = backtest[field]
        elif field in download:
            expected = download[field]
        else:
            # No source provided — should be the SharedInputsPreferences default
            from app.core.models.settings_models import SharedInputsPreferences
            expected = SharedInputsPreferences.model_fields[field].default
            # For float comparison use tolerance
        actual = getattr(si, field)
        if isinstance(expected, float):
            assert abs(actual - expected) < 1e-9, (
                f"Field {field!r}: expected {expected!r}, got {actual!r}"
            )
        else:
            assert actual == expected, (
                f"Field {field!r}: expected {expected!r}, got {actual!r}"
            )


# ===========================================================================
# Properties 2–5: SharedInputsService write/read, validation, preset, pairs
# ===========================================================================

import os
import re
import tempfile
from datetime import date

import pytest

from app.core.services.settings_service import SettingsService
from app.core.services.shared_inputs_service import SharedInputsService, SharedInputsUpdate
from app.core.services.input_holder_service import KNOWN_PRESETS

_YYYYMMDD_RE = re.compile(r"^\d{8}-\d{8}$")

_timeframe_st = st.sampled_from(["1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d"])
_wallet_valid_st = st.floats(min_value=0.01, max_value=1_000_000.0, allow_nan=False, allow_infinity=False)
_trades_valid_st = st.integers(min_value=1, max_value=100)
_pairs_st = st.text(min_size=0, max_size=100)


def _fresh_service() -> tuple[SharedInputsService, str]:
    """Return a SharedInputsService backed by a fresh temp settings file."""
    tmp = tempfile.mktemp(suffix=".json")
    svc = SettingsService(settings_file=tmp)
    return SharedInputsService(svc), tmp


def _cleanup(tmp: str) -> None:
    if os.path.exists(tmp):
        os.unlink(tmp)


# ---------------------------------------------------------------------------
# Property 2: Write/read round-trip preserves values
# Validates: Requirements 2.1, 2.2, 9.1
# ---------------------------------------------------------------------------

_valid_update_st = st.builds(
    SharedInputsUpdate,
    default_timeframe=st.one_of(st.none(), _timeframe_st),
    default_timerange=st.one_of(st.none(), st.text(max_size=20)),
    # Avoid known presets so preset resolution doesn't overwrite default_timerange
    last_timerange_preset=st.one_of(
        st.none(),
        st.text(max_size=10).filter(lambda s: s not in KNOWN_PRESETS),
    ),
    default_pairs=st.one_of(st.none(), _pairs_st),
    dry_run_wallet=st.one_of(st.none(), _wallet_valid_st),
    max_open_trades=st.one_of(st.none(), _trades_valid_st),
)


@given(_valid_update_st)
@h_settings(max_examples=100)
def test_write_read_roundtrip(update: SharedInputsUpdate) -> None:
    """**Validates: Requirements 2.1, 2.2, 9.1**

    For any valid SharedInputsUpdate, write_config followed by read_config
    returns SharedInputsPreferences whose fields match the written values
    (after preset resolution and pair deduplication).
    """
    service, tmp = _fresh_service()
    try:
        written = service.write_config(update)
        read_back = service.read_config()

        # The two calls must agree
        assert written == read_back

        # Each non-None field in the update must be reflected (after transforms)
        if update.default_timeframe is not None:
            assert read_back.default_timeframe == update.default_timeframe

        if update.max_open_trades is not None:
            assert read_back.max_open_trades == update.max_open_trades

        if update.dry_run_wallet is not None:
            assert abs(read_back.dry_run_wallet - update.dry_run_wallet) < 1e-9

        # default_pairs: deduplication applied — result must be a subset preserving order
        if update.default_pairs is not None:
            stored = read_back.default_pairs
            if stored:
                stored_list = stored.split(",")
                assert len(stored_list) == len(set(stored_list)), "Duplicates found after dedup"

        # last_timerange_preset (non-known): stored as-is
        if update.last_timerange_preset is not None:
            assert read_back.last_timerange_preset == update.last_timerange_preset

        # default_timerange: only check when no preset was set (preset would overwrite it)
        if update.default_timerange is not None and update.last_timerange_preset is None:
            assert read_back.default_timerange == update.default_timerange
    finally:
        _cleanup(tmp)


# ---------------------------------------------------------------------------
# Property 3: Numeric validation rejects invalid inputs
# Validates: Requirements 2.3, 2.4
# ---------------------------------------------------------------------------

@given(st.floats(max_value=0.0, allow_nan=False, allow_infinity=False))
@h_settings(max_examples=100)
def test_invalid_wallet_raises_and_no_state_change(bad_wallet: float) -> None:
    """**Validates: Requirements 2.3, 2.4**

    write_config with dry_run_wallet <= 0 raises ValueError and does not
    modify persisted settings.
    """
    service, tmp = _fresh_service()
    try:
        before = service.read_config()
        with pytest.raises(ValueError):
            service.write_config(SharedInputsUpdate(dry_run_wallet=bad_wallet))
        after = service.read_config()
        assert before == after
    finally:
        _cleanup(tmp)


@given(st.integers(max_value=0))
@h_settings(max_examples=100)
def test_invalid_trades_raises_and_no_state_change(bad_trades: int) -> None:
    """**Validates: Requirements 2.3, 2.4**

    write_config with max_open_trades < 1 raises ValueError and does not
    modify persisted settings.
    """
    service, tmp = _fresh_service()
    try:
        before = service.read_config()
        with pytest.raises(ValueError):
            service.write_config(SharedInputsUpdate(max_open_trades=bad_trades))
        after = service.read_config()
        assert before == after
    finally:
        _cleanup(tmp)


# ---------------------------------------------------------------------------
# Property 4: Preset resolution produces valid YYYYMMDD-YYYYMMDD timerange
# Validates: Requirements 2.5
# ---------------------------------------------------------------------------

@given(st.sampled_from(list(KNOWN_PRESETS)), st.dates(min_value=date(1001, 1, 1)))
@h_settings(max_examples=100)
def test_preset_resolution_sets_valid_timerange(preset_key: str, today: date) -> None:
    """**Validates: Requirements 2.5**

    write_config with a known last_timerange_preset sets default_timerange to a
    YYYYMMDD-YYYYMMDD string whose end date equals today.
    """
    from app.core.services.input_holder_service import InputHolderService

    service, tmp = _fresh_service()
    try:
        # Resolve expected value using the same static helper
        expected_timerange = InputHolderService.resolve_preset(preset_key, today=today)
        assert expected_timerange is not None

        # We can't inject 'today' into write_config directly, so we verify the
        # static helper's output format and that write_config delegates to it.
        # Verify format: YYYYMMDD-YYYYMMDD
        assert _YYYYMMDD_RE.match(expected_timerange), f"Bad format: {expected_timerange!r}"
        start_str, end_str = expected_timerange.split("-")
        assert end_str == today.strftime("%Y%m%d"), "End date must equal today"
        start = date(int(start_str[:4]), int(start_str[4:6]), int(start_str[6:]))
        assert start < today

        # Also verify write_config actually resolves the preset (using real today)
        result = service.write_config(SharedInputsUpdate(last_timerange_preset=preset_key))
        assert _YYYYMMDD_RE.match(result.default_timerange), (
            f"write_config did not produce YYYYMMDD-YYYYMMDD: {result.default_timerange!r}"
        )
    finally:
        _cleanup(tmp)


# ---------------------------------------------------------------------------
# Property 5: Pair deduplication preserves insertion order and removes duplicates
# Validates: Requirements 2.6
# ---------------------------------------------------------------------------

_safe_pair_char = st.characters(
    whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="/"
)
_safe_pair_st = st.text(min_size=1, max_size=10, alphabet=_safe_pair_char)


@given(st.lists(_safe_pair_st, min_size=1, max_size=20))
@h_settings(max_examples=100)
def test_pair_deduplication_order(pairs: list[str]) -> None:
    """**Validates: Requirements 2.6**

    write_config with a default_pairs string containing duplicates persists a
    value where each pair appears at most once and first-occurrence order is preserved.
    """
    # Inject duplicates by doubling the list
    doubled = pairs + pairs
    input_str = ",".join(doubled)

    service, tmp = _fresh_service()
    try:
        result = service.write_config(SharedInputsUpdate(default_pairs=input_str))
        stored = result.default_pairs
        stored_list = [p for p in stored.split(",") if p] if stored else []

        # No duplicates
        assert len(stored_list) == len(set(stored_list)), "Duplicates found in stored pairs"

        # Relative order matches first occurrence in input
        seen_order: list[str] = []
        for p in doubled:
            if p not in seen_order:
                seen_order.append(p)
        assert stored_list == seen_order, (
            f"Order mismatch: expected {seen_order!r}, got {stored_list!r}"
        )
    finally:
        _cleanup(tmp)
