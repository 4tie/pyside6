"""SharedInputsRouter — REST endpoints for the six shared trading input fields.

Exposes:
  GET  /api/shared-inputs  — read current SharedInputs state
  PUT  /api/shared-inputs  — partial update and persist SharedInputs state
"""

from fastapi import APIRouter, HTTPException

from app.core.models.settings_models import SharedInputsPreferences
from app.core.services.shared_inputs_service import SharedInputsService, SharedInputsUpdate
from leave.web.dependencies import SettingsServiceDep

router = APIRouter()


@router.get(
    "/shared-inputs",
    response_model=SharedInputsPreferences,
    tags=["shared-inputs"],
)
async def get_shared_inputs(settings: SettingsServiceDep) -> SharedInputsPreferences:
    """Return the current shared trading inputs from persisted settings."""
    try:
        return SharedInputsService(settings).read_config()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put(
    "/shared-inputs",
    response_model=SharedInputsPreferences,
    tags=["shared-inputs"],
)
async def put_shared_inputs(
    update: SharedInputsUpdate,
    settings: SettingsServiceDep,
) -> SharedInputsPreferences:
    """Partially update and persist the shared trading inputs."""
    try:
        return SharedInputsService(settings).write_config(update)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
