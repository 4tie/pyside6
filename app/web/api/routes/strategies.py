"""Strategy listing endpoints."""

from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException

from app.core.freqtrade.resolvers.config_resolver import find_config_file_path
from app.core.parsing.json_parser import parse_json_file
from app.web.dependencies import BacktestServiceDep, SettingsServiceDep
from app.web.models import StrategyResponse

router = APIRouter()


@router.get("/strategies", response_model=List[StrategyResponse])
async def list_strategies(backtest_service: BacktestServiceDep) -> List[StrategyResponse]:
    return [StrategyResponse(name=name, config=None) for name in backtest_service.get_available_strategies()]


@router.get("/strategies/{strategy_name}", response_model=StrategyResponse)
async def get_strategy(strategy_name: str, settings: SettingsServiceDep) -> StrategyResponse:
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        raise HTTPException(status_code=404, detail="User data path not configured")

    user_data_dir = Path(app_settings.user_data_path).expanduser()
    try:
        config_path = find_config_file_path(user_data_dir, strategy_name=strategy_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_name} not found") from exc

    config = parse_json_file(config_path) if Path(config_path).exists() else {}
    return StrategyResponse(name=strategy_name, config=config)
