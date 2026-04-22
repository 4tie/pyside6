"""API endpoints for application settings.

Provides endpoints to retrieve and update application settings.
"""
from fastapi import APIRouter, HTTPException, Depends

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
    
    # Save the updated settings
    settings.save_settings(app_settings)
    
    return SettingsResponse(
        user_data_path=app_settings.user_data_path or "",
        venv_path=app_settings.venv_path or "",
        python_executable=app_settings.python_executable or "",
        freqtrade_executable=app_settings.freqtrade_executable or "",
        use_module_execution=app_settings.use_module_execution,
    )
