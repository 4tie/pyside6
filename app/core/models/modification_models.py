"""
modification_models.py — Data models for modification history tracking.

Provides ModificationRecord for detailed tracking of parameter changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from app.core.parsing.json_parser import parse_json_file, write_json_file_atomic
from app.core.utils.app_logger import get_logger

_log = get_logger("models.modification")


@dataclass
class ModificationRecord:
    """Record of a single parameter modification.

    Attributes:
        record_id: Unique identifier for this record.
        iteration_number: The iteration where this modification was applied.
        version_id: Associated version ID, if any.
        parameter: The parameter that was modified.
        value_before: Value before modification.
        value_after: Value after modification.
        reason: Why this modification was made.
        outcome: Result ("improved", "degraded", "neutral").
        improvement: Quantified improvement amount.
        context: Dict of diagnostic signals at time of modification.
        created_at: ISO timestamp.
    """

    record_id: str
    iteration_number: int
    version_id: Optional[str]
    parameter: str
    value_before: Any
    value_after: Any
    reason: str
    outcome: str
    improvement: float
    context: dict
    created_at: str

    @staticmethod
    def generate_id() -> str:
        """Generate unique record ID."""
        return datetime.now(timezone.utc).strftime("mod_%Y%m%d_%H%M%S_%f")[:-3]

    @classmethod
    def create(
        cls,
        iteration_number: int,
        version_id: Optional[str],
        parameter: str,
        value_before: Any,
        value_after: Any,
        reason: str,
        context: dict,
    ) -> ModificationRecord:
        """Create a new modification record."""
        return cls(
            record_id=cls.generate_id(),
            iteration_number=iteration_number,
            version_id=version_id,
            parameter=parameter,
            value_before=value_before,
            value_after=value_after,
            reason=reason,
            outcome="pending",  # Will be updated after evaluation
            improvement=0.0,
            context=context.copy(),
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def update_outcome(self, outcome: str, improvement: float) -> None:
        """Update the outcome after evaluation."""
        self.outcome = outcome
        self.improvement = improvement

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ModificationRecord:
        """Create from dictionary."""
        return cls(
            record_id=data["record_id"],
            iteration_number=data["iteration_number"],
            version_id=data.get("version_id"),
            parameter=data["parameter"],
            value_before=data["value_before"],
            value_after=data["value_after"],
            reason=data["reason"],
            outcome=data["outcome"],
            improvement=data.get("improvement", 0.0),
            context=data.get("context", {}),
            created_at=data["created_at"],
        )


@dataclass
class ModificationHistory:
    """Complete modification history for a strategy.

    Attributes:
        strategy_name: Name of the strategy.
        records: List of all modification records.
        total_improvements: Count of improvements.
        total_degradations: Count of degradations.
        total_neutral: Count of neutral outcomes.
    """

    strategy_name: str
    records: List[ModificationRecord] = field(default_factory=list)
    total_improvements: int = 0
    total_degradations: int = 0
    total_neutral: int = 0

    def add_record(self, record: ModificationRecord) -> None:
        """Add a new record."""
        self.records.append(record)

    def update_outcome(self, record_id: str, outcome: str, improvement: float) -> bool:
        """Update outcome for a record."""
        for record in self.records:
            if record.record_id == record_id:
                old_outcome = record.outcome
                record.update_outcome(outcome, improvement)

                # Update counters
                if old_outcome == "improved":
                    self.total_improvements -= 1
                elif old_outcome == "degraded":
                    self.total_degradations -= 1
                elif old_outcome == "neutral":
                    self.total_neutral -= 1

                if outcome == "improved":
                    self.total_improvements += 1
                elif outcome == "degraded":
                    self.total_degradations += 1
                elif outcome == "neutral":
                    self.total_neutral += 1

                return True
        return False

    def get_parameter_history(self, parameter: str) -> List[ModificationRecord]:
        """Get all modifications for a specific parameter."""
        return [r for r in self.records if r.parameter == parameter]

    def get_success_rate(self, parameter: Optional[str] = None) -> float:
        """Get success rate for a parameter or overall."""
        records = (
            self.get_parameter_history(parameter)
            if parameter
            else self.records
        )

        completed = [r for r in records if r.outcome != "pending"]
        if not completed:
            return 0.0

        improvements = sum(1 for r in completed if r.outcome == "improved")
        return (improvements / len(completed)) * 100

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "strategy_name": self.strategy_name,
            "records": [r.to_dict() for r in self.records],
            "total_improvements": self.total_improvements,
            "total_degradations": self.total_degradations,
            "total_neutral": self.total_neutral,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ModificationHistory:
        """Create from dictionary."""
        return cls(
            strategy_name=data["strategy_name"],
            records=[ModificationRecord.from_dict(r) for r in data.get("records", [])],
            total_improvements=data.get("total_improvements", 0),
            total_degradations=data.get("total_degradations", 0),
            total_neutral=data.get("total_neutral", 0),
        )

    def save(self, file_path: Path) -> None:
        """Save to disk."""
        write_json_file_atomic(file_path, self.to_dict())

    @classmethod
    def load(cls, file_path: Path) -> ModificationHistory:
        """Load from disk."""
        if not file_path.exists():
            return cls(strategy_name="")

        try:
            data = parse_json_file(file_path)
            return cls.from_dict(data)
        except Exception as e:
            _log.error("Failed to load modification history: %s", e)
            return cls(strategy_name="")
