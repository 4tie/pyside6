"""
Strategy Optimizer session service.

Orchestrates optimizer sessions, trial execution, Optuna integration,
and result persistence.

Architecture boundary: NO PySide6 imports in this module.
"""

import difflib
import math
import os
import re
import shutil
import subprocess
import threading
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import optuna
from sqlalchemy import event, text

from app.core.models.optimizer_models import (
    ApplyTrialResult,
    BestPointer,
    ExportResult,
    OptimizerSession,
    ParamDef,
    ParamType,
    SessionConfig,
    SessionStatus,
    TrialDiff,
    TrialMetrics,
    TrialParamChange,
    TrialRecord,
    TrialStatus,
)
from app.core.parsing.backtest_parser import parse_backtest_results_from_zip
from app.core.parsing.json_parser import parse_json_file, write_json_file_atomic
from app.core.services.optimizer_store import OptimizerStore
from app.core.services.settings_service import SettingsService
from app.core.utils.app_logger import get_logger

_log = get_logger("services.optimizer_session")

# Suppress Optuna's verbose logging
optuna.logging.set_verbosity(optuna.logging.WARNING)

SCORE_METRICS = frozenset({
    "total_profit_pct",
    "total_profit_abs",
    "sharpe_ratio",
    "profit_factor",
    "win_rate",
})

_MISSING_VALUE = "<absent>"


def compute_optimizer_score(metrics: Dict[str, Any], score_metric: str) -> float:
    """
    Compute a finite float score from a backtest metrics dict.

    Always returns a finite float — never NaN, +Inf, or -Inf.
    Returns 0.0 for unknown metrics, missing keys, None values,
    non-numeric values, or non-finite values.

    Parameters
    ----------
    metrics:
        Dict of backtest metric names to values.
    score_metric:
        One of: total_profit_pct, total_profit_abs, sharpe_ratio,
        profit_factor, win_rate.

    Returns
    -------
    float
        A finite float score. Higher is better.
    """
    if score_metric not in SCORE_METRICS:
        _log.warning("Unknown score metric %r — returning 0.0", score_metric)
        return 0.0

    raw = metrics.get(score_metric)
    if raw is None:
        return 0.0

    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0

    if not math.isfinite(value):
        return 0.0

    return value


def compute_enhanced_composite_score(
    metrics: Dict[str, Any],
    config: Any,
) -> tuple[float, Dict[str, float]]:
    """
    Compute a non-linear, risk-adjusted optimizer score.

    The score is finite for all inputs and combines capped return, logarithmic
    trade confidence, quadratic drawdown penalty, RoMAD, profit factor, win
    rate, and Sharpe into one Optuna-friendly objective.
    """
    total_trades = max(0, int(_sanitize_float(metrics.get("total_trades", 0))))
    total_profit_pct = _sanitize_float(metrics.get("total_profit_pct", 0.0))
    max_drawdown_pct = _sanitize_float(metrics.get("max_drawdown_pct", 0.0))
    profit_factor = _sanitize_float(metrics.get("profit_factor", 0.0))
    sharpe_ratio = _sanitize_float(metrics.get("sharpe_ratio", 0.0))
    win_rate = _sanitize_float(metrics.get("win_rate", 0.0))
    if 0.0 <= win_rate <= 1.0:
        win_rate *= 100.0

    target_min_trades = _positive_config_float(config, "target_min_trades", 100.0)
    target_profit_pct = _positive_config_float(config, "target_profit_pct", 50.0)
    max_drawdown_limit = _positive_config_float(config, "max_drawdown_limit", 25.0)
    target_romad = _positive_config_float(config, "target_romad", 2.0)

    trade_ln = math.log(max(1.0, float(total_trades)))
    target_ln = math.log(max(2.0, target_min_trades))
    trade_count_score = _clamp(trade_ln / target_ln, 0.0, 1.0)

    dd_ratio = _clamp(max(0.0, max_drawdown_pct) / max(0.01, max_drawdown_limit), 0.0, 1.0)
    drawdown_score = 1.0 - (dd_ratio ** 2)

    romad = total_profit_pct / max(0.1, max_drawdown_pct) if total_profit_pct > 0 else 0.0
    romad_score = _clamp(romad / target_romad, -1.0, 1.0)

    profit_score = _clamp(total_profit_pct / max(0.01, target_profit_pct), -1.0, 1.0)
    profit_factor_score = _clamp((profit_factor - 1.0) / 2.0, -1.0, 1.0)
    win_rate_score = _clamp((win_rate - 40.0) / 30.0, 0.0, 1.0)
    sharpe_score = _clamp(sharpe_ratio / 3.0, -1.0, 1.0)

    base_score = (
        (0.25 * romad_score)
        + (0.20 * profit_score)
        + (0.20 * drawdown_score)
        + (0.15 * trade_count_score)
        + (0.10 * profit_factor_score)
        + (0.05 * win_rate_score)
        + (0.05 * sharpe_score)
    )

    final_score = base_score
    if total_trades < target_min_trades:
        final_score *= total_trades / max(1.0, target_min_trades)
    if max_drawdown_pct > max_drawdown_limit:
        final_score -= 0.50
    if total_profit_pct <= 0:
        final_score -= 1.0
    if not math.isfinite(final_score):
        final_score = -2.0

    breakdown = {
        "trade_count_score": round(trade_count_score, 4),
        "profit_score": round(profit_score, 4),
        "drawdown_score": round(drawdown_score, 4),
        "romad_score": round(romad_score, 4),
        "profit_factor_score": round(profit_factor_score, 4),
        "sharpe_score": round(sharpe_score, 4),
        "win_rate_score": round(win_rate_score, 4),
        "base_score": round(base_score, 4),
        "final_score": round(final_score, 4),
    }
    return float(final_score), breakdown


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(value, max_value))


