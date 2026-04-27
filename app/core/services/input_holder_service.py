"""InputHolderService — backend source of truth for the seven Configure-section fields.

Reads and writes Strategy, Timeframe, Preset, Timerange, Wallet, Max Trades, and Pairs
through SettingsService / OptimizerPreferences / AppSettings.

Architecture boundary: NO PySide6 imports in this module.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from app.core.models.optimizer_models import (
    OptimizerConfigResponse,
    OptimizerConfigUpdate,
    OptimizerPreferences,
)
from app.core.services.settings_service import SettingsService
from app.core.utils.app_logger import get_logger

_log = get_logger("input_holder_service")

# Mapping of known preset keys to number of days back
_PRESET_DAYS: dict[str, int] = {
    "7d": 7,
    "14d": 14,
    "30d": 30,
    "60d": 60,
    "90d": 90,
    "180d": 180,
    "1y": 365,
}

KNOWN_PRESETS: tuple[str, ...] = tuple(_PRESET_DAYS.keys())


def _prefs_to_response(prefs: OptimizerPreferences) -> OptimizerConfigResponse:
    """Convert an OptimizerPreferences instance to the response DTO."""
    raw = prefs.default_pairs or ""
    pairs_list = [p.strip() for p in raw.split(",") if p.strip()] if raw else []
    return OptimizerConfigResponse(
        last_strategy=prefs.last_strategy,
        default_timeframe=prefs.default_timeframe,
        last_timerange_preset=prefs.last_timerange_preset,
        default_timerange=prefs.default_timerange,
        default_pairs=raw,
        pairs_list=pairs_list,
        dry_run_wallet=prefs.dry_run_wallet,
        max_open_trades=prefs.max_open_trades,
    )


class InputHolderService:
    """Service that owns read/write of the seven Configure-section InputHolder fields."""

    def __init__(self, settings_service: SettingsService) -> None:
        self._settings = settings_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read_config(self) -> OptimizerConfigResponse:
        """Load OptimizerPreferences and return the full response DTO."""
        settings = self._settings.load_settings()
        return _prefs_to_response(settings.optimizer_preferences)

    def write_config(self, update: OptimizerConfigUpdate) -> OptimizerConfigResponse:
        """Validate, resolve preset, deduplicate pairs, persist, return updated state.

        Raises:
            ValueError: for invalid field values (dry_run_wallet <= 0, max_open_trades < 1).
            RuntimeError: propagated from SettingsService on disk write failure.
        """
        # Validate numeric constraints before touching persistence
        if update.dry_run_wallet is not None and update.dry_run_wallet <= 0:
            raise ValueError(
                f"dry_run_wallet must be greater than 0, got {update.dry_run_wallet}"
            )
        if update.max_open_trades is not None and update.max_open_trades < 1:
            raise ValueError(
                f"max_open_trades must be at least 1, got {update.max_open_trades}"
            )

        # Build the fields dict from the update (only non-None values)
        fields: dict = {k: v for k, v in update.model_dump().items() if v is not None}

        # Preset resolution: if a known preset key is provided, compute timerange
        preset_key = fields.get("last_timerange_preset")
        if preset_key is not None:
            resolved = self.resolve_preset(preset_key)
            if resolved is not None:
                fields["default_timerange"] = resolved

        # Pairs deduplication
        if "default_pairs" in fields:
            fields["default_pairs"] = self.deduplicate_pairs(fields["default_pairs"])

        # Atomic write via SettingsService
        updated_prefs = self._settings.update_preferences("optimizer_preferences", **fields)
        return _prefs_to_response(updated_prefs)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def resolve_preset(key: str, today: Optional[date] = None) -> Optional[str]:
        """Return YYYYMMDD-YYYYMMDD for a known preset key, or None if unknown.

        Args:
            key: Preset key such as "30d" or "1y".
            today: Reference date (defaults to date.today()).
        """
        days = _PRESET_DAYS.get(key)
        if days is None:
            return None
        ref = today if today is not None else date.today()
        start = ref - timedelta(days=days)
        return f"{start:%Y%m%d}-{ref:%Y%m%d}"

    @staticmethod
    def deduplicate_pairs(pairs_str: str) -> str:
        """Remove duplicate entries from a comma-separated pairs string.

        Preserves insertion order of first occurrences.
        Returns empty string for empty input.
        Tokens are compared and stored as-is (no whitespace stripping) so that
        the stored raw string round-trips faithfully through read-your-writes.
        Only truly empty tokens (from consecutive commas) are filtered out.
        """
        if not pairs_str:
            return ""
        seen: dict[str, None] = {}
        for part in pairs_str.split(","):
            if part:  # filter only truly empty tokens (consecutive commas)
                seen[part] = None
        return ",".join(seen.keys())
