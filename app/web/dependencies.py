"""Dependency injection for FastAPI routes."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.core.services.backtest_service import BacktestService
from app.core.services.download_data_service import DownloadDataService
from app.core.services.optimize_service import OptimizeService
from app.core.services.process_service import ProcessService
from app.core.services.settings_service import SettingsService
from app.web.process_output_bus import ProcessOutputBus


@lru_cache
def get_settings_service() -> SettingsService:
    return SettingsService()


@lru_cache
def get_backtest_service() -> BacktestService:
    return BacktestService(get_settings_service())


@lru_cache
def get_download_data_service() -> DownloadDataService:
    return DownloadDataService(get_settings_service())


@lru_cache
def get_optimize_service() -> OptimizeService:
    return OptimizeService(get_settings_service())


@lru_cache
def get_process_service() -> ProcessService:
    return ProcessService()


@lru_cache
def get_process_output_bus() -> ProcessOutputBus:
    return ProcessOutputBus()


SettingsServiceDep = Annotated[SettingsService, Depends(get_settings_service)]
BacktestServiceDep = Annotated[BacktestService, Depends(get_backtest_service)]
DownloadDataServiceDep = Annotated[DownloadDataService, Depends(get_download_data_service)]
OptimizeServiceDep = Annotated[OptimizeService, Depends(get_optimize_service)]
ProcessServiceDep = Annotated[ProcessService, Depends(get_process_service)]
ProcessOutputBusDep = Annotated[ProcessOutputBus, Depends(get_process_output_bus)]
