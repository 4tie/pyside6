"""API endpoints for hyperopt optimization operations.

Provides endpoints to run hyperopt optimization.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends

from app.core.services.optimize_service import OptimizeService
from app.core.services.settings_service import SettingsService
from leave.web.dependencies import (
    SettingsServiceDep,
    OptimizeServiceDep,
    ProcessServiceDep,
    ProcessOutputBusDep,
)
from app.core.services.process_service import ProcessService

router = APIRouter()


@router.post("/optimize/run")
async def run_optimize(
    strategy: str,
    timeframe: str,
    epochs: int,
    timerange: Optional[str] = None,
    pairs: Optional[list[str]] = None,
    spaces: Optional[list[str]] = None,
    hyperopt_loss: Optional[str] = None,
    settings: SettingsServiceDep = None,
    optimize_service: OptimizeServiceDep = None,
    process_service: ProcessServiceDep = None,
    bus: ProcessOutputBusDep = None,
    background_tasks: BackgroundTasks = None,
) -> dict:
    """Run hyperopt optimization."""
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        raise HTTPException(status_code=404, detail="User data path not configured")
    
    if not app_settings.venv_path:
        raise HTTPException(
            status_code=400,
            detail="Virtual environment not configured. Please configure the venv path in settings."
        )
    
    try:
        command = optimize_service.build_command(
            strategy_name=strategy,
            timeframe=timeframe,
            epochs=epochs,
            timerange=timerange,
            pairs=pairs,
            spaces=spaces,
            hyperopt_loss=hyperopt_loss,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Strategy or configuration not found: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")
    
    env = ProcessService.build_environment(app_settings.venv_path)
    full_command = command.as_list()
    
    def execute_optimize():
        try:
            process_service.execute_command(
                command=full_command,
                on_output=bus.push_line,
                on_error=bus.push_line,
                on_finished=bus.push_finished,
                working_directory=command.cwd,
                env=env
            )
        except Exception:
            pass
    
    background_tasks.add_task(execute_optimize)
    
    return {
        "status": "started",
        "message": f"Hyperopt optimization started for strategy={strategy}",
    }
