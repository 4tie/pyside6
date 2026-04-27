"""Application settings endpoints."""

from fastapi import APIRouter, HTTPException

from app.web.dependencies import SettingsServiceDep
from app.web.models import SettingsResponse, SettingsUpdate

router = APIRouter()


def _settings_response(app_settings) -> SettingsResponse:
    return SettingsResponse(
        user_data_path=app_settings.user_data_path or "",
        venv_path=app_settings.venv_path or "",
        python_executable=app_settings.python_executable or "",
        freqtrade_executable=app_settings.freqtrade_executable or "",
        use_module_execution=app_settings.use_module_execution,
        backtest_preferences=app_settings.backtest_preferences.model_dump(mode="json"),
        optimize_preferences=app_settings.optimize_preferences.model_dump(mode="json"),
        download_preferences=app_settings.download_preferences.model_dump(mode="json"),
        optimizer_preferences=app_settings.optimizer_preferences.model_dump(mode="json"),
    )


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(settings: SettingsServiceDep) -> SettingsResponse:
    return _settings_response(settings.load_settings())


@router.post("/settings/validate")
async def validate_settings(settings: SettingsServiceDep) -> dict:
    result = settings.validate_settings(settings.load_settings())
    return {
        "valid": result.valid,
        "python_ok": result.python_ok,
        "freqtrade_ok": result.freqtrade_ok,
        "user_data_ok": result.user_data_ok,
        "message": result.message,
        "details": result.details,
    }


@router.put("/settings", response_model=SettingsResponse)
async def update_settings(update: SettingsUpdate, settings: SettingsServiceDep) -> SettingsResponse:
    app_settings = settings.load_settings()

    for field_name in (
        "user_data_path",
        "venv_path",
        "python_executable",
        "freqtrade_executable",
        "use_module_execution",
    ):
        value = getattr(update, field_name)
        if value is not None:
            setattr(app_settings, field_name, value)

    if not settings.save_settings(app_settings):
        raise HTTPException(status_code=500, detail="Failed to save settings")

    for section_name in (
        "backtest_preferences",
        "optimize_preferences",
        "download_preferences",
        "optimizer_preferences",
    ):
        values = getattr(update, section_name)
        if values is not None:
            try:
                settings.update_preferences(section_name, **values)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            except RuntimeError as exc:
                raise HTTPException(status_code=500, detail=str(exc)) from exc

    return _settings_response(settings.load_settings())
