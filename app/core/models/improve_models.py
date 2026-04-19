"""
improve_models.py — Data transfer objects for the strategy improvement pipeline.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.core.utils.app_logger import get_logger

_log = get_logger("models.improve")


@dataclass
class DiagnosedIssue:
    """A single issue identified during strategy diagnosis.

    Attributes:
        issue_id: Unique identifier for the issue type.
        description: Human-readable explanation of the issue.
    """

    issue_id: str
    description: str


@dataclass
class ParameterSuggestion:
    """A suggested parameter change to address a diagnosed issue.

    Attributes:
        parameter: Name of the strategy parameter to adjust.
        proposed_value: The recommended new value for the parameter.
        reason: Explanation of why this change is suggested.
        expected_effect: Description of the anticipated impact on strategy performance.
        is_advisory: If True, the suggestion is informational only and should not be
            applied automatically. Defaults to False.
    """

    parameter: str
    proposed_value: Any
    reason: str
    expected_effect: str
    is_advisory: bool = False


# ---------------------------------------------------------------------------
# Session tracking dataclasses (imported lazily to avoid circular imports)
# ---------------------------------------------------------------------------

def _get_backtest_summary_type():
    """Lazy import to avoid circular dependency at module load time."""
    from app.core.backtests.results_models import BacktestSummary  # noqa: PLC0415
    return BacktestSummary


@dataclass
class SessionBaseline:
    """In-memory accepted-session baseline for ImprovePage.

    Captured at the moment the user accepts a candidate. Never re-read from
    disk after initial load.

    Attributes:
        params: Strategy parameter dict at the time of acceptance.
        summary: BacktestSummary from the accepted run.
    """

    params: dict
    summary: Any  # BacktestSummary — typed as Any to avoid circular import


@dataclass
class SessionRound:
    """One entry in the ImprovePage session history stack.

    Attributes:
        round_number: 1-based round counter within the session.
        params_before: Strategy parameters before this round's acceptance.
        params_after: Strategy parameters after this round's acceptance.
        summary: BacktestSummary from the accepted candidate run.
        timestamp: UTC datetime when the round was accepted.
    """

    round_number: int
    params_before: dict
    params_after: dict
    summary: Any  # BacktestSummary — typed as Any to avoid circular import
    timestamp: datetime
