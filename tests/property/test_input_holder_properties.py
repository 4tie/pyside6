"""Property-based tests for the input-holder-backend-persistence feature.

Uses Hypothesis to verify correctness properties across arbitrary inputs.
Each test is tagged with a comment referencing the design property it validates.

Properties covered:
  1  - OptimizerPreferences JSON round-trip
  2  - Type constraint violations raise ValidationError
  6  - Known preset resolution produces valid YYYYMMDD-YYYYMMDD
  7  - Preset resolution idempotence
  9  - Pairs deduplication preserves insertion order
"""

from __future__ import annotations

import re
from datetime import date

import pytest
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st
from pydantic import ValidationError

from app.core.models.optimizer_models import OptimizerPreferences
from app.core.services.input_holder_service import KNOWN_PRESETS, InputHolderService

# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------

_nonempty_str = st.text(min_size=1, max_size=50)
_timeframe_st = st.sampled_from(["1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d"])
_pairs_st = st.text(min_size=0, max_size=100)
_wallet_st = st.floats(min_value=0.01, max_value=1_000_000.0, allow_nan=False, allow_infinity=False)
_trades_st = st.integers(min_value=1, max_value=100)

_valid_prefs_st = st.builds(
    OptimizerPreferences,
    last_strategy=st.text(max_size=80),
    default_timeframe=_timeframe_st,
    default_timerange=st.text(max_size=20),
    default_pairs=_pairs_st,
    last_timerange_preset=st.text(max_size=10),
    dry_run_wallet=_wallet_st,
    max_open_trades=_trades_st,
    total_trials=st.integers(min_value=1, max_value=1000),
    score_metric=st.text(max_size=30),
    score_mode=st.text(max_size=30),
    target_min_trades=st.integers(min_value=1, max_value=100_000),
    target_profit_pct=st.floats(min_value=0.01, max_value=10_000.0, allow_nan=False, allow_infinity=False),
    max_drawdown_limit=st.floats(min_value=0.01, max_value=100.0, allow_nan=False, allow_infinity=False),
    target_romad=st.floats(min_value=0.01, max_value=100.0, allow_nan=False, allow_infinity=False),
)

# ---------------------------------------------------------------------------
# Property 1: OptimizerPreferences JSON round-trip
# Feature: input-holder-backend-persistence, Property 1: OptimizerPreferences JSON round-trip
# ---------------------------------------------------------------------------

@given(_valid_prefs_st)
@h_settings(max_examples=100)
def test_optimizer_preferences_round_trip(prefs: OptimizerPreferences):
    # Feature: input-holder-backend-persistence, Property 1: OptimizerPreferences JSON round-trip
    data = prefs.model_dump(mode="json")
    restored = OptimizerPreferences.model_validate(data)
    assert restored == prefs


# ---------------------------------------------------------------------------
# Property 2: Type constraint violations raise ValidationError
# Feature: input-holder-backend-persistence, Property 2: Type constraint violations raise ValidationError
# ---------------------------------------------------------------------------

@given(st.floats(max_value=0.0, allow_nan=False, allow_infinity=False))
@h_settings(max_examples=100)
def test_invalid_wallet_raises_validation_error(bad_wallet: float):
    # Feature: input-holder-backend-persistence, Property 2: Type constraint violations raise ValidationError
    with pytest.raises(ValidationError):
        OptimizerPreferences(dry_run_wallet=bad_wallet)


@given(st.integers(max_value=0))
@h_settings(max_examples=100)
def test_invalid_trades_raises_validation_error(bad_trades: int):
    # Feature: input-holder-backend-persistence, Property 2: Type constraint violations raise ValidationError
    with pytest.raises(ValidationError):
        OptimizerPreferences(max_open_trades=bad_trades)


# ---------------------------------------------------------------------------
# Property 6: Known preset resolution produces valid YYYYMMDD-YYYYMMDD
# Feature: input-holder-backend-persistence, Property 6: Known preset resolution produces valid YYYYMMDD-YYYYMMDD
# ---------------------------------------------------------------------------

_YYYYMMDD_RE = re.compile(r"^\d{8}-\d{8}$")


@given(st.sampled_from(KNOWN_PRESETS), st.dates(min_value=date(1001, 1, 1)))
@h_settings(max_examples=100)
def test_preset_resolution_format(key: str, today: date):
    # Feature: input-holder-backend-persistence, Property 6: Known preset resolution produces valid YYYYMMDD-YYYYMMDD
    result = InputHolderService.resolve_preset(key, today=today)
    assert result is not None
    assert _YYYYMMDD_RE.match(result), f"Bad format: {result!r}"
    start_str, end_str = result.split("-")
    assert end_str == today.strftime("%Y%m%d"), "End date must equal today"
    # Start date must be strictly before today
    start = date(int(start_str[:4]), int(start_str[4:6]), int(start_str[6:]))
    assert start < today


