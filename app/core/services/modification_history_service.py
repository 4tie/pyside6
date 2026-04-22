"""
modification_history_service.py — Service for tracking modification history.

Provides detailed tracking of parameter changes and their outcomes.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.models.modification_models import ModificationHistory, ModificationRecord
from app.core.utils.app_logger import get_logger

_log = get_logger("services.modification_history")


class ModificationHistoryService:
    """Service for managing modification history.

    Persists history to user_data/modification_history.json
    """

    _HISTORY_FILE = "modification_history.json"

    def __init__(self, user_data_path: str) -> None:
        """Initialize with user data path."""
        self._user_data_path = Path(user_data_path)
        self._history_file = self._user_data_path / self._HISTORY_FILE
        self._history = ModificationHistory(strategy_name="global")
        self._load()

    def _load(self) -> None:
        """Load history from disk."""
        self._history = ModificationHistory.load(self._history_file)
        _log.debug(
            "Loaded modification history: %d records",
            len(self._history.records),
        )

    def _save(self) -> None:
        """Save history to disk."""
        try:
            self._history.save(self._history_file)
        except Exception as e:
            _log.error("Failed to save modification history: %s", e)

    def record_modification(
        self,
        iteration_number: int,
        version_id: Optional[str],
        parameter: str,
        value_before: Any,
        value_after: Any,
        reason: str,
        context: Dict,
    ) -> str:
        """Record a new modification.

        Returns:
            Record ID for later outcome update.
        """
        record = ModificationRecord.create(
            iteration_number=iteration_number,
            version_id=version_id,
            parameter=parameter,
            value_before=value_before,
            value_after=value_after,
            reason=reason,
            context=context,
        )

        self._history.add_record(record)
        self._save()

        _log.debug(
            "Recorded modification %s: %s (%s -> %s)",
            record.record_id,
            parameter,
            value_before,
            value_after,
        )

        return record.record_id

    def update_outcome(
        self,
        record_id: str,
        outcome: str,  # "improved", "degraded", "neutral"
        improvement: float = 0.0,
    ) -> bool:
        """Update the outcome of a modification."""
        success = self._history.update_outcome(record_id, outcome, improvement)
        if success:
            self._save()
            _log.debug(
                "Updated outcome for %s: %s (%.4f)",
                record_id,
                outcome,
                improvement,
            )
        return success

    def get_parameter_history(self, parameter: str) -> List[ModificationRecord]:
        """Get all modifications for a parameter."""
        return self._history.get_parameter_history(parameter)

    def get_parameter_success_rate(self, parameter: str) -> float:
        """Get success rate for a parameter."""
        return self._history.get_success_rate(parameter)

    def get_overall_success_rate(self) -> float:
        """Get overall success rate."""
        return self._history.get_success_rate()

    def get_common_modifications(
        self,
        limit: int = 10,
        min_count: int = 3,
    ) -> List[dict]:
        """Get most commonly modified parameters with stats."""
        from collections import Counter

        # Count modifications per parameter
        param_counts = Counter(r.parameter for r in self._history.records)

        results = []
        for param, count in param_counts.most_common(limit):
            if count >= min_count:
                success_rate = self.get_parameter_success_rate(param)
                records = self.get_parameter_history(param)
                avg_improvement = sum(
                    r.improvement for r in records if r.outcome == "improved"
                ) / max(1, len([r for r in records if r.outcome == "improved"]))

                results.append({
                    "parameter": param,
                    "count": count,
                    "success_rate": success_rate,
                    "avg_improvement": avg_improvement,
                })

        return results

    def get_best_modifications_for_context(
        self,
        context_keys: List[str],
        limit: int = 5,
    ) -> List[dict]:
        """Get modifications that worked well in similar contexts."""
        # Find records with matching context
        matching = []
        for record in self._history.records:
            if record.outcome != "improved":
                continue

            # Check if any context keys match
            if any(key in record.context for key in context_keys):
                matching.append(record)

        # Sort by improvement
        matching.sort(key=lambda r: r.improvement, reverse=True)

        return [
            {
                "parameter": r.parameter,
                "change": f"{r.value_before} -> {r.value_after}",
                "improvement": r.improvement,
                "reason": r.reason,
            }
            for r in matching[:limit]
        ]

    def get_stats(self) -> dict:
        """Get summary statistics."""
        total = len(self._history.records)
        completed = sum(1 for r in self._history.records if r.outcome != "pending")

        return {
            "total_modifications": total,
            "completed_evaluations": completed,
            "improvements": self._history.total_improvements,
            "degradations": self._history.total_degradations,
            "neutral": self._history.total_neutral,
            "success_rate": self.get_overall_success_rate(),
            "unique_parameters": len(set(r.parameter for r in self._history.records)),
        }

    def export_history(self, export_path: Path) -> bool:
        """Export history to file."""
        try:
            self._history.save(export_path)
            return True
        except Exception as e:
            _log.error("Failed to export history: %s", e)
            return False

    def reset_history(self) -> None:
        """Clear all history."""
        self._history = ModificationHistory(strategy_name="global")
        self._save()
        _log.info("Reset modification history")
