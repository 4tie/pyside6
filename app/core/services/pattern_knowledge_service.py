"""
pattern_knowledge_service.py — Service for managing pattern knowledge base.

Tracks which patterns work and provides recommendations based on historical success.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from app.core.models.knowledge_models import PatternKnowledge, PatternKnowledgeBase
from app.core.utils.app_logger import get_logger

_log = get_logger("services.pattern_knowledge")


class PatternKnowledgeService:
    """Service for tracking and querying pattern effectiveness.

    Persists knowledge to user_data/pattern_knowledge.json
    """

    _KNOWLEDGE_FILE = "pattern_knowledge.json"
    _MAX_AGE_DAYS = 90  # Prune patterns older than this with low confidence

    def __init__(self, user_data_path: str) -> None:
        """Initialize with user data path.

        Args:
            user_data_path: Path to user_data directory.
        """
        self._user_data_path = Path(user_data_path)
        self._knowledge_file = self._user_data_path / self._KNOWLEDGE_FILE
        self._knowledge = PatternKnowledgeBase()
        self._load()

    def _load(self) -> None:
        """Load knowledge base from disk."""
        self._knowledge = PatternKnowledgeBase.load(self._knowledge_file)
        _log.debug(
            "Loaded knowledge base with %d patterns",
            len(self._knowledge.patterns),
        )

    def _save(self) -> None:
        """Save knowledge base to disk."""
        try:
            self._knowledge.save(self._knowledge_file)
        except Exception as e:
            _log.error("Failed to save knowledge base: %s", e)

    def record_pattern_result(
        self,
        pattern_id: str,
        pattern_type: str,  # "issue", "structural", "exit_reason"
        success: bool,
        improvement: float = 0.0,
    ) -> None:
        """Record the outcome of applying a pattern.

        Args:
            pattern_id: The pattern identifier.
            pattern_type: Type of pattern.
            success: Whether the modification improved results.
            improvement: Amount of improvement (score/profit increase).
        """
        if success:
            self._knowledge.record_success(pattern_id, pattern_type, improvement)
            _log.debug(
                "Recorded success for %s (%s), improvement=%.4f",
                pattern_id,
                pattern_type,
                improvement,
            )
        else:
            self._knowledge.record_failure(pattern_id, pattern_type)
            _log.debug(
                "Recorded failure for %s (%s)",
                pattern_id,
                pattern_type,
            )

        self._save()

    def get_pattern_confidence(self, pattern_id: str) -> float:
        """Get the confidence score for a pattern.

        Args:
            pattern_id: The pattern identifier.

        Returns:
            Confidence score in [0, 1], or 0.5 if pattern unknown.
        """
        pattern = self._knowledge.get_pattern(pattern_id)
        if pattern is None:
            return 0.5  # Neutral for unknown patterns
        return pattern.confidence_score

    def get_recommended_patterns(
        self,
        available_patterns: List[str],
        min_confidence: float = 0.5,
    ) -> List[tuple]:
        """Get recommended patterns from available options.

        Args:
            available_patterns: List of pattern IDs available to try.
            min_confidence: Minimum confidence threshold.

        Returns:
            List of (pattern_id, confidence, success_rate) tuples, sorted by confidence.
        """
        recommendations = []

        for pattern_id in available_patterns:
            pattern = self._knowledge.get_pattern(pattern_id)
            if pattern and pattern.confidence_score >= min_confidence:
                recommendations.append((
                    pattern_id,
                    pattern.confidence_score,
                    pattern.success_rate,
                ))

        # Sort by confidence score
        recommendations.sort(key=lambda x: x[1], reverse=True)
        return recommendations

    def get_top_patterns(
        self,
        pattern_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[PatternKnowledge]:
        """Get top performing patterns.

        Args:
            pattern_type: Filter by type, or None for all.
            limit: Maximum number to return.

        Returns:
            List of PatternKnowledge objects.
        """
        return self._knowledge.get_top_patterns(
            pattern_type=pattern_type,
            limit=limit,
        )

    def get_pattern_stats(self, pattern_id: str) -> Optional[dict]:
        """Get detailed stats for a pattern.

        Args:
            pattern_id: The pattern identifier.

        Returns:
            Dict with stats, or None if pattern not found.
        """
        pattern = self._knowledge.get_pattern(pattern_id)
        if not pattern:
            return None

        return {
            "pattern_id": pattern.pattern_id,
            "pattern_type": pattern.pattern_type,
            "success_count": pattern.success_count,
            "failure_count": pattern.failure_count,
            "success_rate": pattern.success_rate,
            "avg_improvement": pattern.avg_improvement,
            "confidence": pattern.confidence_score,
            "total_applications": pattern.total_applications,
            "last_seen": pattern.last_seen,
            "last_success": pattern.last_success,
        }

    def get_all_stats(self) -> dict:
        """Get summary stats for the entire knowledge base.

        Returns:
            Dict with overall statistics.
        """
        patterns = list(self._knowledge.patterns.values())

        if not patterns:
            return {
                "total_patterns": 0,
                "total_outcomes": 0,
                "avg_confidence": 0.0,
                "top_patterns": [],
            }

        # Calculate aggregate stats
        avg_confidence = sum(p.confidence_score for p in patterns) / len(patterns)

        # Get top 5 patterns
        top_patterns = sorted(
            patterns,
            key=lambda p: p.confidence_score,
            reverse=True,
        )[:5]

        return {
            "total_patterns": len(patterns),
            "total_outcomes": self._knowledge.total_recorded_outcomes,
            "avg_confidence": avg_confidence,
            "created_at": self._knowledge.created_at,
            "updated_at": self._knowledge.updated_at,
            "top_patterns": [
                {
                    "pattern_id": p.pattern_id,
                    "success_rate": p.success_rate,
                    "confidence": p.confidence_score,
                    "applications": p.total_applications,
                }
                for p in top_patterns
            ],
        }

    def prune_old_patterns(self, min_applications: int = 3) -> int:
        """Remove old patterns with low confidence.

        Args:
            min_applications: Keep patterns with at least this many applications.

        Returns:
            Number of patterns removed.
        """
        from datetime import datetime, timezone, timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(days=self._MAX_AGE_DAYS)
        cutoff_str = cutoff.isoformat()

        to_remove = []
        for pattern_id, pattern in self._knowledge.patterns.items():
            # Remove if:
            # 1. Older than cutoff
            # 2. Low confidence
            # 3. Few applications
            if (
                pattern.last_seen < cutoff_str
                and pattern.confidence_score < 0.5
                and pattern.total_applications < min_applications
            ):
                to_remove.append(pattern_id)

        for pattern_id in to_remove:
            del self._knowledge.patterns[pattern_id]

        if to_remove:
            _log.info("Pruned %d old patterns from knowledge base", len(to_remove))
            self._save()

        return len(to_remove)

    def export_knowledge(self, export_path: Path) -> bool:
        """Export knowledge base to a file.

        Args:
            export_path: Path to export to.

        Returns:
            True if successful, False otherwise.
        """
        try:
            self._knowledge.save(export_path)
            return True
        except Exception as e:
            _log.error("Failed to export knowledge: %s", e)
            return False

    def import_knowledge(self, import_path: Path, merge: bool = True) -> bool:
        """Import knowledge from a file.

        Args:
            import_path: Path to import from.
            merge: If True, merge with existing; if False, replace.

        Returns:
            True if successful, False otherwise.
        """
        try:
            imported = PatternKnowledgeBase.load(import_path)

            if merge:
                # Merge patterns, keeping highest confidence for duplicates
                for pattern_id, pattern in imported.patterns.items():
                    existing = self._knowledge.get_pattern(pattern_id)
                    if existing is None:
                        self._knowledge.patterns[pattern_id] = pattern
                    elif pattern.confidence_score > existing.confidence_score:
                        self._knowledge.patterns[pattern_id] = pattern
            else:
                # Replace entirely
                self._knowledge = imported

            self._save()
            _log.info(
                "Imported knowledge base with %d patterns (merge=%s)",
                len(imported.patterns),
                merge,
            )
            return True

        except Exception as e:
            _log.error("Failed to import knowledge: %s", e)
            return False

    def reset_knowledge(self) -> None:
        """Clear all pattern knowledge."""
        self._knowledge = PatternKnowledgeBase()
        self._save()
        _log.info("Reset pattern knowledge base")

    # -------------------------------------------------------------------------
    # Simplified 4-Layer Architecture Methods
    # -------------------------------------------------------------------------

    def update(self, pattern_id: str, action_id: str, improved: bool) -> None:
        """Record action outcome for 4-layer architecture.

        Incremental update only, no full recalculation.

        Args:
            pattern_id: The pattern identifier.
            action_id: The action identifier.
            improved: Whether the action improved results.
        """
        # Use action_id as key for simplified tracking
        if not hasattr(self._knowledge, '_action_data'):
            self._knowledge._action_data = {}

        if action_id not in self._knowledge._action_data:
            self._knowledge._action_data[action_id] = {"success": 0, "failure": 0}

        if improved:
            self._knowledge._action_data[action_id]["success"] += 1
        else:
            self._knowledge._action_data[action_id]["failure"] += 1

        # Also record in legacy format for compatibility
        self.record_pattern_result(pattern_id, "action", improved)

    def get_success_rate(self, action_id: str) -> float:
        """Get success rate for an action.

        Args:
            action_id: The action identifier.

        Returns:
            Success rate in [0, 1], or 0.5 if unknown.
        """
        if not hasattr(self._knowledge, '_action_data'):
            return 0.5

        data = self._knowledge._action_data.get(action_id)
        if not data:
            return 0.5

        total = data["success"] + data["failure"]
        if total == 0:
            return 0.5

        return data["success"] / total

    def get_data(self) -> dict:
        """Get knowledge data for DecisionEngine.

        Returns:
            Dict mapping action_id to success_rate.
        """
        if not hasattr(self._knowledge, '_action_data'):
            return {}

        return {
            action_id: self.get_success_rate(action_id)
            for action_id in self._knowledge._action_data.keys()
        }
