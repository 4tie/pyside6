"""Dependency injection for FastAPI routes.

Provides singleton instances of core services for use across API endpoints.
Uses FastAPI's Depends() system for clean dependency management.
"""
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.core.services.settings_service import SettingsService
from app.core.services.backtest_service import BacktestService
from app.core.services.optimize_service import OptimizeService
from app.core.services.download_data_service import DownloadDataService
from app.core.services.diagnosis_service import DiagnosisService
from app.core.services.comparison_service import ComparisonService
from app.core.services.loop_service import LoopService
from app.core.services.improve_service import ImproveService
from app.core.services.process_service import ProcessService
from app.core.services.rollback_service import RollbackService
from leave.web.process_output_bus import ProcessOutputBus


@lru_cache
def get_settings_service() -> SettingsService:
    """Get singleton SettingsService instance."""
    return SettingsService()


@lru_cache
def get_backtest_service() -> BacktestService:
    """Get singleton BacktestService instance."""
    settings = get_settings_service()
    return BacktestService(settings)


@lru_cache
def get_improve_service() -> ImproveService:
    """Get singleton ImproveService instance."""
    settings = get_settings_service()
    backtest = get_backtest_service()
    return ImproveService(settings, backtest)


@lru_cache
def get_diagnosis_service() -> DiagnosisService:
    """Get singleton DiagnosisService instance."""
    return DiagnosisService()


@lru_cache
def get_comparison_service() -> ComparisonService:
    """Get singleton ComparisonService instance."""
    return ComparisonService()


@lru_cache
def get_loop_service() -> LoopService:
    """Get singleton LoopService instance."""
    settings = get_settings_service()
    backtest = get_backtest_service()
    diagnosis = get_diagnosis_service()
    improve = get_improve_service()
    return LoopService(settings, backtest, diagnosis, improve)


@lru_cache
def get_process_service() -> ProcessService:
    """Get singleton ProcessService instance."""
    return ProcessService()


@lru_cache
def get_optimize_service() -> OptimizeService:
    """Get singleton OptimizeService instance."""
    settings = get_settings_service()
    return OptimizeService(settings)


@lru_cache
def get_download_data_service() -> DownloadDataService:
    """Get singleton DownloadDataService instance."""
    settings = get_settings_service()
    return DownloadDataService(settings)


@lru_cache
def get_rollback_service() -> RollbackService:
    """Get singleton RollbackService instance."""
    return RollbackService()


@lru_cache
def get_process_output_bus() -> ProcessOutputBus:
    """Get singleton ProcessOutputBus instance."""
    return ProcessOutputBus()


# Type aliases for dependency injection
SettingsServiceDep = Annotated[SettingsService, Depends(get_settings_service)]
BacktestServiceDep = Annotated[BacktestService, Depends(get_backtest_service)]
OptimizeServiceDep = Annotated[OptimizeService, Depends(get_optimize_service)]
DownloadDataServiceDep = Annotated[DownloadDataService, Depends(get_download_data_service)]
ImproveServiceDep = Annotated[ImproveService, Depends(get_improve_service)]
DiagnosisServiceDep = Annotated[DiagnosisService, Depends(get_diagnosis_service)]
ComparisonServiceDep = Annotated[ComparisonService, Depends(get_comparison_service)]
LoopServiceDep = Annotated[LoopService, Depends(get_loop_service)]
ProcessServiceDep = Annotated[ProcessService, Depends(get_process_service)]
RollbackServiceDep = Annotated[RollbackService, Depends(get_rollback_service)]
ProcessOutputBusDep = Annotated[ProcessOutputBus, Depends(get_process_output_bus)]