# ---------------------------------------------------------------------------
# Property 7: Preset resolution idempotence
# Feature: input-holder-backend-persistence, Property 7: Preset resolution idempotence
# ---------------------------------------------------------------------------

@given(st.sampled_from(KNOWN_PRESETS), st.dates(min_value=date(1001, 1, 1)))
@h_settings(max_examples=100)
def test_preset_resolution_idempotence(key: str, today: date):
    # Feature: input-holder-backend-persistence, Property 7: Preset resolution idempotence
    first = InputHolderService.resolve_preset(key, today=today)
    second = InputHolderService.resolve_preset(key, today=today)
    assert first == second


# ---------------------------------------------------------------------------
# Property 9: Pairs deduplication preserves insertion order
# Feature: input-holder-backend-persistence, Property 9: Pairs deduplication preserves insertion order
# ---------------------------------------------------------------------------

@given(st.lists(st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="/")), min_size=1, max_size=20))
@h_settings(max_examples=100)
def test_pairs_deduplication_order(pairs: list[str]):
    # Feature: input-holder-backend-persistence, Property 9: Pairs deduplication preserves insertion order
    # Inject duplicates by doubling the list
    doubled = pairs + pairs
    input_str = ",".join(doubled)
    result = InputHolderService.deduplicate_pairs(input_str)
    result_list = [p for p in result.split(",") if p]

    # No duplicates
    assert len(result_list) == len(set(result_list))

    # Relative order matches first occurrence in input
    seen_order = []
    for p in doubled:
        if p not in seen_order:
            seen_order.append(p)
    assert result_list == seen_order


# ===========================================================================
# Router-level property tests (Properties 3, 4, 5, 8, 10)
# These use FastAPI TestClient with a real in-memory SettingsService backed
# by a temporary file so that read-your-writes can be verified end-to-end.
# ===========================================================================

import tempfile
import os

from fastapi.testclient import TestClient

from app.core.services.settings_service import SettingsService
from app.web.dependencies import get_settings_service
from app.web.main import app

KNOWN_FIELDS = frozenset(
    {"last_strategy", "default_timeframe", "last_timerange_preset",
     "default_timerange", "default_pairs", "dry_run_wallet", "max_open_trades"}
)


def _fresh_client() -> tuple[TestClient, str]:
    """Return a TestClient wired to a fresh temp settings file, plus the temp path."""
    tmp = tempfile.mktemp(suffix=".json")
    svc = SettingsService(settings_file=tmp)
    app.dependency_overrides[get_settings_service] = lambda: svc
    client = TestClient(app, raise_server_exceptions=False)
    return client, tmp


def _cleanup(tmp: str) -> None:
    app.dependency_overrides.clear()
    if os.path.exists(tmp):
        os.unlink(tmp)


# ---------------------------------------------------------------------------
# Property 3: Read-your-writes consistency
# Feature: input-holder-backend-persistence, Property 3: Read-your-writes consistency
# ---------------------------------------------------------------------------

_update_st = st.fixed_dictionaries(
    {},
    optional={
        "last_strategy": st.text(max_size=40),
        "default_timeframe": st.sampled_from(["1m", "5m", "15m", "1h", "4h", "1d"]),
        "default_pairs": st.text(max_size=60),
        "dry_run_wallet": st.floats(min_value=0.01, max_value=100_000.0, allow_nan=False, allow_infinity=False),
        "max_open_trades": st.integers(min_value=1, max_value=100),
    },
)


@given(_update_st)
@h_settings(max_examples=50)
def test_read_your_writes(payload: dict):
    # Feature: input-holder-backend-persistence, Property 3: Read-your-writes consistency
    client, tmp = _fresh_client()
    try:
        put_resp = client.put("/api/optimizer/config", json=payload)
        assert put_resp.status_code == 200, put_resp.text
        get_resp = client.get("/api/optimizer/config")
        assert get_resp.status_code == 200
        data = get_resp.json()
        for key, value in payload.items():
            if key == "dry_run_wallet":
                assert abs(data[key] - value) < 1e-6
            elif key == "max_open_trades":
                assert data[key] == value
            else:
                assert data[key] == value, f"Mismatch for {key}: {data[key]!r} != {value!r}"
    finally:
        _cleanup(tmp)


