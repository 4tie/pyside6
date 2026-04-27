"""SharedInputsService — backend service for reading and writing shared trading inputs.

Owns the six common fields (default_timeframe, default_timerange, last_timerange_preset,
default_pairs, dry_run_wallet, max_open_trades) via the shared_inputs preference section.

Architecture boundary: NO PySide6 imports in this module.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from app.core.models.settings_models import SharedInputsPreferences
from app.core.services.input_holder_service import KNOWN_PRESETS, InputHolderService
from app.core.services.settings_service import SettingsService
from app.core.utils.app_logger import get_logger

_log = get_logger("shared_inputs_service")


class SharedInputsUpdate(BaseModel):
    """Partial update model for shared trading inputs. All fields are optional."""

    default_timeframe: Optional[str] = None
    default_timerange: Optional[str] = None
    last_timerange_preset: Optional[str] = None
    default_pairs: Optional[str] = None
    dry_run_wallet: Optional[float] = None
    max_open_trades: Optional[int] = None


class SharedInputsService:
    """Service that owns read/write of the six shared trading input fields."""

    def __init__(self, settings_service: SettingsService) -> None:
        self._settings = settings_service

    def read_config(self) -> SharedInputsPreferences:
        """Load and return the current SharedInputsPreferences."""
        return self._settings.load_settings().shared_inputs

    def write_config(self, update: SharedInputsUpdate) -> SharedInputsPreferences:
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

        # Build fields dict from non-None values
        fields: dict = {k: v for k, v in update.model_dump().items() if v is not None}

        # Preset resolution: if a known preset key is provided, compute timerange
        preset_key = fields.get("last_timerange_preset")
        if preset_key is not None and preset_key in KNOWN_PRESETS:
            resolved = InputHolderService.resolve_preset(preset_key)
            if resolved is not None:
                fields["default_timerange"] = resolved

        # Pairs deduplication
        if "default_pairs" in fields:
            fields["default_pairs"] = InputHolderService.deduplicate_pairs(fields["default_pairs"])

        # Atomic write via SettingsService
        updated = self._settings.update_preferences("shared_inputs", **fields)
        return SharedInputsPreferences.model_validate(updated.model_dump())
