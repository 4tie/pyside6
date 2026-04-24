"""
pattern_models.py — Data models for failure pattern detection system.

Provides PatternCondition, PatternAction, FailurePattern for the 4-layer diagnostic architecture.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.models.backtest_models import BacktestSummary  # noqa: PLC0415


@dataclass
class LoopState4L:
    """State for 4-layer architecture loop iteration.
    
    Tracks parameters, last summary, candidate queue, fallback state,
    tried actions, and iteration counter.
    """
    params: dict
    last_summary: Optional[BacktestSummary] = None
    candidate_actions: List['Action'] = field(default_factory=list)
    fallback_index: int = 0
    tried_actions: set = field(default_factory=set)
    iteration: int = 0


@dataclass
class PatternCondition:
    """A condition for matching a pattern against metrics.
    
    Attributes:
        metric: The metric name to check (e.g., "max_drawdown", "sharpe_ratio")
        op: The operator to use (">", "<", "==", ">=", "<=")
        value: The threshold value to compare against
    """
    metric: str
    op: str  # ">", "<", "==", ">=", "<="
    value: float


@dataclass
class PatternAction:
    """An action to take when a pattern is matched.
    
    Attributes:
        id: Unique action identifier (e.g., "tighten_stoploss")
        parameter: The parameter to modify (e.g., "stoploss")
        type: The adjustment type ("scale", "add", "set", "toggle")
        factor: Multiplier for "scale" type (e.g., 0.8 for 20% reduction)
        delta: Additive change for "add" type
        value: Fixed value for "set" type
        bounds: Min/max bounds for the parameter (tuple of two values)
    """
    id: str
    parameter: str
    type: str  # "scale", "add", "set", "toggle"
    factor: Optional[float] = None
    delta: Optional[float] = None
    value: Optional[Any] = None
    bounds: Optional[tuple] = None


@dataclass
class FailurePattern:
    """A failure pattern with conditions and suggested actions.
    
    Attributes:
        id: Unique pattern identifier (e.g., "PR_001")
        category: Pattern category ("risk", "frequency", "entries", "exits", "pairs", "structure", "market_adaptation")
        conditions: List of conditions to match
        actions: List of suggested actions when pattern matches
        description: Human-readable description of the pattern
        severity: Severity score 0.0 to 1.0
    """
    id: str
    category: str
    conditions: List[PatternCondition]
    actions: List[PatternAction]
    description: str
    severity: float  # 0.0 to 1.0


@dataclass
class PatternDiagnosis:
    """Result of pattern detection for a single pattern.
    
    Attributes:
        pattern_id: The matched pattern ID
        severity: Severity score from the pattern
        confidence: Confidence score 0.0 to 1.0 (ratio of matched conditions)
        root_cause: Human-readable description of the issue
    """
    pattern_id: str
    severity: float
    confidence: float
    root_cause: str


@dataclass
class Action:
    """A concrete action to apply to strategy parameters.
    
    Attributes:
        id: Action identifier (e.g., "tighten_stoploss")
        pattern_id: Source pattern ID that suggested this action
        parameter: Parameter to modify
        type: Adjustment type ("scale", "add", "set", "toggle")
        factor: For "scale" type
        delta: For "add" type
        value: For "set" type
        bounds: Min/max bounds for the parameter
    """
    id: str
    pattern_id: str
    parameter: str
    type: str
    factor: Optional[float] = None
    delta: Optional[float] = None
    value: Optional[Any] = None
    bounds: Optional[tuple] = None
    
    @classmethod
    def from_def(cls, action_def: PatternAction, pattern_id: str) -> Action:
        """Create Action from PatternAction definition."""
        return cls(
            id=action_def.id,
            pattern_id=pattern_id,
            parameter=action_def.parameter,
            type=action_def.type,
            factor=action_def.factor,
            delta=action_def.delta,
            value=action_def.value,
            bounds=action_def.bounds
        )
