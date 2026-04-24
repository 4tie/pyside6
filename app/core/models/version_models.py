"""
version_models.py — Data models for strategy version management.

Provides StrategyVersion for tracking and managing strategy versions.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Any

from app.core.parsing.json_parser import parse_json_file, write_json_file_atomic
from app.core.utils.app_logger import get_logger

_log = get_logger("models.version")


@dataclass
class StrategyVersion:
    """A single version snapshot of a strategy.

    Attributes:
        version_id: Unique identifier (timestamp-based: v20260422_060000).
        parent_version_id: ID of the parent version, None for initial version.
        strategy_name: Name of the strategy.
        params: Strategy parameters at this version.
        summary: Key metrics from the backtest (stored as dict for serialization).
        iteration_number: The iteration number in the optimization loop.
        changes_summary: Human-readable description of changes.
        created_at: UTC timestamp when version was created.
        is_best: Whether this is the best version so far.
        score: RobustScore total for comparison.
        exit_reason_analysis: Key exit reason stats (stored as dict).
    """

    version_id: str
    parent_version_id: Optional[str]
    strategy_name: str
    params: dict
    summary: dict
    iteration_number: int
    changes_summary: List[str]
    created_at: str
    is_best: bool = False
    score: float = 0.0
    exit_reason_analysis: Optional[dict] = None

    @staticmethod
    def generate_id() -> str:
        """Generate a unique version ID based on current timestamp."""
        return datetime.now(timezone.utc).strftime("v%Y%m%d_%H%M%S_%f")[:-3]

    @classmethod
    def from_iteration(
        cls,
        strategy_name: str,
        params: dict,
        summary: Any,  # BacktestSummary
        iteration_number: int,
        changes_summary: List[str],
        parent_version_id: Optional[str] = None,
        score: float = 0.0,
        exit_reason_analysis: Optional[dict] = None,
    ) -> StrategyVersion:
        """Create a StrategyVersion from a LoopIteration.

        Args:
            strategy_name: Name of the strategy.
            params: Strategy parameters.
            summary: BacktestSummary from the iteration.
            iteration_number: Iteration number.
            changes_summary: List of change descriptions.
            parent_version_id: ID of parent version, if any.
            score: RobustScore total.
            exit_reason_analysis: Optional exit reason analysis dict.

        Returns:
            StrategyVersion instance.
        """
        # Convert summary to dict if it's a BacktestSummary
        if hasattr(summary, 'strategy'):
            summary_dict = {
                "strategy": summary.strategy,
                "timeframe": summary.timeframe,
                "total_trades": summary.total_trades,
                "wins": summary.wins,
                "losses": summary.losses,
                "draws": summary.draws,
                "win_rate": summary.win_rate,
                "avg_profit": summary.avg_profit,
                "total_profit": summary.total_profit,
                "total_profit_abs": summary.total_profit_abs,
                "sharpe_ratio": summary.sharpe_ratio,
                "sortino_ratio": summary.sortino_ratio,
                "calmar_ratio": summary.calmar_ratio,
                "max_drawdown": summary.max_drawdown,
                "max_drawdown_abs": summary.max_drawdown_abs,
                "trade_duration_avg": summary.trade_duration_avg,
                "expectancy": summary.expectancy,
                "profit_factor": summary.profit_factor,
            }
        else:
            summary_dict = summary if isinstance(summary, dict) else {}

        return cls(
            version_id=cls.generate_id(),
            parent_version_id=parent_version_id,
            strategy_name=strategy_name,
            params=params,
            summary=summary_dict,
            iteration_number=iteration_number,
            changes_summary=changes_summary,
            created_at=datetime.now(timezone.utc).isoformat(),
            is_best=False,
            score=score,
            exit_reason_analysis=exit_reason_analysis,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> StrategyVersion:
        """Create from dictionary (JSON deserialization)."""
        return cls(
            version_id=data["version_id"],
            parent_version_id=data.get("parent_version_id"),
            strategy_name=data["strategy_name"],
            params=data["params"],
            summary=data["summary"],
            iteration_number=data["iteration_number"],
            changes_summary=data.get("changes_summary", []),
            created_at=data["created_at"],
            is_best=data.get("is_best", False),
            score=data.get("score", 0.0),
            exit_reason_analysis=data.get("exit_reason_analysis"),
        )

    def save(self, versions_dir: Path) -> Path:
        """Save this version to disk.

        Args:
            versions_dir: Directory to save versions (e.g., user_data/strategy_versions/).

        Returns:
            Path to saved file.
        """
        strategy_dir = versions_dir / self.strategy_name
        strategy_dir.mkdir(parents=True, exist_ok=True)

        file_path = strategy_dir / f"{self.version_id}.json"

        try:
            write_json_file_atomic(file_path, self.to_dict())
            _log.debug("Saved version %s to %s", self.version_id, file_path)
            return file_path
        except Exception as e:
            _log.error("Failed to save version %s: %s", self.version_id, e)
            raise

    @classmethod
    def load(cls, file_path: Path) -> StrategyVersion:
        """Load a version from disk.

        Args:
            file_path: Path to the version JSON file.

        Returns:
            StrategyVersion instance.
        """
        try:
            data = parse_json_file(file_path)
            return cls.from_dict(data)
        except Exception as e:
            _log.error("Failed to load version from %s: %s", file_path, e)
            raise

    @property
    def display_name(self) -> str:
        """Human-readable display name for this version."""
        # Parse vYYYYMMDD_HHMMSS_mmm format
        try:
            parts = self.version_id.split("_")
            date_part = parts[0][1:]  # Remove 'v' prefix
            time_part = parts[1]
            formatted_date = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:]}"
            formatted_time = f"{time_part[:2]}:{time_part[2:4]}:{time_part[4:]}"
            return f"Iter #{self.iteration_number} - {formatted_date} {formatted_time}"
        except (IndexError, ValueError):
            return f"Iter #{self.iteration_number} - {self.version_id}"

    @property
    def short_description(self) -> str:
        """Short description of changes in this version."""
        if self.changes_summary:
            return " | ".join(self.changes_summary[:3])  # Show first 3 changes
        return "Initial version" if self.iteration_number == 1 else "No changes recorded"


@dataclass
class VersionLineage:
    """Complete lineage of strategy versions.

    Attributes:
        strategy_name: Name of the strategy.
        versions: List of all versions in chronological order.
        best_version_id: ID of the best performing version.
        root_version_id: ID of the initial version.
    """

    strategy_name: str
    versions: List[StrategyVersion] = field(default_factory=list)
    best_version_id: Optional[str] = None
    root_version_id: Optional[str] = None

    def add_version(self, version: StrategyVersion) -> None:
        """Add a new version and update lineage."""
        self.versions.append(version)

        # Set root version if this is the first
        if len(self.versions) == 1:
            self.root_version_id = version.version_id
            version.is_best = True
            self.best_version_id = version.version_id

    def update_best_version(self, version_id: str) -> None:
        """Mark a version as the best and unmark others."""
        for v in self.versions:
            v.is_best = (v.version_id == version_id)
        self.best_version_id = version_id

    def get_version(self, version_id: str) -> Optional[StrategyVersion]:
        """Get a specific version by ID."""
        for v in self.versions:
            if v.version_id == version_id:
                return v
        return None

    def get_parent_version(self, version: StrategyVersion) -> Optional[StrategyVersion]:
        """Get the parent version of a given version."""
        if version.parent_version_id:
            return self.get_version(version.parent_version_id)
        return None

    def get_version_chain(self, version_id: str) -> List[StrategyVersion]:
        """Get the chain of versions from root to the given version."""
        chain = []
        current = self.get_version(version_id)

        while current:
            chain.append(current)
            current = self.get_parent_version(current)

        return list(reversed(chain))  # From root to target

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "strategy_name": self.strategy_name,
            "versions": [v.to_dict() for v in self.versions],
            "best_version_id": self.best_version_id,
            "root_version_id": self.root_version_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> VersionLineage:
        """Create from dictionary (JSON deserialization)."""
        return cls(
            strategy_name=data["strategy_name"],
            versions=[StrategyVersion.from_dict(v) for v in data.get("versions", [])],
            best_version_id=data.get("best_version_id"),
            root_version_id=data.get("root_version_id"),
        )
