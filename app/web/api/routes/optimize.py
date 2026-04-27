"""Hyperopt optimization endpoint."""

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.core.services.process_service import ProcessService
from app.web.dependencies import (
    OptimizeServiceDep,
    ProcessOutputBusDep,
    ProcessServiceDep,
    SettingsServiceDep,
)
from app.web.models import OptimizeRequest

router = APIRouter()


@router.post("/optimize/run")
async def run_optimize(
    request: OptimizeRequest,
    settings: SettingsServiceDep,
    optimize_service: OptimizeServiceDep,
    process_service: ProcessServiceDep,
    bus: ProcessOutputBusDep,
    background_tasks: BackgroundTasks,
) -> dict:
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        raise HTTPException(status_code=404, detail="User data path not configured")
    if not app_settings.venv_path:
        raise HTTPException(status_code=400, detail="Virtual environment not configured")

    try:
        command = optimize_service.build_command(
            strategy_name=request.strategy,
            timeframe=request.timeframe,
            epochs=request.epochs,
            timerange=request.timerange,
            pairs=request.pairs,
            spaces=request.spaces,
            hyperopt_loss=request.hyperopt_loss,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    env = ProcessService.build_environment(app_settings.venv_path)

    def execute_optimize() -> None:
        process_service.execute_command(
            command=command.as_list(),
            on_output=bus.push_line,
            on_error=bus.push_line,
            on_finished=bus.push_finished,
            working_directory=command.cwd,
            env=env,
        )

    background_tasks.add_task(execute_optimize)
    return {
        "status": "started",
        "message": f"Hyperopt optimization started for strategy={request.strategy}",
    }
