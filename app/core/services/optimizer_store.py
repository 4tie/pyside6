"""
Filesystem persistence layer for the Strategy Optimizer.

Manages the directory layout under {user_data}/optimizer/sessions/
and provides atomic read/write operations for sessions, trials, and
the best-pointer file.

Directory layout:
    {user_data}/optimizer/sessions/
        {session_id}/
            session.json          ← OptimizerSession
            session_config.json   ← SessionConfig snapshot
            best.json             ← BestPointer
            study.db              ← Optuna SQLite RDB storage
            trial_001/
                params.json
                metrics.json
                score.json
                backtest_result.json
                trial.log
                strategy_dir/
            trial_002/
                ...

Architecture boundary: NO PySide6 imports in this module.
"""

import shutil
from pathlib import Path
from typing import List, Optional

from app.core.models.optimizer_models import (
    BestPointer,
    OptimizerSession,
    TrialRecord,
)
from app.core.parsing.json_parser import ParseError, parse_json_file, write_json_file_atomic
from app.core.services.settings_service import SettingsService
from app.core.utils.app_logger import get_logger

_log = get_logger("services.optimizer_store")


class OptimizerStore:
    """
    Filesystem persistence layer for optimizer sessions and trials.

    All writes are atomic (temp-file + os.replace via write_json_file_atomic).
    All reads return None / empty list gracefully when files are absent.
    """

    def __init__(self, settings_service: SettingsService) -> None:
        self._settings = settings_service

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def sessions_root(self) -> Path:
        """Return the root directory for all optimizer sessions."""
        settings = self._settings.load_settings()
        user_data = settings.user_data_path or "user_data"
        return Path(user_data).expanduser().absolute() / "optimizer" / "sessions"

    def session_dir(self, session_id: str) -> Path:
        """Return the directory for a specific session."""
        return self.sessions_root() / session_id

    def trial_dir(self, session_id: str, trial_number: int) -> Path:
        """Return the directory for a specific trial."""
        return self.session_dir(session_id) / f"trial_{trial_number:03d}"

    # ------------------------------------------------------------------
    # Session operations
    # ------------------------------------------------------------------

    def save_session(self, session: OptimizerSession) -> None:
        """Persist an OptimizerSession to session.json."""
        path = self.session_dir(session.session_id) / "session.json"
        try:
            write_json_file_atomic(path, session.model_dump(mode="json"))
            _log.debug("Saved session %s", session.session_id)
        except ParseError as exc:
            _log.error("Failed to save session %s: %s", session.session_id, exc)
            raise

    def load_session(self, session_id: str) -> Optional[OptimizerSession]:
        """Load an OptimizerSession from session.json, or None if not found."""
        path = self.session_dir(session_id) / "session.json"
        try:
            data = parse_json_file(path)
            return OptimizerSession.model_validate(data)
        except ParseError as exc:
            _log.warning("Cannot load session %s: %s", session_id, exc)
            return None
        except Exception as exc:
            _log.warning("Invalid session data for %s: %s", session_id, exc)
            return None

    def list_sessions(self) -> List[OptimizerSession]:
        """
        Return all persisted sessions sorted newest-first by started_at.

        Silently skips directories that cannot be loaded.
        """
        root = self.sessions_root()
        if not root.exists():
            return []

        sessions: List[OptimizerSession] = []
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            session = self.load_session(entry.name)
            if session is not None:
                sessions.append(session)

        # Sort newest-first; sessions without started_at sort last
        sessions.sort(key=lambda s: s.started_at or "", reverse=True)
        return sessions

    def delete_session(self, session_id: str) -> None:
        """Remove the entire session directory."""
        path = self.session_dir(session_id)
        if path.exists():
            shutil.rmtree(path)
            _log.info("Deleted session %s", session_id)
        else:
            _log.warning("Session directory not found for %s", session_id)

    # ------------------------------------------------------------------
    # Trial record operations
    # ------------------------------------------------------------------

    def save_trial_record(self, session_id: str, record: TrialRecord) -> None:
        """Persist a TrialRecord to trial_{n:03d}/trial_record.json."""
        trial_path = self.trial_dir(session_id, record.trial_number)
        trial_path.mkdir(parents=True, exist_ok=True)
        path = trial_path / "trial_record.json"
        try:
            write_json_file_atomic(path, record.model_dump(mode="json"))
            _log.debug("Saved trial %d for session %s", record.trial_number, session_id)
        except ParseError as exc:
            _log.error("Failed to save trial %d: %s", record.trial_number, exc)
            raise

    def load_trial_record(self, session_id: str, trial_number: int) -> Optional[TrialRecord]:
        """Load a TrialRecord, or None if not found."""
        path = self.trial_dir(session_id, trial_number) / "trial_record.json"
        try:
            data = parse_json_file(path)
            return TrialRecord.model_validate(data)
        except ParseError as exc:
            _log.warning("Cannot load trial %d for session %s: %s", trial_number, session_id, exc)
            return None
        except Exception as exc:
            _log.warning("Invalid trial data %d for session %s: %s", trial_number, session_id, exc)
            return None

    def load_all_trial_records(self, session_id: str) -> List[TrialRecord]:
        """
        Load all trial records for a session, sorted by trial_number ascending.

        Silently skips trial directories that cannot be loaded.
        """
        session_path = self.session_dir(session_id)
        if not session_path.exists():
            return []

        records: List[TrialRecord] = []
        for entry in session_path.iterdir():
            if not entry.is_dir() or not entry.name.startswith("trial_"):
                continue
            try:
                trial_number = int(entry.name.split("_")[1])
            except (IndexError, ValueError):
                continue
            record = self.load_trial_record(session_id, trial_number)
            if record is not None:
                records.append(record)

        records.sort(key=lambda r: r.trial_number)
        return records

    # ------------------------------------------------------------------
    # Best pointer operations
    # ------------------------------------------------------------------

    def save_best_pointer(self, session_id: str, pointer: BestPointer) -> None:
        """Persist the BestPointer to best.json."""
        path = self.session_dir(session_id) / "best.json"
        try:
            write_json_file_atomic(path, pointer.model_dump(mode="json"))
            _log.debug(
                "Saved best pointer for session %s → trial %d",
                session_id,
                pointer.trial_number,
            )
        except ParseError as exc:
            _log.error("Failed to save best pointer for session %s: %s", session_id, exc)
            raise

    def load_best_pointer(self, session_id: str) -> Optional[BestPointer]:
        """Load the BestPointer, or None if not found."""
        path = self.session_dir(session_id) / "best.json"
        try:
            data = parse_json_file(path)
            return BestPointer.model_validate(data)
        except ParseError as exc:
            _log.warning("Cannot load best pointer for session %s: %s", session_id, exc)
            return None
        except Exception as exc:
            _log.warning("Invalid best pointer data for session %s: %s", session_id, exc)
            return None
