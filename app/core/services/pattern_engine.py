"""
pattern_engine.py — Pure function pattern detection engine.

Part of the 4-layer diagnostic architecture.
Input → Output only. No file reads, no state changes, no complex logging.
"""
from __future__ import annotations

from typing import List, Optional

from app.core.models.backtest_models import BacktestSummary
from app.core.models.pattern_models import (
    FailurePattern,
    PatternCondition,
    PatternDiagnosis,
)


class PatternEngine:
    """Pure function pattern detection engine.
    
    Detects failure patterns from backtest results using JSON-defined conditions.
    """

    @staticmethod
    def detect(summary: BacktestSummary, patterns: List[FailurePattern]) -> List[PatternDiagnosis]:
        """Detect patterns from backtest summary.
        
        Pure function: input → output only.
        No file reads, no state changes, no complex logging.
        
        Args:
            summary: Backtest summary with metrics
            patterns: List of failure patterns to check against
            
        Returns:
            List of PatternDiagnosis (limited to top 5 by confidence)
        """
        diagnoses = []
        
        for pattern in patterns:
            if PatternEngine._matches(pattern, summary):
                diagnoses.append(PatternDiagnosis(
                    pattern_id=pattern.id,
                    severity=pattern.severity,
                    confidence=PatternEngine._calculate_confidence(pattern, summary),
                    root_cause=pattern.description
                ))
        
        # Limit to top 5 by confidence to avoid pattern explosion
        return sorted(diagnoses, key=lambda d: d.confidence, reverse=True)[:5]

    @staticmethod
    def _matches(pattern: FailurePattern, summary: BacktestSummary) -> bool:
        """Check if all conditions of a pattern match the summary."""
        for cond in pattern.conditions:
            if not PatternEngine._check_condition(cond, summary):
                return False
        return True

    @staticmethod
    def _calculate_confidence(pattern: FailurePattern, summary: BacktestSummary) -> float:
        """Calculate confidence based on matched conditions.
        
        Confidence = ratio of matched conditions to total conditions.
        """
        if not pattern.conditions:
            return 0.5
        
        matched = 0
        for cond in pattern.conditions:
            if PatternEngine._check_condition(cond, summary):
                matched += 1
        
        return matched / len(pattern.conditions)

    @staticmethod
    def _check_condition(cond: PatternCondition, summary: BacktestSummary) -> bool:
        """Check if a single condition matches the summary metrics.
        
        Raises:
            Exception: If the metric is not found in summary (prevents silent failures)
        """
        if not hasattr(summary, cond.metric):
            raise Exception(f"Unknown metric: {cond.metric}")
        
        value = getattr(summary, cond.metric)
        
        if cond.op == ">":
            return value > cond.value
        elif cond.op == "<":
            return value < cond.value
        elif cond.op == "==":
            return value == cond.value
        elif cond.op == ">=":
            return value >= cond.value
        elif cond.op == "<=":
            return value <= cond.value
        
        return False
