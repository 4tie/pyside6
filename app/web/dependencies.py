"""Dependency injection for FastAPI routes.

Provides singleton instances of core services for use across API endpoints.
Uses FastAPI's Depends() system for clean dependency management.
"""
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.core.services.settings_service import SettingsService
from app.core.services.backtest_service import BacktestService
from app.core.services.diagnosis_service import DiagnosisService
from app.core.services.comparison_service import ComparisonService
from app.core.services.loop_service import LoopService
from app.core.services.improve_service import ImproveService


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


# Type aliases for dependency injection
SettingsServiceDep = Annotated[SettingsService, Depends(get_settings_service)]
BacktestServiceDep = Annotated[BacktestService, Depends(get_backtest_service)]
ImproveServiceDep = Annotated[ImproveService, Depends(get_improve_service)]
DiagnosisServiceDep = Annotated[DiagnosisService, Depends(get_diagnosis_service)]
ComparisonServiceDep = Annotated[ComparisonService, Depends(get_comparison_service)]
LoopServiceDep = Annotated[LoopService, Depends(get_loop_service)]
