"""
knowledge_models.py — Data models for pattern knowledge base.

Provides PatternKnowledge and PatternKnowledgeBase for tracking successful patterns.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.core.utils.app_logger import get_logger

_log = get_logger("models.knowledge")


@dataclass
class PatternKnowledge:
    """Knowledge about a specific pattern's effectiveness.

    Attributes:
        pattern_id: Unique identifier for the pattern (e.g., "stoploss_too_wide").
        pattern_type: Type of pattern ("issue", "structural", "exit_reason").
        success_count: Number of times this pattern led to improvement.
        failure_count: Number of times this pattern didn't help or made things worse.
        avg_improvement: Average score/profit improvement when successful.
        applicable_contexts: List of market contexts where pattern applies.
        last_seen: ISO timestamp of last occurrence.
        last_success: ISO timestamp of last successful application.
        confidence_score: Computed confidence in [0, 1].
        suggested_params: Parameters typically adjusted for this pattern.
    """

    pattern_id: str
    pattern_type: str  # "issue", "structural", "exit_reason"
    success_count: int = 0
    failure_count: int = 0
    avg_improvement: float = 0.0
    applicable_contexts: List[str] = field(default_factory=list)
    last_seen: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_success: Optional[str] = None
    confidence_score: float = 0.5
    suggested_params: List[str] = field(default_factory=list)

    def update_success(self, improvement: float) -> None:
        """Record a successful application of this pattern."""
        self.success_count += 1
        # Update running average
        total = self.success_count + self.failure_count
        if total > 1:
            self.avg_improvement = (
                (self.avg_improvement * (total - 1) + improvement) / total
            )
        else:
            self.avg_improvement = improvement
        self.last_success = datetime.now(timezone.utc).isoformat()
        self._update_confidence()

    def update_failure(self) -> None:
        """Record a failed application of this pattern."""
        self.failure_count += 1
        self._update_confidence()

    def _update_confidence(self) -> None:
        """Recalculate confidence score based on success/failure ratio."""
        total = self.success_count + self.failure_count
        if total == 0:
            self.confidence_score = 0.5
        else:
            # Wilson score interval for confidence
            z = 1.96  # 95% confidence
            p = self.success_count / total
            numerator = p + z*z/(2*total) - z * ((p*(1-p) + z*z/(4*total))/total)**0.5
            denominator = 1 + z*z/total
            self.confidence_score = numerator / denominator if denominator > 0 else 0.5

    @property
    def total_applications(self) -> int:
        """Total number of times this pattern was applied."""
        return self.success_count + self.failure_count

    @property
    def success_rate(self) -> float:
        """Success rate as a percentage."""
        total = self.total_applications
        if total == 0:
            return 0.0
        return (self.success_count / total) * 100

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> PatternKnowledge:
        """Create from dictionary."""
        return cls(
            pattern_id=data["pattern_id"],
            pattern_type=data["pattern_type"],
            success_count=data.get("success_count", 0),
            failure_count=data.get("failure_count", 0),
            avg_improvement=data.get("avg_improvement", 0.0),
            applicable_contexts=data.get("applicable_contexts", []),
            last_seen=data.get("last_seen", datetime.now(timezone.utc).isoformat()),
            last_success=data.get("last_success"),
            confidence_score=data.get("confidence_score", 0.5),
            suggested_params=data.get("suggested_params", []),
        )


@dataclass
class PatternKnowledgeBase:
    """Complete knowledge base of patterns.

    Attributes:
        patterns: Dict mapping pattern_id to PatternKnowledge.
        created_at: When the knowledge base was first created.
        updated_at: When the knowledge base was last updated.
        total_recorded_outcomes: Total number of outcomes recorded.
    """

    patterns: Dict[str, PatternKnowledge] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_recorded_outcomes: int = 0

    def get_pattern(self, pattern_id: str) -> Optional[PatternKnowledge]:
        """Get knowledge for a specific pattern."""
        return self.patterns.get(pattern_id)

    def record_success(self, pattern_id: str, pattern_type: str, improvement: float) -> None:
        """Record a successful pattern application."""
        if pattern_id not in self.patterns:
            self.patterns[pattern_id] = PatternKnowledge(
                pattern_id=pattern_id,
                pattern_type=pattern_type,
            )

        self.patterns[pattern_id].update_success(improvement)
        self.total_recorded_outcomes += 1
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def record_failure(self, pattern_id: str, pattern_type: str) -> None:
        """Record a failed pattern application."""
        if pattern_id not in self.patterns:
            self.patterns[pattern_id] = PatternKnowledge(
                pattern_id=pattern_id,
                pattern_type=pattern_type,
            )

        self.patterns[pattern_id].update_failure()
        self.total_recorded_outcomes += 1
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def get_top_patterns(
        self,
        pattern_type: Optional[str] = None,
        min_confidence: float = 0.5,
        min_applications: int = 3,
        limit: int = 10,
    ) -> List[PatternKnowledge]:
        """Get top patterns by confidence and success rate.

        Args:
            pattern_type: Filter by pattern type, or None for all.
            min_confidence: Minimum confidence score.
            min_applications: Minimum number of applications.
            limit: Maximum number to return.

        Returns:
            List of PatternKnowledge objects sorted by confidence.
        """
        patterns = list(self.patterns.values())

        # Filter
        patterns = [
            p for p in patterns
            if p.confidence_score >= min_confidence
            and p.total_applications >= min_applications
            and (pattern_type is None or p.pattern_type == pattern_type)
        ]

        # Sort by confidence score
        patterns.sort(key=lambda p: p.confidence_score, reverse=True)

        return patterns[:limit]

    def get_recommended_for_context(
        self,
        context: str,
        limit: int = 5,
    ) -> List[PatternKnowledge]:
        """Get patterns recommended for a specific market context.

        Args:
            context: Market context (e.g., "high_volatility", "trending").
            limit: Maximum number to return.

        Returns:
            List of PatternKnowledge objects applicable to the context.
        """
        patterns = [
            p for p in self.patterns.values()
            if context in p.applicable_contexts and p.confidence_score > 0.5
        ]

        patterns.sort(key=lambda p: p.confidence_score, reverse=True)
        return patterns[:limit]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "patterns": {
                k: v.to_dict() for k, v in self.patterns.items()
            },
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "total_recorded_outcomes": self.total_recorded_outcomes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PatternKnowledgeBase:
        """Create from dictionary."""
        return cls(
            patterns={
                k: PatternKnowledge.from_dict(v)
                for k, v in data.get("patterns", {}).items()
            },
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
            total_recorded_outcomes=data.get("total_recorded_outcomes", 0),
        )

    def save(self, file_path: Path) -> None:
        """Save knowledge base to disk."""
        file_path.write_text(
            json.dumps(self.to_dict(), indent=2),
            encoding="utf-8",
        )
        _log.debug("Saved knowledge base to %s", file_path)

    @classmethod
    def load(cls, file_path: Path) -> PatternKnowledgeBase:
        """Load knowledge base from disk."""
        if not file_path.exists():
            _log.debug("Knowledge base not found at %s, creating new", file_path)
            return cls()

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            return cls.from_dict(data)
        except Exception as e:
            _log.error("Failed to load knowledge base: %s", e)
            return cls()
