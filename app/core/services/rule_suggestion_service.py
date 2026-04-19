"""
rule_suggestion_service.py — Stateless service that maps diagnosed issues to parameter suggestions.
"""
from typing import List, Optional

from app.core.models.diagnosis_models import StructuralDiagnosis
from app.core.models.improve_models import DiagnosedIssue, ParameterSuggestion
from app.core.utils.app_logger import get_logger

_log = get_logger("services.rule_suggestion")


class RuleSuggestionService:
    """Maps a list of diagnosed issues to concrete parameter change suggestions.

    All methods are stateless and operate purely on the inputs provided.
    """

    @staticmethod
    def suggest(
        issues: List[DiagnosedIssue],
        params: dict,
        structural: Optional[List[StructuralDiagnosis]] = None,
    ) -> List[ParameterSuggestion]:
        """Generate parameter suggestions for each diagnosed issue.

        Args:
            issues: List of issues identified by ResultsDiagnosisService.
            params: Current strategy parameters dict with keys: buy_params, sell_params,
                minimal_roi, stoploss, max_open_trades.
            structural: Optional list of structural diagnosis patterns to handle.

        Returns:
            List of ParameterSuggestion objects, one per handled issue type.
        """
        suggestions: List[ParameterSuggestion] = []

        # Process legacy issues first
        for issue in issues:
            suggestion = RuleSuggestionService._handle_issue(issue, params)
            if suggestion is not None:
                suggestions.append(suggestion)

        # Process structural patterns if provided
        if structural:
            for structural_diag in structural:
                suggestion = RuleSuggestionService._handle_structural(structural_diag, params)
                if suggestion is not None:
                    suggestions.append(suggestion)

        return suggestions

    @staticmethod
    def _handle_structural(
        structural_diag: StructuralDiagnosis, params: dict
    ) -> "ParameterSuggestion | None":
        """Dispatch a single structural diagnosis to its handler.

        Args:
            structural_diag: The structural diagnosis to handle.
            params: Current strategy parameters dict.

        Returns:
            A ParameterSuggestion, or None if the pattern type is unrecognised.
        """
        handlers = {
            "entries_too_loose_in_chop": RuleSuggestionService._suggest_entries_too_loose_in_chop,
            "single_regime_dependency": RuleSuggestionService._suggest_single_regime_dependency,
            "outlier_trade_dependency": RuleSuggestionService._suggest_outlier_trade_dependency,
            "drawdown_cluster_dependency": RuleSuggestionService._suggest_drawdown_cluster_dependency,
        }
        handler = handlers.get(structural_diag.failure_pattern)
        if handler is None:
            _log.warning(
                "Unrecognised structural pattern '%s' — no suggestion generated",
                structural_diag.failure_pattern,
            )
            return None
        return handler(structural_diag, params)

    @staticmethod
    def _suggest_entries_too_loose_in_chop(
        structural_diag: StructuralDiagnosis, params: dict
    ) -> ParameterSuggestion:
        """Tighten entry thresholds based on choppy market evidence."""
        buy_params = params.get("buy_params", {})
        # Find the highest threshold parameter and tighten it
        # Common parameters: rsi, macd, stoch, etc.
        proposed_buy_params = dict(buy_params)

        # Example: if rsi_buy is present, reduce it slightly
        if "rsi_buy" in proposed_buy_params:
            current = proposed_buy_params["rsi_buy"]
            proposed_buy_params["rsi_buy"] = current - 2 if isinstance(current, (int, float)) else current
        elif "mfi_buy" in proposed_buy_params:
            current = proposed_buy_params["mfi_buy"]
            proposed_buy_params["mfi_buy"] = current - 2 if isinstance(current, (int, float)) else current

        _log.debug(
            "entries_too_loose_in_chop: buy_params adjusted based on choppy market evidence"
        )
        return ParameterSuggestion(
            parameter="buy_params",
            proposed_value=proposed_buy_params,
            reason=f"Entry thresholds are too loose in choppy market conditions ({structural_diag.evidence})",
            expected_effect="More selective entries, better performance in choppy markets",
        )

    @staticmethod
    def _suggest_single_regime_dependency(
        structural_diag: StructuralDiagnosis, params: dict
    ) -> ParameterSuggestion:
        """Add regime filters to reduce single-regime dependency."""
        _log.debug("single_regime_dependency: adding regime filter suggestion")
        return ParameterSuggestion(
            parameter="entry_filters",
            proposed_value=["regime_filter"],
            reason=f"Strategy depends heavily on single regime ({structural_diag.evidence})",
            expected_effect="Better performance across multiple market regimes",
            is_advisory=True,
        )

    @staticmethod
    def _suggest_outlier_trade_dependency(
        structural_diag: StructuralDiagnosis, params: dict
    ) -> ParameterSuggestion:
        """Adjust position sizing to reduce outlier trade dependency."""
        current_max_open = params.get("max_open_trades", 3)
        proposed_max_open = max(current_max_open + 2, 5)

        _log.debug(
            "outlier_trade_dependency: increasing max_open_trades to reduce outlier dependency"
        )
        return ParameterSuggestion(
            parameter="max_open_trades",
            proposed_value=proposed_max_open,
            reason=f"Strategy performance depends on outlier trades ({structural_diag.evidence})",
            expected_effect="More consistent performance, less reliance on outliers",
        )

    @staticmethod
    def _suggest_drawdown_cluster_dependency(
        structural_diag: StructuralDiagnosis, params: dict
    ) -> ParameterSuggestion:
        """Adjust stoploss or max_open_trades to reduce drawdown cluster dependency."""
        current_stoploss = params.get("stoploss", -0.10)
        proposed_stoploss = round(current_stoploss + 0.02, 10)

        _log.debug(
            "drawdown_cluster_dependency: tightening stoploss to reduce drawdown cluster dependency"
        )
        return ParameterSuggestion(
            parameter="stoploss",
            proposed_value=proposed_stoploss,
            reason=f"Drawdown clusters are causing significant losses ({structural_diag.evidence})",
            expected_effect="Reduced drawdown severity during cluster events",
        )

    @staticmethod
    def _handle_issue(issue: DiagnosedIssue, params: dict) -> "ParameterSuggestion | None":
        """Dispatch a single issue to its handler.

        Args:
            issue: The diagnosed issue to handle.
            params: Current strategy parameters dict.

        Returns:
            A ParameterSuggestion, or None if the issue type is unrecognised.
        """
        handlers = {
            "stoploss_too_wide": RuleSuggestionService._suggest_stoploss_too_wide,
            "trades_too_low": RuleSuggestionService._suggest_trades_too_low,
            "weak_win_rate": RuleSuggestionService._suggest_weak_win_rate,
            "drawdown_high": RuleSuggestionService._suggest_drawdown_high,
            "poor_pair_concentration": RuleSuggestionService._suggest_poor_pair_concentration,
            "negative_profit": RuleSuggestionService._suggest_negative_profit,
            "profit_factor_low": RuleSuggestionService._suggest_profit_factor_low,
            "expectancy_negative": RuleSuggestionService._suggest_expectancy_negative,
        }
        handler = handlers.get(issue.issue_id)
        if handler is None:
            _log.warning("Unrecognised issue_id '%s' — no suggestion generated", issue.issue_id)
            return None
        return handler(params)

    @staticmethod
    def _suggest_stoploss_too_wide(params: dict) -> ParameterSuggestion:
        """Tighten stoploss by reducing its absolute value by 0.02."""
        current = params.get("stoploss", -0.10)
        proposed = round(current + 0.02, 10)
        _log.debug("stoploss_too_wide: %s -> %s", current, proposed)
        return ParameterSuggestion(
            parameter="stoploss",
            proposed_value=proposed,
            reason="Stoploss is too wide — tightening reduces per-trade loss exposure",
            expected_effect="Lower max drawdown, smaller individual losses",
        )

    @staticmethod
    def _suggest_trades_too_low(params: dict) -> ParameterSuggestion:
        """Increase max_open_trades by 1, capped at 10."""
        current = params.get("max_open_trades", 3)
        proposed = min(current + 1, 10)
        _log.debug("trades_too_low: %s -> %s", current, proposed)
        return ParameterSuggestion(
            parameter="max_open_trades",
            proposed_value=proposed,
            reason="Too few trades reduce statistical significance",
            expected_effect="More trades, better statistical confidence",
        )

    @staticmethod
    def _suggest_weak_win_rate(params: dict) -> ParameterSuggestion:
        """Lower the ROI value at the smallest integer key by 0.005."""
        minimal_roi: dict = params.get("minimal_roi", {})
        if minimal_roi:
            smallest_key = min(minimal_roi.keys(), key=lambda k: int(k))
            current_val = minimal_roi[smallest_key]
            proposed_roi = dict(minimal_roi)
            proposed_roi[smallest_key] = round(current_val - 0.005, 10)
        else:
            proposed_roi = minimal_roi
        _log.debug("weak_win_rate: minimal_roi smallest key adjusted")
        return ParameterSuggestion(
            parameter="minimal_roi",
            proposed_value=proposed_roi,
            reason="Lowering ROI target increases the chance of hitting take-profit",
            expected_effect="Higher win rate, lower average profit per trade",
        )

    @staticmethod
    def _suggest_drawdown_high(params: dict) -> ParameterSuggestion:
        """Decrease max_open_trades by 1, minimum 1."""
        current = params.get("max_open_trades", 3)
        proposed = max(current - 1, 1)
        _log.debug("drawdown_high: %s -> %s", current, proposed)
        return ParameterSuggestion(
            parameter="max_open_trades",
            proposed_value=proposed,
            reason="Reducing concurrent trades limits simultaneous drawdown exposure",
            expected_effect="Lower max drawdown",
        )

    @staticmethod
    def _suggest_poor_pair_concentration(_params: dict) -> ParameterSuggestion:
        """Advisory-only suggestion for poor pair concentration."""
        _log.debug("poor_pair_concentration: advisory suggestion")
        return ParameterSuggestion(
            parameter="pairlist",
            proposed_value=None,
            reason="Too few pairs reduce diversification",
            expected_effect="More diversified exposure; add pairs via Backtest page",
            is_advisory=True,
        )

    @staticmethod
    def _suggest_negative_profit(params: dict) -> ParameterSuggestion:
        """Tighten stoploss by reducing its absolute value by 0.03."""
        current = params.get("stoploss", -0.10)
        proposed = round(current + 0.03, 10)
        _log.debug("negative_profit: %s -> %s", current, proposed)
        return ParameterSuggestion(
            parameter="stoploss",
            proposed_value=proposed,
            reason="Negative total profit — cutting losses earlier may recover profitability",
            expected_effect="Reduced losses per trade",
        )

    @staticmethod
    def _suggest_profit_factor_low(_params: dict) -> ParameterSuggestion:
        """Advisory-only suggestion for profit factor below 1.0."""
        _log.debug("profit_factor_low: advisory suggestion")
        return ParameterSuggestion(
            parameter="entry_conditions",
            proposed_value=None,
            reason="Profit factor below 1.0 — losses exceed gains",
            expected_effect="Review entry/exit conditions to improve trade quality",
            is_advisory=True,
        )

    @staticmethod
    def _suggest_expectancy_negative(_params: dict) -> ParameterSuggestion:
        """Advisory-only suggestion for negative expectancy."""
        _log.debug("expectancy_negative: advisory suggestion")
        return ParameterSuggestion(
            parameter="entry_filters",
            proposed_value=None,
            reason="Negative expectancy — average trade loses money",
            expected_effect="Consider tightening entry filters to improve trade selectivity",
            is_advisory=True,
        )
