"""API endpoints for strategy management.

Provides endpoints to list available strategies and retrieve strategy configurations.
"""
from typing import List

from fastapi import APIRouter, HTTPException, Depends

from app.core.services.backtest_service import BacktestService
from app.core.services.settings_service import SettingsService
from app.core.services.strategy_config_service import StrategyConfigService
from app.core.freqtrade.resolvers.config_resolver import find_config_file_path
from app.web.dependencies import (
    SettingsServiceDep,
    BacktestServiceDep,
)
from app.web.models import StrategyResponse
from pathlib import Path

router = APIRouter()


@router.get("/strategies", response_model=List[StrategyResponse])
async def list_strategies(
    backtest_service: BacktestServiceDep,
) -> List[StrategyResponse]:
    """List all available strategies."""
    strategies = backtest_service.get_available_strategies()
    return [
        StrategyResponse(
            name=strategy,
            config=None,
        )
        for strategy in strategies
    ]


@router.get("/strategies/{strategy_name}", response_model=StrategyResponse)
async def get_strategy(
    strategy_name: str,
    settings: SettingsServiceDep,
) -> StrategyResponse:
    """Get strategy configuration details."""
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        raise HTTPException(status_code=404, detail="User data path not configured")
    
    user_data_dir = Path(app_settings.user_data_path).expanduser().resolve()
    
    try:
        config_path = find_config_file_path(user_data_dir, strategy_name=strategy_name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_name} not found")
    
    # Load strategy configuration
    config = {}
    if config_path and Path(config_path).exists():
        config = parse_json_file(Path(config_path))
    
    return StrategyResponse(
        name=strategy_name,
        config=config,
    )