def _positive_config_float(config: Any, name: str, default: float) -> float:
    value = _sanitize_float(getattr(config, name, default))
    return value if value > 0 else default


def _sanitize_float(value: Any) -> float:
    """Convert any value to a finite float, returning 0.0 for non-finite/None."""
    if value is None:
        return 0.0
    try:
        f = float(value)
        return f if math.isfinite(f) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _group_candidate_params(candidate: Dict[str, Any], param_defs: List[ParamDef]) -> Dict[str, Any]:
    """Convert sampled flat optimizer params into Freqtrade strategy param groups."""
    grouped: Dict[str, Any] = {}
    spaces_by_name = {param_def.name: param_def.space for param_def in param_defs}

    for name, value in candidate.items():
        space = spaces_by_name.get(name, "")
        if space == "buy":
            grouped.setdefault("buy_params", {})[name] = value
        elif space == "sell":
            grouped.setdefault("sell_params", {})[name] = value
        elif space == "roi":
            grouped.setdefault("minimal_roi", {})[name] = value
        elif space == "stoploss":
            grouped["stoploss"] = value
        elif space == "trailing":
            grouped[name] = value
        else:
            grouped.setdefault("buy_params", {})[name] = value

    return grouped


def _build_freqtrade_params_file(
    strategy_name: str,
    grouped_params: Dict[str, Any],
    base_params_file: Path,
) -> Dict[str, Any]:
    """Build a Freqtrade strategy JSON file from grouped optimizer params."""
    try:
        from app.core.parsing.json_parser import parse_json_file

        base = parse_json_file(base_params_file) if base_params_file.exists() else {}
    except Exception:
        base = {}

    ft_params = dict(base.get("params", {}))

    if grouped_params.get("buy_params"):
        ft_params["buy"] = grouped_params["buy_params"]
    if grouped_params.get("sell_params"):
        ft_params["sell"] = grouped_params["sell_params"]
    if grouped_params.get("minimal_roi"):
        ft_params["roi"] = grouped_params["minimal_roi"]
    if grouped_params.get("stoploss") is not None:
        ft_params["stoploss"] = {"stoploss": grouped_params["stoploss"]}
    if grouped_params.get("max_open_trades") is not None:
        ft_params["max_open_trades"] = {"max_open_trades": grouped_params["max_open_trades"]}

    trailing_keys = {
        "trailing_stop",
        "trailing_stop_positive",
        "trailing_stop_positive_offset",
        "trailing_only_offset_is_reached",
    }
    trailing_updates = {
        key: grouped_params[key]
        for key in trailing_keys
        if key in grouped_params and grouped_params[key] is not None
    }
    if trailing_updates:
        trailing = dict(ft_params.get("trailing", {}))
        trailing.update(trailing_updates)
        ft_params["trailing"] = trailing

    base["strategy_name"] = strategy_name
    base["params"] = ft_params
    base["ft_stratparam_v"] = 1
    base["export_time"] = datetime.now(timezone.utc).isoformat()
    return base


