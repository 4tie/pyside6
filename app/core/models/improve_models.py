"""
improve_models.py — Data transfer objects for the strategy improvement pipeline.
"""
from dataclasses import dataclass
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
