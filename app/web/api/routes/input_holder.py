"""InputHolderRouter — REST endpoints for the seven Configure-section fields.

Exposes:
  GET  /api/optimizer/config  — read current InputHolder state
  PUT  /api/optimizer/config  — partial update and persist InputHolder state
"""

from fastapi import APIRouter, HTTPException

from app.core.models.optimizer_models import (
    OptimizerConfigResponse,
    OptimizerConfigUpdate,
)
from app.core.services.input_holder_service import InputHolderService
from app.web.dependencies import SettingsServiceDep

router = APIRouter()


@router.get(
    "/optimizer/config",
    response_model=OptimizerConfigResponse,
    tags=["optimizer-config"],
)
async def get_optimizer_config(settings: SettingsServiceDep) -> OptimizerConfigResponse:
    """Return the current InputHolder configuration from persisted settings."""
    try:
        return InputHolderService(settings).read_config()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put(
    "/optimizer/config",
    response_model=OptimizerConfigResponse,
    tags=["optimizer-config"],
)
async def put_optimizer_config(
    update: OptimizerConfigUpdate,
    settings: SettingsServiceDep,
) -> OptimizerConfigResponse:
    """Partially update and persist the InputHolder configuration."""
    try:
        return InputHolderService(settings).write_config(update)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
