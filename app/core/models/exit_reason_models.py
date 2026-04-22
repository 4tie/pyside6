"""
exit_reason_models.py — Data models for exit reason analysis.

Provides ExitReasonAnalysis for categorizing and analyzing trade exit reasons.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ExitReasonStats:
    """Statistics for a single exit reason.

    Attributes:
        reason: The exit reason string (e.g., "roi", "stoploss", "signal").
        count: Number of trades with this exit reason.
        win_count: Number of winning trades with this exit reason.
        loss_count: Number of losing trades with this exit reason.
        total_profit_pct: Sum of profit percentages for this exit reason.
        avg_profit_pct: Average profit percentage per trade.
        avg_duration_min: Average trade duration in minutes.
        win_rate_pct: Win rate percentage for this exit reason.
        frequency_pct: Percentage of total trades using this exit reason.
    """

    reason: str
    count: int = 0
    win_count: int = 0
    loss_count: int = 0
    total_profit_pct: float = 0.0
    avg_profit_pct: float = 0.0
    avg_duration_min: float = 0.0
    win_rate_pct: float = 0.0
    frequency_pct: float = 0.0


@dataclass
class ExitReasonAnalysis:
    """Comprehensive analysis of exit reasons from a backtest.

    Attributes:
        total_trades: Total number of closed trades analyzed.
        reason_stats: Dict mapping exit reason to ExitReasonStats.
        dominant_reason: The most frequent exit reason.
        problematic_reasons: List of exit reasons flagged as problematic.
        suggestions: List of suggestions based on exit reason patterns.
    """

    total_trades: int = 0
    reason_stats: Dict[str, ExitReasonStats] = field(default_factory=dict)
    dominant_reason: str = ""
    problematic_reasons: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    # Common Freqtrade exit reasons
    KNOWN_REASONS = {
        "roi": "ROI target reached",
        "stoploss": "Stoploss triggered",
        "trailing_stop": "Trailing stop triggered",
        "signal": "Exit signal from strategy",
        "force_exit": "Force exit (manual or shutdown)",
        "emergency_exit": "Emergency exit",
        "roi_timeout": "ROI timeout",
        "stoploss_on_exchange": "Stoploss executed on exchange",
        "stoploss_on_exchange_per_pair": "Per-pair stoploss on exchange",
        "trailing_only_offset_is_reached": "Trailing stop offset reached",
    }

    @property
    def stoploss_rate_pct(self) -> float:
        """Percentage of trades that exited via stoploss."""
        if self.total_trades == 0:
            return 0.0
        stoploss_stats = self.reason_stats.get("stoploss")
        if stoploss_stats is None:
            return 0.0
        return stoploss_stats.frequency_pct

    @property
    def roi_rate_pct(self) -> float:
        """Percentage of trades that exited via ROI."""
        if self.total_trades == 0:
            return 0.0
        roi_stats = self.reason_stats.get("roi")
        if roi_stats is None:
            return 0.0
        return roi_stats.frequency_pct

    @property
    def signal_rate_pct(self) -> float:
        """Percentage of trades that exited via signal."""
        if self.total_trades == 0:
            return 0.0
        signal_stats = self.reason_stats.get("signal")
        if signal_stats is None:
            return 0.0
        return signal_stats.frequency_pct

    @property
    def has_high_stoploss_rate(self) -> bool:
        """True if stoploss rate exceeds 40%."""
        return self.stoploss_rate_pct > 40.0

    @property
    def has_roi_dominance(self) -> bool:
        """True if ROI exits dominate (>50%) but profit factor is low."""
        roi_stats = self.reason_stats.get("roi")
        if roi_stats is None:
            return False
        return roi_stats.frequency_pct > 50.0 and roi_stats.total_profit_pct < 0

    def get_reason_description(self, reason: str) -> str:
        """Get human-readable description for an exit reason."""
        return self.KNOWN_REASONS.get(reason, f"Unknown: {reason}")


@dataclass
class ExitReasonSuggestion:
    """A suggestion based on exit reason analysis.

    Attributes:
        issue: Description of the identified issue.
        affected_reason: The exit reason causing the problem.
        suggestion: Recommended action to address the issue.
        expected_improvement: Expected impact of the suggestion.
        confidence: Confidence score in [0, 1].
    """

    issue: str
    affected_reason: str
    suggestion: str
    expected_improvement: str
    confidence: float = 0.5
