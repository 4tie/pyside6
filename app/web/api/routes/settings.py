"""API endpoints for application settings.

Provides endpoints to retrieve and update application settings.
"""
from fastapi import APIRouter, HTTPException, Depends

from app.core.models.optimizer_models import OptimizerPreferences
from app.core.models.settings_models import BacktestPreferences
from app.core.services.settings_service import SettingsService
from app.web.dependencies import SettingsServiceDep
from app.web.models import SettingsResponse, SettingsUpdate

router = APIRouter()


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(
    settings: SettingsServiceDep,
) -> SettingsResponse:
    """Get current application settings."""
    app_settings = settings.load_settings()
    
    return SettingsResponse(
        user_data_path=app_settings.user_data_path or "",
        venv_path=app_settings.venv_path or "",
        python_executable=app_settings.python_executable or "",
        freqtrade_executable=app_settings.freqtrade_executable or "",
        use_module_execution=app_settings.use_module_execution,
        backtest_preferences=app_settings.backtest_preferences.model_dump(mode="json"),
        optimizer_preferences=app_settings.optimizer_preferences.model_dump(mode="json"),
    )


@router.put("/settings")
async def update_settings(
    update: SettingsUpdate,
    settings: SettingsServiceDep,
) -> SettingsResponse:
    """Update application settings."""
    app_settings = settings.load_settings()
    
    # Update only the fields that are provided
    if update.user_data_path is not None:
        app_settings.user_data_path = update.user_data_path
    if update.venv_path is not None:
        app_settings.venv_path = update.venv_path
    if update.python_executable is not None:
        app_settings.python_executable = update.python_executable
    if update.freqtrade_executable is not None:
        app_settings.freqtrade_executable = update.freqtrade_executable
    if update.backtest_preferences is not None:
        merged = app_settings.backtest_preferences.model_dump()
        merged.update(update.backtest_preferences)
        app_settings.backtest_preferences = BacktestPreferences.model_validate(merged)
    if update.optimizer_preferences is not None:
        merged = app_settings.optimizer_preferences.model_dump()
        merged.update(update.optimizer_preferences)
        app_settings.optimizer_preferences = OptimizerPreferences.model_validate(merged)
    
    # Save the updated settings
    settings.save_settings(app_settings)
    
    return SettingsResponse(
        user_data_path=app_settings.user_data_path or "",
        venv_path=app_settings.venv_path or "",
        python_executable=app_settings.python_executable or "",
        freqtrade_executable=app_settings.freqtrade_executable or "",
        use_module_execution=app_settings.use_module_execution,
        backtest_preferences=app_settings.backtest_preferences.model_dump(mode="json"),
        optimizer_preferences=app_settings.optimizer_preferences.model_dump(mode="json"),
    )
