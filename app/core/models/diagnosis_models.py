"""
diagnosis_models.py — Data transfer objects for the strategy diagnosis pipeline.

Provides DiagnosisInput (input bundle), DiagnosisBundle (output bundle), and
StructuralDiagnosis (pattern-based root-cause diagnosis).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from app.core.backtests.results_models import BacktestSummary
from app.core.models.improve_models import DiagnosedIssue


@dataclass
class StructuralDiagnosis:
    """Pattern-based root-cause diagnosis of a structural strategy failure.

    Attributes:
        failure_pattern: Short label identifying the failure pattern
            (e.g. "single_regime_dependency", "outlier_trade_dependency").
        evidence: Human-readable description of the evidence that triggered
            this diagnosis.
        root_cause: Explanation of the underlying cause.
        mutation_direction: Suggested direction for parameter mutation to
            address this pattern.
        confidence: Confidence score in [0, 1] for this diagnosis.
        severity: One of "critical", "moderate", or "advisory".
    """

    failure_pattern: str
    evidence: str
    root_cause: str
    mutation_direction: str
    confidence: float
    severity: str


@dataclass
class DiagnosisInput:
    """Input bundle passed to ResultsDiagnosisService.diagnose().

    Attributes:
        in_sample: In-sample BacktestSummary (always required).
        oos_summary: Out-of-sample BacktestSummary; None when not available.
        fold_summaries: Per-fold summaries from walk-forward gate; None when
            not available (e.g. Quick mode or ImprovePage single-run).
        trade_profit_contributions: Per-trade profit contribution values as
            fractions of total profit; None when not available.
        drawdown_periods: List of (start_date, end_date, drawdown_pct) tuples
            identifying significant drawdown periods; None when not available.
        atr_spike_periods: List of (start_date, end_date) tuples identifying
            periods of elevated ATR / volatility; None when not available.
    """

    in_sample: BacktestSummary
    oos_summary: Optional[BacktestSummary] = None
    fold_summaries: Optional[List[BacktestSummary]] = None
    trade_profit_contributions: Optional[List[float]] = None
    drawdown_periods: Optional[List[Tuple[str, str, float]]] = None
    atr_spike_periods: Optional[List[Tuple[str, str]]] = None


@dataclass
class DiagnosisBundle:
    """Output bundle returned by ResultsDiagnosisService.diagnose().

    Attributes:
        issues: List of shallow DiagnosedIssue objects from the eight legacy
            rule-based checks.
        structural: List of StructuralDiagnosis objects from the ten
            pattern-based structural checks.
    """

    issues: List[DiagnosedIssue] = field(default_factory=list)
    structural: List[StructuralDiagnosis] = field(default_factory=list)
