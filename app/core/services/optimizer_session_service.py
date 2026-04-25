"""
Strategy Optimizer session service.

Orchestrates optimizer sessions, trial execution, Optuna integration,
and result persistence.

Architecture boundary: NO PySide6 imports in this module.
"""

import math
import shutil
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import optuna
from sqlalchemy import event, text

from app.core.models.optimizer_models import (
    BestPointer,
    ExportResult,
    OptimizerSession,
    ParamDef,
    ParamType,
    SessionConfig,
    SessionStatus,
    TrialMetrics,
    TrialRecord,
    TrialStatus,
)
from app.core.parsing.backtest_parser import parse_backtest_results_from_zip
from app.core.parsing.json_parser import write_json_file_atomic
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


def _sanitize_float(value: Any) -> float:
    """Convert any value to a finite float, returning 0.0 for non-finite/None."""
    if value is None:
        return 0.0
    try:
        f = float(value)
        return f if math.isfinite(f) else 0.0
    except (TypeError, ValueError):
        return 0.0


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
            write_json_file_atomic(live_json, record.candidate_params)

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

        # Write candidate params JSON named after the strategy class
        params_json_path = strategy_dir / f"{session.config.strategy_class}.json"
        write_json_file_atomic(params_json_path, candidate)

        # Also write params.json in trial dir for record-keeping
        write_json_file_atomic(trial_dir / "params.json", candidate)

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
            record.score = compute_optimizer_score(
                metrics.model_dump(), session.config.score_metric
            )
            record.status = TrialStatus.SUCCESS

            # Write metrics and score artefacts
            write_json_file_atomic(trial_dir / "metrics.json", metrics.model_dump(mode="json"))
            write_json_file_atomic(
                trial_dir / "score.json",
                {"score": record.score, "score_metric": record.score_metric},
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
                json.dumps(s.model_dump(mode="json"), indent=2), encoding="utf-8"
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
