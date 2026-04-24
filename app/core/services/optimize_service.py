from pathlib import Path
from typing import List, Optional

from app.core.freqtrade import create_optimize_command, list_strategies
from app.core.services.settings_service import SettingsService


class OptimizeService:
    """Service for building hyperopt commands and listing strategies."""

    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service

    def build_command(
        self,
        strategy_name: str,
        timeframe: str,
        epochs: int,
        timerange: Optional[str] = None,
        pairs: Optional[List[str]] = None,
        spaces: Optional[List[str]] = None,
        hyperopt_loss: Optional[str] = None,
        extra_flags: Optional[List[str]] = None,
    ):
        """Build a hyperopt command."""
        settings = self.settings_service.load_settings()
        return create_optimize_command(
            settings=settings,
            strategy_name=strategy_name,
            timeframe=timeframe,
            epochs=epochs,
            timerange=timerange,
            pairs=pairs or [],
            spaces=spaces or [],
            hyperopt_loss=hyperopt_loss,
            extra_flags=extra_flags or [],
        )

    def get_available_strategies(self) -> List[str]:
        """List available strategy names from user_data/strategies/."""
        settings = self.settings_service.load_settings()
        if not settings.user_data_path:
            return []
        return list_strategies(Path(settings.user_data_path).expanduser().resolve())