def _flatten_params(data: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten Freqtrade params JSON into stable diff keys."""
    params = data.get("params", data)
    if not isinstance(params, dict):
        return {}

    flat: Dict[str, Any] = {}
    for group, value in params.items():
        if isinstance(value, dict):
            for key, item_value in value.items():
                flat[f"{group}.{key}"] = item_value
        else:
            flat[str(group)] = value
    return flat


def _validate_strategy_name(strategy_name: str) -> str:
    """Normalize and validate a strategy name or filename."""
    name = strategy_name.strip()
    if name.endswith(".py"):
        name = name[:-3]
    if not name.isidentifier():
        raise ValueError("Strategy name must be a valid Python identifier.")
    return name


def _rename_first_strategy_class(source: str, new_strategy_name: str) -> str:
    """Rename the first class definition in a strategy source file."""
    replacement = rf"\g<prefix>{new_strategy_name}\g<suffix>"
    renamed, count = re.subn(
        r"^(?P<prefix>\s*class\s+)(?P<name>[A-Za-z_]\w*)(?P<suffix>\s*(?:\(|:))",
        replacement,
        source,
        count=1,
        flags=re.MULTILINE,
    )
    if count != 1:
        raise ValueError("Could not find a strategy class definition to rename.")
    return renamed


def _write_text_atomic(file_path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write text atomically using a temp file in the destination directory."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = file_path.with_suffix(file_path.suffix + ".tmp")
    try:
        tmp_path.write_text(text, encoding=encoding)
        os.replace(tmp_path, file_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _create_optuna_study(db_path: Path, study_name: str) -> optuna.Study:
    """Create an Optuna study with SQLite WAL mode enabled."""
    storage_url = f"sqlite:///{db_path}"
    storage = optuna.storages.RDBStorage(
        url=storage_url,
        engine_kwargs={"connect_args": {"check_same_thread": False}},
    )

    @event.listens_for(storage.engine, "connect")
    def set_wal_mode(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")

    with storage.engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))

    return optuna.create_study(
        study_name=study_name,
        storage=storage,
        direction="maximize",
        load_if_exists=True,
    )


class StrategyOptimizerService:
    """
    Orchestrates optimizer sessions, trial execution, Optuna integration,
    and result persistence.

    Architecture boundary: NO PySide6 imports.
    """

    def __init__(
        self,
        settings_service: SettingsService,
        backtest_service,  # BacktestService — avoid circular import
        process_service=None,
        rollback_service=None,
    ) -> None:
        from app.core.services.process_service import ProcessService
        from app.core.services.rollback_service import RollbackService

        self._settings = settings_service
        self._backtest = backtest_service
        self._process = process_service or ProcessService()
        self._rollback = rollback_service or RollbackService()
        self._store = OptimizerStore(settings_service)

        self._active_session: Optional[OptimizerSession] = None
        self._active_study: Optional[optuna.Study] = None
        self._stop_requested: bool = False
        self._active_subprocess: Optional[subprocess.Popen] = None

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(self, config: SessionConfig) -> OptimizerSession:
        """Create a new optimizer session with a UUID4 session_id."""
        session_id = str(uuid.uuid4())
        session = OptimizerSession(
            session_id=session_id,
            status=SessionStatus.PENDING,
            config=config,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        # Create session directory
        session_dir = self._store.session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)

        # Persist session config
        write_json_file_atomic(
            session_dir / "session_config.json",
            config.model_dump(mode="json"),
        )

        # Create Optuna study with WAL mode
        db_path = session_dir / "study.db"
        study = _create_optuna_study(db_path, study_name=session_id)
        self._active_study = study

        # Save initial session state
        self._store.save_session(session)
        self._active_session = session

        _log.info("Created session %s for strategy %s", session_id, config.strategy_name)
        return session

    def run_session_async(
        self,
        session: OptimizerSession,
        on_trial_start: Optional[Callable[[int, dict], None]] = None,
        on_trial_complete: Optional[Callable[[TrialRecord], None]] = None,
        on_session_complete: Optional[Callable[[OptimizerSession], None]] = None,
        on_log_line: Optional[Callable[[str], None]] = None,
    ) -> threading.Thread:
        """Run the trial loop on a background thread."""
        self._stop_requested = False
        study = self._active_study
        if study is None:
            # Reload study from disk
            session_dir = self._store.session_dir(session.session_id)
            db_path = session_dir / "study.db"
            study = _create_optuna_study(db_path, study_name=session.session_id)
            self._active_study = study

        thread = threading.Thread(
            target=self._run_trial_loop,
            args=(session, study, on_trial_start, on_trial_complete, on_session_complete, on_log_line),
            daemon=True,
            name=f"optimizer-{session.session_id[:8]}",
        )
        thread.start()
        return thread

    def stop_session(self) -> None:
        """Stop the active session: set flag and SIGTERM/SIGKILL the subprocess."""
        self._stop_requested = True
        proc = self._active_subprocess
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()  # SIGTERM
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()  # SIGKILL
            except Exception as exc:
                _log.warning("Error stopping subprocess: %s", exc)

    def set_best(self, session_id: str, trial_number: int) -> None:
        """Manually override the Accepted_Best to a specific trial."""
        record = self._store.load_trial_record(session_id, trial_number)
        if record is None:
            raise ValueError(f"Trial {trial_number} not found in session {session_id}")
        pointer = BestPointer(
            session_id=session_id,
            trial_number=trial_number,
            score=record.score or 0.0,
        )
        self._store.save_best_pointer(session_id, pointer)
        _log.info("Manually set best to trial %d for session %s", trial_number, session_id)

    def export_best(self, session_id: str) -> ExportResult:
        """Export Accepted_Best params to the live strategy JSON."""
        pointer = self._store.load_best_pointer(session_id)
        if pointer is None:
            return ExportResult(success=False, error_message="No best pointer found")

        record = self._store.load_trial_record(session_id, pointer.trial_number)
        if record is None:
            return ExportResult(success=False, error_message=f"Trial {pointer.trial_number} not found")

        session = self._store.load_session(session_id)
        if session is None:
            return ExportResult(success=False, error_message=f"Session {session_id} not found")

        settings = self._settings.load_settings()
        user_data = settings.user_data_path or "user_data"
        live_json = Path(user_data) / "strategies" / f"{session.config.strategy_name}.json"

        try:
            # (a) Backup current live JSON
            backup_path = self._rollback._backup_file(live_json)

            # (b+c+d) Write candidate params atomically (temp file in same dir)
            grouped_params = _group_candidate_params(
                record.candidate_params,
                session.config.param_defs,
            )
            write_json_file_atomic(
                live_json,
                _build_freqtrade_params_file(
                    session.config.strategy_name,
                    grouped_params,
                    live_json,
                ),
            )

            # Prune old backups
            self._rollback._prune_backups(live_json)

            _log.info("Exported best (trial %d) to %s", pointer.trial_number, live_json)
            return ExportResult(
                success=True,
                live_json_path=str(live_json),
                backup_path=str(backup_path),
            )
        except Exception as exc:
            _log.error("Export failed: %s", exc)
            return ExportResult(success=False, error_message=str(exc))

    def build_trial_diff(self, session_id: str, trial_number: int) -> TrialDiff:
        """Build a selected-trial diff against the current live strategy files."""
        try:
            session, record = self._load_successful_trial(session_id, trial_number)
            paths = self._trial_artifact_paths(session, trial_number)
            if not paths["trial_py"].exists():
                raise FileNotFoundError(f"Trial strategy file not found: {paths['trial_py']}")
            live_params = self._load_json_default(paths["live_json"])
            trial_params = self._load_trial_params_json(session, record, paths["trial_json"])

            current_flat = _flatten_params(live_params)
            trial_flat = _flatten_params(trial_params)
            param_changes = [
                TrialParamChange(
                    key=key,
                    current_value=current_flat.get(key, _MISSING_VALUE),
                    trial_value=trial_flat.get(key, _MISSING_VALUE),
                )
                for key in sorted(set(current_flat) | set(trial_flat))
                if current_flat.get(key, _MISSING_VALUE) != trial_flat.get(key, _MISSING_VALUE)
            ]

            live_source = self._read_text_default(paths["live_py"])
            trial_source = self._read_text_default(paths["trial_py"])
            strategy_diff = "".join(
                difflib.unified_diff(
                    live_source.splitlines(keepends=True),
                    trial_source.splitlines(keepends=True),
                    fromfile=str(paths["live_py"]),
                    tofile=str(paths["trial_py"]),
                )
            )

            return TrialDiff(
                success=True,
                param_changes=param_changes,
                strategy_diff=strategy_diff,
                live_strategy_path=str(paths["live_py"]),
                trial_strategy_path=str(paths["trial_py"]),
                live_json_path=str(paths["live_json"]),
                trial_json_path=str(paths["trial_json"]),
            )
        except Exception as exc:
            _log.warning("Could not build selected trial diff: %s", exc)
            return TrialDiff(success=False, error_message=str(exc))

    def apply_trial_to_strategy(self, session_id: str, trial_number: int) -> ApplyTrialResult:
        """Apply selected trial .py and params JSON to the existing strategy."""
        try:
            session, record = self._load_successful_trial(session_id, trial_number)
            paths = self._trial_artifact_paths(session, trial_number)
            if not paths["trial_py"].exists():
                raise FileNotFoundError(f"Trial strategy file not found: {paths['trial_py']}")

            trial_params = self._load_trial_params_json(session, record, paths["trial_json"])
            backup_paths = [
                self._backup_any_file(paths["live_py"]),
                self._backup_any_file(paths["live_json"]),
            ]

            _write_text_atomic(paths["live_py"], paths["trial_py"].read_text(encoding="utf-8"))
            trial_params["strategy_name"] = session.config.strategy_name
            write_json_file_atomic(paths["live_json"], trial_params)
            self._rollback._prune_backups(paths["live_py"])
            self._rollback._prune_backups(paths["live_json"])

            _log.info(
                "Applied selected trial %d to existing strategy %s",
                trial_number,
                session.config.strategy_name,
            )
            return ApplyTrialResult(
                success=True,
                strategy_py_path=str(paths["live_py"]),
                strategy_json_path=str(paths["live_json"]),
                backup_paths=[str(path) for path in backup_paths],
            )
        except Exception as exc:
            _log.error("Apply selected trial failed: %s", exc)
            return ApplyTrialResult(success=False, error_message=str(exc))

    def apply_trial_as_new_strategy(
        self,
        session_id: str,
        trial_number: int,
        new_strategy_name: str,
    ) -> ApplyTrialResult:
        """Apply selected trial artifacts as a new strategy .py/.json pair."""
        try:
            name = _validate_strategy_name(new_strategy_name)
            session, record = self._load_successful_trial(session_id, trial_number)
            paths = self._trial_artifact_paths(session, trial_number)
            if not paths["trial_py"].exists():
                raise FileNotFoundError(f"Trial strategy file not found: {paths['trial_py']}")

            strategies_dir = paths["live_py"].parent
            new_py = strategies_dir / f"{name}.py"
            new_json = strategies_dir / f"{name}.json"
            if new_py.exists() or new_json.exists():
                raise FileExistsError(f"Strategy {name!r} already exists.")

            source = paths["trial_py"].read_text(encoding="utf-8")
            renamed_source = _rename_first_strategy_class(source, name)
            trial_params = self._load_trial_params_json(session, record, paths["trial_json"])
            trial_params["strategy_name"] = name

            _write_text_atomic(new_py, renamed_source)
            write_json_file_atomic(new_json, trial_params)

            _log.info("Applied selected trial %d as new strategy %s", trial_number, name)
            return ApplyTrialResult(
                success=True,
                strategy_py_path=str(new_py),
                strategy_json_path=str(new_json),
            )
        except Exception as exc:
            _log.error("Apply selected trial as new strategy failed: %s", exc)
            return ApplyTrialResult(success=False, error_message=str(exc))

    def _load_successful_trial(
        self,
        session_id: str,
        trial_number: int,
    ) -> tuple[OptimizerSession, TrialRecord]:
        session = self._store.load_session(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        record = self._store.load_trial_record(session_id, trial_number)
        if record is None:
            raise ValueError(f"Trial {trial_number} not found in session {session_id}")
        if record.status != TrialStatus.SUCCESS:
            raise ValueError("Only successful selected trials can be applied.")
        return session, record

    def _trial_artifact_paths(
        self,
        session: OptimizerSession,
        trial_number: int,
    ) -> Dict[str, Path]:
        settings = self._settings.load_settings()
        user_data = settings.user_data_path or "user_data"
        strategies_dir = Path(user_data) / "strategies"
        trial_dir = self._store.trial_dir(session.session_id, trial_number)
        strategy_dir = trial_dir / "strategy_dir"
        return {
            "live_py": strategies_dir / f"{session.config.strategy_name}.py",
            "live_json": strategies_dir / f"{session.config.strategy_name}.json",
            "trial_py": strategy_dir / f"{session.config.strategy_name}.py",
            "trial_json": strategy_dir / f"{session.config.strategy_class}.json",
        }

    def _load_trial_params_json(
        self,
        session: OptimizerSession,
        record: TrialRecord,
        trial_json: Path,
    ) -> Dict[str, Any]:
        if trial_json.exists():
            return parse_json_file(trial_json)
        grouped_params = _group_candidate_params(record.candidate_params, session.config.param_defs)
        return _build_freqtrade_params_file(
            session.config.strategy_name,
            grouped_params,
            Path(),
        )

    @staticmethod
    def _load_json_default(path: Path) -> Dict[str, Any]:
        try:
            return parse_json_file(path) if path.exists() else {}
        except Exception:
            return {}

    @staticmethod
    def _read_text_default(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8") if path.exists() else ""
        except Exception:
            return ""

    @staticmethod
    def _backup_any_file(active_path: Path) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        backup_path = active_path.parent / f"{active_path.name}.bak_{timestamp}"
        if not active_path.exists():
            return backup_path
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(active_path, backup_path)
        return backup_path

    # ------------------------------------------------------------------
    # Trial loop (background thread)
    # ------------------------------------------------------------------

    def _run_trial_loop(
        self,
        session: OptimizerSession,
        study: optuna.Study,
        on_trial_start: Optional[Callable],
        on_trial_complete: Optional[Callable],
        on_session_complete: Optional[Callable],
        on_log_line: Optional[Callable],
    ) -> None:
        session.status = SessionStatus.RUNNING
        self._store.save_session(session)

        for trial_number in range(1, session.config.total_trials + 1):
            if self._stop_requested:
                break

            # 1. Ask Optuna for candidate params
            optuna_trial = study.ask()
            candidate = self._sample_params(optuna_trial, session.config.param_defs)

            if on_trial_start:
                try:
                    on_trial_start(trial_number, candidate)
                except Exception:
                    pass

            # 2. Execute trial
            trial_dir = self._store.trial_dir(session.session_id, trial_number)
            trial_dir.mkdir(parents=True, exist_ok=True)
            record = self._execute_trial(session, trial_number, candidate, trial_dir, on_log_line)

            # 3. Tell Optuna the result
            score = record.score if record.score is not None else 0.0
            study.tell(optuna_trial, score)

            # 4. Update best
            self._maybe_update_best(session, record)

            # 5. Persist and notify
            self._store.save_trial_record(session.session_id, record)
            session.trials_completed += 1
            self._store.save_session(session)

            if on_trial_complete:
                try:
                    on_trial_complete(record)
                except Exception:
                    pass

        session.status = SessionStatus.STOPPED if self._stop_requested else SessionStatus.COMPLETED
        session.finished_at = datetime.now(timezone.utc).isoformat()
        self._store.save_session(session)

        if on_session_complete:
            try:
                on_session_complete(session)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Optuna parameter sampling
    # ------------------------------------------------------------------

    def _sample_params(self, optuna_trial, param_defs: List[ParamDef]) -> Dict[str, Any]:
        """Map enabled ParamDef entries to Optuna suggest_* calls."""
        params: Dict[str, Any] = {}
        for param_def in param_defs:
            if not param_def.enabled:
                params[param_def.name] = param_def.default
                continue

            try:
                if param_def.param_type == ParamType.INT:
                    low = int(param_def.low or 0)
                    high = int(param_def.high or 1)
                    params[param_def.name] = optuna_trial.suggest_int(param_def.name, low, high)

                elif param_def.param_type == ParamType.DECIMAL:
                    low = float(param_def.low or 0.0)
                    high = float(param_def.high or 1.0)
                    params[param_def.name] = optuna_trial.suggest_float(param_def.name, low, high)

                elif param_def.param_type == ParamType.CATEGORICAL:
                    categories = param_def.categories or [param_def.default]
                    params[param_def.name] = optuna_trial.suggest_categorical(param_def.name, categories)

                elif param_def.param_type == ParamType.BOOLEAN:
                    params[param_def.name] = optuna_trial.suggest_categorical(
                        param_def.name, [True, False]
                    )
                else:
                    params[param_def.name] = param_def.default

            except Exception as exc:
                _log.warning("Failed to sample param %s: %s — using default", param_def.name, exc)
                params[param_def.name] = param_def.default

        return params

    # ------------------------------------------------------------------
    # Trial execution
    # ------------------------------------------------------------------

    def _execute_trial(
        self,
        session: OptimizerSession,
        trial_number: int,
        candidate: Dict[str, Any],
        trial_dir: Path,
        on_log_line: Optional[Callable],
    ) -> TrialRecord:
        """Execute one backtest trial and return a TrialRecord."""
        record = TrialRecord(
            session_id=session.session_id,
            trial_number=trial_number,
            status=TrialStatus.RUNNING,
            candidate_params=candidate,
            score_metric=session.config.score_metric,
            score_mode=session.config.score_mode,
        )

        # Create trial strategy dir with copied .py and candidate JSON
        strategy_dir = trial_dir / "strategy_dir"
        strategy_dir.mkdir(parents=True, exist_ok=True)

        settings = self._settings.load_settings()
        user_data = settings.user_data_path or "user_data"
        strategies_path = Path(user_data) / "strategies"
        src_py = strategies_path / f"{session.config.strategy_name}.py"

        # Copy (never symlink) the strategy .py file
        if src_py.exists():
            shutil.copy2(src_py, strategy_dir / src_py.name)

        grouped_candidate = _group_candidate_params(candidate, session.config.param_defs)

        # Write candidate params JSON named after the strategy class
        params_json_path = strategy_dir / f"{session.config.strategy_class}.json"
        live_params_path = strategies_path / f"{session.config.strategy_name}.json"
        write_json_file_atomic(
            params_json_path,
            _build_freqtrade_params_file(
                session.config.strategy_class,
                grouped_candidate,
                live_params_path,
            ),
        )

        # Also write params.json in trial dir for record-keeping
        write_json_file_atomic(trial_dir / "params.json", grouped_candidate)

        # Build backtest command with --strategy-path override
        log_lines: List[str] = []

        try:
            cmd = self._backtest.build_command(
                strategy_name=session.config.strategy_class,
                timeframe=session.config.timeframe,
                timerange=session.config.timerange,
                pairs=session.config.pairs or None,
                max_open_trades=session.config.max_open_trades,
                dry_run_wallet=session.config.dry_run_wallet,
                extra_flags=["--strategy-path", str(strategy_dir)],
            )
        except Exception as exc:
            _log.error("Failed to build backtest command for trial %d: %s", trial_number, exc)
            record.status = TrialStatus.FAILED
            record.log_excerpt = str(exc)
            return record

        # Run via subprocess directly (to get Popen handle for stop_session)
        exit_code = self._run_subprocess(cmd.as_list(), log_lines, on_log_line, cmd.cwd)

        # Write trial log
        log_text = "\n".join(log_lines)
        (trial_dir / "trial.log").write_text(log_text, encoding="utf-8")
        record.log_excerpt = log_text[-2000:] if len(log_text) > 2000 else log_text

        if exit_code != 0:
            record.status = TrialStatus.FAILED
            _log.warning("Trial %d failed with exit code %d", trial_number, exit_code)
            return record

        # Parse result
        try:
            metrics = self._parse_trial_result(Path(cmd.export_dir), trial_dir)
            record.metrics = metrics
            metrics_dict = metrics.model_dump()
            if session.config.score_mode == "composite":
                record.score, record.score_breakdown = compute_enhanced_composite_score(
                    metrics_dict,
                    session.config,
                )
            else:
                record.score = compute_optimizer_score(metrics_dict, session.config.score_metric)
                record.score_breakdown = {}
            record.status = TrialStatus.SUCCESS

            # Write metrics and score artefacts
            write_json_file_atomic(trial_dir / "metrics.json", metrics.model_dump(mode="json"))
            write_json_file_atomic(
                trial_dir / "score.json",
                {
                    "score": record.score,
                    "score_metric": record.score_metric,
                    "score_mode": record.score_mode,
                    "score_breakdown": record.score_breakdown,
                },
            )
        except Exception as exc:
            _log.warning("Failed to parse trial %d result: %s", trial_number, exc)
            record.status = TrialStatus.FAILED
            record.log_excerpt += f"\nResult parse error: {exc}"

        return record

    def _run_subprocess(
        self,
        command: List[str],
        log_lines: List[str],
        on_log_line: Optional[Callable],
        cwd: str,
    ) -> int:
        """Run a subprocess, capture output, store Popen handle for stop_session."""
        try:
            proc = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=cwd,
            )
            self._active_subprocess = proc

            for line in proc.stdout:
                line = line.rstrip("\n")
                log_lines.append(line)
                if on_log_line:
                    try:
                        on_log_line(line)
                    except Exception:
                        pass

            proc.wait()
            self._active_subprocess = None
            return proc.returncode or 0
        except Exception as exc:
            _log.error("Subprocess error: %s", exc)
            self._active_subprocess = None
            return 1

    # ------------------------------------------------------------------
    # Result parsing
    # ------------------------------------------------------------------

    def _parse_trial_result(self, export_dir: Path, trial_dir: Path) -> TrialMetrics:
        """Find newest backtest zip and extract TrialMetrics."""
        zips = sorted(
            export_dir.glob("*.zip"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not zips:
            raise FileNotFoundError(f"No backtest result zip found in {export_dir}")

        results = parse_backtest_results_from_zip(str(zips[0]))
        s = results.summary

        # Copy result to trial dir
        try:
            import json
            (trial_dir / "backtest_result.json").write_text(
                json.dumps(asdict(s), indent=2), encoding="utf-8"
            )
        except Exception:
            pass

        # Map BacktestSummary → TrialMetrics with sanitization
        win_rate = _sanitize_float(s.win_rate) / 100.0 if s.win_rate > 1 else _sanitize_float(s.win_rate)

        return TrialMetrics(
            total_profit_pct=_sanitize_float(s.total_profit),
            total_profit_abs=_sanitize_float(s.total_profit_abs),
            win_rate=win_rate,
            max_drawdown_pct=_sanitize_float(s.max_drawdown),
            total_trades=s.total_trades or 0,
            profit_factor=_sanitize_float(s.profit_factor),
            sharpe_ratio=_sanitize_float(s.sharpe_ratio) if s.sharpe_ratio is not None else None,
            best_pair=s.pairlist[0] if s.pairlist else "",
            worst_pair=s.pairlist[-1] if s.pairlist else "",
            final_balance=_sanitize_float(s.final_balance),
            best_trade_profit_pct=0.0,
            worst_trade_profit_pct=0.0,
        )

    # ------------------------------------------------------------------
    # Best pointer management
    # ------------------------------------------------------------------

    def _maybe_update_best(self, session: OptimizerSession, record: TrialRecord) -> None:
        """Update best.json if this trial's score is strictly higher."""
        if record.status != TrialStatus.SUCCESS or record.score is None:
            return

        current = self._store.load_best_pointer(session.session_id)
        if current is None or record.score > current.score:
            pointer = BestPointer(
                session_id=session.session_id,
                trial_number=record.trial_number,
                score=record.score,
            )
            self._store.save_best_pointer(session.session_id, pointer)
            record.is_best = True
            session.best_pointer = pointer
            _log.info(
                "New best: trial %d score=%.4f (session %s)",
                record.trial_number,
                record.score,
                session.session_id,
            )