# ---------------------------------------------------------------------------
# Property 4: Unknown fields rejected with HTTP 422
# Feature: input-holder-backend-persistence, Property 4: Unknown fields rejected with HTTP 422
# ---------------------------------------------------------------------------

_unknown_field_st = st.text(
    min_size=1, max_size=30,
    alphabet=st.characters(whitelist_categories=("Ll",)),
).filter(lambda s: s not in KNOWN_FIELDS and s.isidentifier())


@given(_unknown_field_st)
@h_settings(max_examples=50)
def test_unknown_fields_rejected_422(field_name: str):
    # Feature: input-holder-backend-persistence, Property 4: Unknown fields rejected with HTTP 422
    client, tmp = _fresh_client()
    try:
        resp = client.put("/api/optimizer/config", json={field_name: "value"})
        assert resp.status_code == 422, f"Expected 422 for unknown field {field_name!r}, got {resp.status_code}"
    finally:
        _cleanup(tmp)


# ---------------------------------------------------------------------------
# Property 5: Wallet and trades boundary validation
# Feature: input-holder-backend-persistence, Property 5: Wallet and trades boundary validation
# ---------------------------------------------------------------------------

@given(st.floats(max_value=0.0, allow_nan=False, allow_infinity=False))
@h_settings(max_examples=50)
def test_wallet_boundary_returns_422(bad_wallet: float):
    # Feature: input-holder-backend-persistence, Property 5: Wallet and trades boundary validation
    client, tmp = _fresh_client()
    try:
        resp = client.put("/api/optimizer/config", json={"dry_run_wallet": bad_wallet})
        assert resp.status_code == 422
    finally:
        _cleanup(tmp)


@given(st.integers(max_value=0))
@h_settings(max_examples=50)
def test_trades_boundary_returns_422(bad_trades: int):
    # Feature: input-holder-backend-persistence, Property 5: Wallet and trades boundary validation
    client, tmp = _fresh_client()
    try:
        resp = client.put("/api/optimizer/config", json={"max_open_trades": bad_trades})
        assert resp.status_code == 422
    finally:
        _cleanup(tmp)


# ---------------------------------------------------------------------------
# Property 8: Unknown preset does not overwrite existing timerange
# Feature: input-holder-backend-persistence, Property 8: Unknown preset does not overwrite existing timerange
# ---------------------------------------------------------------------------

@given(
    st.text(min_size=1, max_size=20).filter(lambda s: s not in KNOWN_PRESETS),
    st.text(min_size=1, max_size=20),
)
@h_settings(max_examples=50)
def test_unknown_preset_preserves_timerange(unknown_preset: str, existing_timerange: str):
    # Feature: input-holder-backend-persistence, Property 8: Unknown preset does not overwrite existing timerange
    client, tmp = _fresh_client()
    try:
        # First set a known timerange
        setup = client.put("/api/optimizer/config", json={"default_timerange": existing_timerange})
        assert setup.status_code == 200

        # Now PUT with an unknown preset — timerange must not change
        resp = client.put("/api/optimizer/config", json={"last_timerange_preset": unknown_preset})
        assert resp.status_code == 200
        data = resp.json()
        assert data["default_timerange"] == existing_timerange, (
            f"Timerange changed from {existing_timerange!r} to {data['default_timerange']!r} "
            f"when unknown preset {unknown_preset!r} was set"
        )
    finally:
        _cleanup(tmp)


# ---------------------------------------------------------------------------
# Property 10: Pairs response includes both raw string and parsed list
# Feature: input-holder-backend-persistence, Property 10: Pairs response includes both raw string and parsed list
# ---------------------------------------------------------------------------

_safe_pair_char = st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="/")
_safe_pair_st = st.text(min_size=1, max_size=10, alphabet=_safe_pair_char)
_pairs_input_st = st.lists(_safe_pair_st, min_size=1, max_size=10).map(lambda ps: ",".join(ps))


@given(_pairs_input_st)
@h_settings(max_examples=50)
def test_pairs_response_consistency(pairs_str: str):
    # Feature: input-holder-backend-persistence, Property 10: Pairs response includes both raw string and parsed list
    client, tmp = _fresh_client()
    try:
        put_resp = client.put("/api/optimizer/config", json={"default_pairs": pairs_str})
        assert put_resp.status_code == 200
        get_resp = client.get("/api/optimizer/config")
        assert get_resp.status_code == 200
        data = get_resp.json()
        raw = data["default_pairs"]
        pairs_list = data["pairs_list"]
        # pairs_list joined must equal the stored (deduplicated) raw string
        if raw:
            assert ",".join(pairs_list) == raw
        else:
            assert pairs_list == []
    finally:
        _cleanup(tmp)
