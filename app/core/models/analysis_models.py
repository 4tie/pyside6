"""analysis_models.py — Data transfer objects for the pair analysis pipeline.

Provides DiagnosisSuggestion, the output DTO of DiagnosisService.
Distinct from diagnosis_models.py which serves the Strategy Lab loop.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.utils.app_logger import get_logger

_log = get_logger("models.analysis")


@dataclass
class DiagnosisSuggestion:
    """One actionable suggestion produced by DiagnosisService.

    Attributes:
        rule_id: Machine-readable identifier for the rule that fired
            (e.g. "entry_too_aggressive", "stoploss_too_loose").
        message: Human-readable explanation of the issue and its implication.
        severity: Urgency level — "critical" for issues that likely harm
            performance, "warning" for issues that warrant attention.
    """

    rule_id: str
    message: str
    severity: str
