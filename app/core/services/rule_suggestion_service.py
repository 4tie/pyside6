"""
Stateless mapping from diagnosed issues to concrete parameter mutations.
"""
from __future__ import annotations

from typing import Callable, List, Optional

from app.core.models.diagnosis_models import StructuralDiagnosis
from app.core.models.exit_reason_models import ExitReasonSuggestion
from app.core.models.improve_models import DiagnosedIssue, ParameterSuggestion
from app.core.utils.app_logger import get_logger

_log = get_logger("services.rule_suggestion")


class RuleSuggestionService:
    """Maps diagnosed issues and structural patterns to concrete JSON mutations."""

    @staticmethod
    def suggest(
        issues: List[DiagnosedIssue],
        params: dict,
        structural: Optional[List[StructuralDiagnosis]] = None,
        exit_reason_suggestions: Optional[List[ExitReasonSuggestion]] = None,
    ) -> List[ParameterSuggestion]:
        """Return concrete parameter mutations for handled diagnoses.

        Advisory-only placeholders are intentionally excluded. If a diagnosis
        has no deterministic JSON mutation, no suggestion is returned for it.
        """
        suggestions: List[ParameterSuggestion] = []

        for issue in issues:
            suggestion = RuleSuggestionService._handle_issue(issue, params)
            if suggestion is not None:
                suggestions.append(suggestion)

        if structural:
            for structural_diag in structural:
                suggestion = RuleSuggestionService._handle_structural(structural_diag, params)
                if suggestion is not None:
                    suggestions.append(suggestion)

        if exit_reason_suggestions:
            for exit_suggestion in exit_reason_suggestions:
                suggestion = RuleSuggestionService._handle_exit_reason(exit_suggestion, params)
                if suggestion is not None:
                    suggestions.append(suggestion)

        return suggestions

    @staticmethod
    def _handle_structural(
        structural_diag: StructuralDiagnosis,
        params: dict,
    ) -> Optional[ParameterSuggestion]:
        handlers = {
            "entries_too_loose_in_chop": RuleSuggestionService._suggest_entries_too_loose_in_chop,
            "entries_too_late_in_trend": RuleSuggestionService._suggest_entries_too_late_in_trend,
            "exits_cutting_winners_early": RuleSuggestionService._suggest_exits_cutting_winners_early,
            "losers_lasting_too_long": RuleSuggestionService._suggest_losers_lasting_too_long,
            "single_regime_dependency": RuleSuggestionService._suggest_single_regime_dependency,
            "micro_loss_noise": RuleSuggestionService._suggest_micro_loss_noise,
            "filter_stack_too_strict": RuleSuggestionService._suggest_filter_stack_too_strict,
            "high_winrate_bad_payoff": RuleSuggestionService._suggest_high_winrate_bad_payoff,
            "outlier_trade_dependency": RuleSuggestionService._suggest_outlier_trade_dependency,
            "drawdown_after_volatility": RuleSuggestionService._suggest_drawdown_after_volatility,
            # New structural patterns
            "stoploss_during_volatility_expansion": RuleSuggestionService._suggest_volatility_aware_stoploss,
            "roi_cutting_trend_continuation": RuleSuggestionService._suggest_roi_trend_adjustment,
            "signal_exit_timing_mismatch": RuleSuggestionService._suggest_signal_confirmation,
            "trailing_stop_underperformance": RuleSuggestionService._suggest_trailing_stop_adjustment,
            # Backward-compatible alias for older tests/data.
            "drawdown_cluster_dependency": RuleSuggestionService._suggest_drawdown_after_volatility,
        }
        handler = handlers.get(structural_diag.failure_pattern)
        if handler is None:
            _log.warning(
                "Unrecognised structural pattern '%s' - no suggestion generated",
                structural_diag.failure_pattern,
            )
            return None
        return handler(structural_diag, params)

    @staticmethod
    def _handle_issue(issue: DiagnosedIssue, params: dict) -> Optional[ParameterSuggestion]:
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
            _log.warning("Unrecognised issue_id '%s' - no suggestion generated", issue.issue_id)
            return None
        return handler(params)

    @staticmethod
    def _first_numeric_key(
        group: dict,
        preferred_keys: Optional[List[str]] = None,
        selector: str = "first",
    ) -> Optional[str]:
        numeric_keys = [
            key
            for key, value in group.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        ]
        if preferred_keys:
            for key in preferred_keys:
                if key in numeric_keys:
                    return key
        if not numeric_keys:
            return None
        if selector == "max_abs":
            return max(numeric_keys, key=lambda key: abs(group[key]))
        if selector == "min_abs":
            return min(numeric_keys, key=lambda key: abs(group[key]))
        return numeric_keys[0]

    @staticmethod
    def _clone_group_with_change(
        group: dict,
        key: str,
        transform: Callable[[float], float],
    ) -> Optional[dict]:
        current = group.get(key)
        if not isinstance(current, (int, float)) or isinstance(current, bool):
            return None
        proposed = transform(current)
        if isinstance(current, int):
            proposed = int(round(proposed))
        else:
            proposed = round(proposed, 6)
        if proposed == current:
            return None
        new_group = dict(group)
        new_group[key] = proposed
        return new_group

    @staticmethod
    def _tighten_buy_group(buy_params: dict) -> Optional[dict]:
        key = RuleSuggestionService._first_numeric_key(
            buy_params,
            preferred_keys=["rsi_buy", "mfi_buy"],
            selector="min_abs",
        )
        if key is None:
            return None

        if key in {"rsi_buy", "mfi_buy"}:
            return RuleSuggestionService._clone_group_with_change(
                buy_params,
                key,
                lambda current: current - 2,
            )

        return RuleSuggestionService._clone_group_with_change(
            buy_params,
            key,
            lambda current: current * 1.1 if current >= 0 else current * 0.9,
        )

    @staticmethod
    def _relax_buy_group(buy_params: dict) -> Optional[dict]:
        key = RuleSuggestionService._first_numeric_key(
            buy_params,
            preferred_keys=["rsi_buy", "mfi_buy"],
            selector="max_abs",
        )
        if key is None:
            return None

        if key in {"rsi_buy", "mfi_buy"}:
            return RuleSuggestionService._clone_group_with_change(
                buy_params,
                key,
                lambda current: current + 2,
            )

        return RuleSuggestionService._clone_group_with_change(
            buy_params,
            key,
            lambda current: current * 0.9 if current >= 0 else current * 1.1,
        )

    @staticmethod
    def _adjust_sell_group(sell_params: dict) -> Optional[dict]:
        key = RuleSuggestionService._first_numeric_key(sell_params, selector="first")
        if key is None:
            return None
        return RuleSuggestionService._clone_group_with_change(
            sell_params,
            key,
            lambda current: current * 0.95 if current >= 0 else current * 1.05,
        )

    @staticmethod
    def _suggest_entries_too_loose_in_chop(
        structural_diag: StructuralDiagnosis,
        params: dict,
    ) -> Optional[ParameterSuggestion]:
        proposed_buy_params = RuleSuggestionService._tighten_buy_group(params.get("buy_params", {}))
        if proposed_buy_params is None:
            return None
        return ParameterSuggestion(
            parameter="buy_params",
            proposed_value=proposed_buy_params,
            reason=(
                "Entry thresholds are too loose in choppy market conditions "
                f"({structural_diag.evidence})"
            ),
            expected_effect="More selective entries in sideways markets",
        )

    @staticmethod
    def _suggest_entries_too_late_in_trend(
        structural_diag: StructuralDiagnosis,
        params: dict,
    ) -> Optional[ParameterSuggestion]:
        proposed_sell_params = RuleSuggestionService._adjust_sell_group(params.get("sell_params", {}))
        if proposed_sell_params is not None:
            return ParameterSuggestion(
                parameter="sell_params",
                proposed_value=proposed_sell_params,
                reason=f"Entries are arriving too late in trend moves ({structural_diag.evidence})",
                expected_effect="Reduce lag in the trend-capture logic",
            )

        proposed_buy_params = RuleSuggestionService._relax_buy_group(params.get("buy_params", {}))
        if proposed_buy_params is None:
            return None
        return ParameterSuggestion(
            parameter="buy_params",
            proposed_value=proposed_buy_params,
            reason=f"Entries are arriving too late in trend moves ({structural_diag.evidence})",
            expected_effect="Allow earlier participation in trend moves",
        )

    @staticmethod
    def _suggest_exits_cutting_winners_early(
        structural_diag: StructuralDiagnosis,
        params: dict,
    ) -> Optional[ParameterSuggestion]:
        minimal_roi: dict = params.get("minimal_roi", {})
        if not minimal_roi:
            return None
        proposed_roi = {key: round(value + 0.005, 6) for key, value in minimal_roi.items()}
        if proposed_roi == minimal_roi:
            return None
        return ParameterSuggestion(
            parameter="minimal_roi",
            proposed_value=proposed_roi,
            reason=f"Winners are being exited too early ({structural_diag.evidence})",
            expected_effect="Let winning trades run further before profit-taking",
        )

    @staticmethod
    def _suggest_losers_lasting_too_long(
        structural_diag: StructuralDiagnosis,
        params: dict,
    ) -> Optional[ParameterSuggestion]:
        current = params.get("stoploss", -0.10)
        proposed = round(max(-0.30, current + 0.02), 10)
        if proposed == current:
            return None
        return ParameterSuggestion(
            parameter="stoploss",
            proposed_value=proposed,
            reason=f"Losing trades are lasting too long ({structural_diag.evidence})",
            expected_effect="Cut losing positions earlier",
        )

    @staticmethod
    def _suggest_single_regime_dependency(
        structural_diag: StructuralDiagnosis,
        params: dict,
    ) -> Optional[ParameterSuggestion]:
        current = params.get("max_open_trades", 3)
        proposed = max(current - 1, 1)
        if proposed == current:
            return None
        return ParameterSuggestion(
            parameter="max_open_trades",
            proposed_value=proposed,
            reason=f"Performance is regime-dependent ({structural_diag.evidence})",
            expected_effect="Reduce exposure concentration while broadening robustness",
        )

    @staticmethod
    def _suggest_micro_loss_noise(
        structural_diag: StructuralDiagnosis,
        params: dict,
    ) -> Optional[ParameterSuggestion]:
        current = params.get("stoploss", -0.10)
        proposed = round(max(-0.30, current + 0.01), 10)
        if proposed == current:
            return None
        return ParameterSuggestion(
            parameter="stoploss",
            proposed_value=proposed,
            reason=f"Micro-loss noise is dominating outcomes ({structural_diag.evidence})",
            expected_effect="Trim noisy losing trades faster",
        )

    @staticmethod
    def _suggest_filter_stack_too_strict(
        structural_diag: StructuralDiagnosis,
        params: dict,
    ) -> Optional[ParameterSuggestion]:
        proposed_buy_params = RuleSuggestionService._relax_buy_group(params.get("buy_params", {}))
        if proposed_buy_params is None:
            return None
        return ParameterSuggestion(
            parameter="buy_params",
            proposed_value=proposed_buy_params,
            reason=f"The entry filter stack is too strict ({structural_diag.evidence})",
            expected_effect="Increase signal frequency without changing code",
        )

    @staticmethod
    def _suggest_high_winrate_bad_payoff(
        structural_diag: StructuralDiagnosis,
        params: dict,
    ) -> Optional[ParameterSuggestion]:
        minimal_roi: dict = params.get("minimal_roi", {})
        if not minimal_roi:
            return None
        proposed_roi = {key: round(value + 0.01, 6) for key, value in minimal_roi.items()}
        if proposed_roi == minimal_roi:
            return None
        return ParameterSuggestion(
            parameter="minimal_roi",
            proposed_value=proposed_roi,
            reason=f"Win rate is high but payoff is too weak ({structural_diag.evidence})",
            expected_effect="Improve risk/reward by letting winners run further",
        )

    @staticmethod
    def _suggest_outlier_trade_dependency(
        structural_diag: StructuralDiagnosis,
        params: dict,
    ) -> Optional[ParameterSuggestion]:
        current = params.get("max_open_trades", 3)
        proposed = max(current - 1, 1)
        if proposed == current:
            return None
        return ParameterSuggestion(
            parameter="max_open_trades",
            proposed_value=proposed,
            reason=f"Results rely too heavily on outlier trades ({structural_diag.evidence})",
            expected_effect="Reduce dependence on a handful of large winners",
        )

    @staticmethod
    def _suggest_drawdown_after_volatility(
        structural_diag: StructuralDiagnosis,
        params: dict,
    ) -> Optional[ParameterSuggestion]:
        current = params.get("stoploss", -0.10)
        proposed = round(max(-0.30, current + 0.015), 10)
        if proposed == current:
            return None
        return ParameterSuggestion(
            parameter="stoploss",
            proposed_value=proposed,
            reason=f"Drawdowns spike after volatility expansion ({structural_diag.evidence})",
            expected_effect="Reduce drawdown sensitivity during volatile regimes",
        )

    @staticmethod
    def _suggest_drawdown_cluster_dependency(
        structural_diag: StructuralDiagnosis,
        params: dict,
    ) -> Optional[ParameterSuggestion]:
        """Backward-compatible alias for older direct-call tests/data."""
        return RuleSuggestionService._suggest_drawdown_after_volatility(structural_diag, params)

    @staticmethod
    def _suggest_stoploss_too_wide(params: dict) -> Optional[ParameterSuggestion]:
        current = params.get("stoploss", -0.10)
        proposed = round(current + 0.02, 10)
        if proposed == current:
            return None
        return ParameterSuggestion(
            parameter="stoploss",
            proposed_value=proposed,
            reason="Stoploss is too wide; tightening reduces per-trade loss exposure",
            expected_effect="Lower max drawdown and smaller losses",
        )

    @staticmethod
    def _suggest_trades_too_low(params: dict) -> Optional[ParameterSuggestion]:
        current = params.get("max_open_trades", 3)
        proposed = min(current + 1, 10)
        if proposed == current:
            return None
        return ParameterSuggestion(
            parameter="max_open_trades",
            proposed_value=proposed,
            reason="Trade count is too low for useful iteration feedback",
            expected_effect="Increase trade frequency and statistical confidence",
        )

    @staticmethod
    def _suggest_weak_win_rate(params: dict) -> Optional[ParameterSuggestion]:
        minimal_roi: dict = params.get("minimal_roi", {})
        if not minimal_roi:
            return None
        smallest_key = min(minimal_roi.keys(), key=lambda key: int(key))
        current_val = minimal_roi[smallest_key]
        proposed_roi = dict(minimal_roi)
        proposed_roi[smallest_key] = round(current_val - 0.005, 10)
        if proposed_roi == minimal_roi:
            return None
        return ParameterSuggestion(
            parameter="minimal_roi",
            proposed_value=proposed_roi,
            reason="Lowering the fastest ROI target can improve win rate",
            expected_effect="Higher hit rate with smaller average wins",
        )

    @staticmethod
    def _suggest_drawdown_high(params: dict) -> Optional[ParameterSuggestion]:
        current = params.get("max_open_trades", 3)
        proposed = max(current - 1, 1)
        if proposed == current:
            return None
        return ParameterSuggestion(
            parameter="max_open_trades",
            proposed_value=proposed,
            reason="Drawdown is too high; reducing concurrency limits exposure",
            expected_effect="Lower simultaneous drawdown pressure",
        )

    @staticmethod
    def _suggest_poor_pair_concentration(_params: dict) -> Optional[ParameterSuggestion]:
        _log.debug("poor_pair_concentration has no deterministic JSON mutation")
        return None

    @staticmethod
    def _suggest_negative_profit(params: dict) -> Optional[ParameterSuggestion]:
        current = params.get("stoploss", -0.10)
        proposed = round(current + 0.03, 10)
        if proposed == current:
            return None
        return ParameterSuggestion(
            parameter="stoploss",
            proposed_value=proposed,
            reason="Total profit is negative; cutting losses earlier may help",
            expected_effect="Reduce loss severity on failed trades",
        )

    @staticmethod
    def _suggest_profit_factor_low(_params: dict) -> Optional[ParameterSuggestion]:
        _log.debug("profit_factor_low has no deterministic JSON mutation")
        return None

    @staticmethod
    def _suggest_expectancy_negative(_params: dict) -> Optional[ParameterSuggestion]:
        _log.debug("expectancy_negative has no deterministic JSON mutation")
        return None

    # ------------------------------------------------------------------
    # Exit reason handlers
    # ------------------------------------------------------------------

    @staticmethod
    def _handle_exit_reason(
        exit_suggestion: ExitReasonSuggestion,
        params: dict,
    ) -> Optional[ParameterSuggestion]:
        """Map exit reason suggestions to parameter mutations."""
        handlers = {
            "stoploss": RuleSuggestionService._suggest_stoploss_too_wide,  # Reuse existing handler
            "roi": RuleSuggestionService._suggest_roi_adjustment,
            "signal": RuleSuggestionService._suggest_signal_filter,
            "trailing_stop": RuleSuggestionService._suggest_trailing_stop_adjustment,
            "force_exit": RuleSuggestionService._suggest_risk_reduction,
            "timing_mismatch": RuleSuggestionService._suggest_asymmetric_exits,
        }

        handler = handlers.get(exit_suggestion.affected_reason)
        if handler is None:
            _log.debug(
                "No handler for exit reason '%s' — skipping suggestion",
                exit_suggestion.affected_reason,
            )
            return None

        return handler(params)

    @staticmethod
    def _suggest_roi_adjustment(params: dict) -> Optional[ParameterSuggestion]:
        """Suggest ROI adjustment based on exit reason analysis."""
        minimal_roi: dict = params.get("minimal_roi", {})
        if not minimal_roi:
            return None

        # Widen ROI targets to capture larger moves
        proposed_roi = {key: round(value + 0.005, 6) for key, value in minimal_roi.items()}
        if proposed_roi == minimal_roi:
            return None

        return ParameterSuggestion(
            parameter="minimal_roi",
            proposed_value=proposed_roi,
            reason="ROI exits dominate but underperform — widening targets",
            expected_improvement="Better profit capture on winning trades",
        )

    @staticmethod
    def _suggest_signal_filter(params: dict) -> Optional[ParameterSuggestion]:
        """Suggest adding entry confirmation filter."""
        buy_params: dict = params.get("buy_params", {})
        if not buy_params:
            return None

        # Tighten first numeric buy param as proxy for confirmation
        numeric_keys = [
            key for key, value in buy_params.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        ]
        if not numeric_keys:
            return None

        target_key = numeric_keys[0]
        current_val = buy_params[target_key]

        # Tighten threshold (decrease for RSI-like, increase for momentum-like)
        if isinstance(current_val, (int, float)):
            delta = -2 if isinstance(current_val, int) else -0.02
            proposed_val = current_val + delta

            proposed_group = dict(buy_params)
            proposed_group[target_key] = round(proposed_val, 6) if isinstance(current_val, float) else int(round(proposed_val))

            return ParameterSuggestion(
                parameter="buy_params",
                proposed_value=proposed_group,
                reason="Signal exits have poor performance — adding confirmation",
                expected_improvement="Better entry quality",
            )
        return None

    @staticmethod
    def _suggest_trailing_stop_adjustment(params: dict) -> Optional[ParameterSuggestion]:
        """Suggest trailing stop adjustment."""
        if not params.get("trailing_stop", False):
            # Enable trailing stop if disabled
            return ParameterSuggestion(
                parameter="trailing_stop",
                proposed_value=True,
                reason="Trailing stop underperforming — enabling with defaults",
                expected_improvement="Better profit protection",
            )

        # Adjust existing trailing stop parameters
        current_positive = params.get("trailing_stop_positive", 0.0)
        proposed_positive = round(current_positive + 0.005, 6) if current_positive > 0 else 0.01

        return ParameterSuggestion(
            parameter="trailing_stop_positive",
            proposed_value=proposed_positive,
            reason="Trailing stop underperforming — tightening distance",
            expected_improvement="Earlier profit capture without premature exits",
        )

    @staticmethod
    def _suggest_risk_reduction(params: dict) -> Optional[ParameterSuggestion]:
        """Suggest risk reduction measures."""
        current_mot = params.get("max_open_trades", 3)
        proposed_mot = max(current_mot - 1, 1)

        if proposed_mot == current_mot:
            return None

        return ParameterSuggestion(
            parameter="max_open_trades",
            proposed_value=proposed_mot,
            reason="High forced/emergency exit rate — reducing exposure",
            expected_improvement="Fewer forced liquidations",
        )

    @staticmethod
    def _suggest_asymmetric_exits(params: dict) -> Optional[ParameterSuggestion]:
        """Suggest asymmetric exit rules for timing mismatch."""
        # Reduce stoploss (tighten) to exit losers faster
        current_stoploss = params.get("stoploss", -0.10)
        proposed_stoploss = round(max(-0.30, current_stoploss + 0.02), 10)

        if proposed_stoploss == current_stoploss:
            return None

        return ParameterSuggestion(
            parameter="stoploss",
            proposed_value=proposed_stoploss,
            reason="Losers lasting too long vs winners — tightening stoploss",
            expected_improvement="Faster exit from losing trades",
        )

    # ------------------------------------------------------------------
    # New structural pattern handlers (Phase 2)
    # ------------------------------------------------------------------

    @staticmethod
    def _suggest_volatility_aware_stoploss(params: dict) -> Optional[ParameterSuggestion]:
        """Suggest volatility-aware stoploss adjustment."""
        current_stoploss = params.get("stoploss", -0.10)

        # Widen stoploss slightly to accommodate volatility
        proposed_stoploss = round(min(-0.05, current_stoploss - 0.02), 10)

        if proposed_stoploss == current_stoploss:
            return None

        return ParameterSuggestion(
            parameter="stoploss",
            proposed_value=proposed_stoploss,
            reason="Stoploss hitting during volatility spikes — widening to accommodate",
            expected_improvement="Fewer premature stoploss hits during normal volatility",
        )

    @staticmethod
    def _suggest_roi_trend_adjustment(params: dict) -> Optional[ParameterSuggestion]:
        """Suggest ROI adjustment for trend continuation."""
        minimal_roi: dict = params.get("minimal_roi", {})
        if not minimal_roi:
            return None

        # Widen ROI targets to capture trend continuation
        proposed_roi = {key: round(value + 0.01, 6) for key, value in minimal_roi.items()}

        if proposed_roi == minimal_roi:
            return None

        return ParameterSuggestion(
            parameter="minimal_roi",
            proposed_value=proposed_roi,
            reason="ROI cutting trend continuation — widening targets",
            expected_improvement="Capture larger moves during trending periods",
        )

    @staticmethod
    def _suggest_signal_confirmation(params: dict) -> Optional[ParameterSuggestion]:
        """Suggest adding confirmation to entry/exit signals."""
        buy_params: dict = params.get("buy_params", {})
        if not buy_params:
            return None

        # Find and tighten a threshold parameter
        numeric_keys = [
            key for key, value in buy_params.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        ]
        if not numeric_keys:
            return None

        target_key = numeric_keys[0]
        current_val = buy_params[target_key]

        if isinstance(current_val, (int, float)):
            # Tighten the threshold
            delta = -3 if isinstance(current_val, int) else -0.03
            proposed_val = current_val + delta

            proposed_group = dict(buy_params)
            proposed_group[target_key] = (
                round(proposed_val, 6) if isinstance(current_val, float)
                else int(round(proposed_val))
            )

            return ParameterSuggestion(
                parameter="buy_params",
                proposed_value=proposed_group,
                reason="Signal exits underperforming — adding confirmation",
                expected_improvement="Higher quality entries and exits",
            )
        return None

    @staticmethod
    def _suggest_trailing_stop_adjustment(params: dict) -> Optional[ParameterSuggestion]:
        """Suggest trailing stop parameter adjustment."""
        if not params.get("trailing_stop", False):
            # Enable trailing stop
            return ParameterSuggestion(
                parameter="trailing_stop",
                proposed_value=True,
                reason="Trailing stop disabled — enabling for profit protection",
                expected_improvement="Better profit protection on winning trades",
            )

        # Adjust trailing stop positive offset
        current_positive = params.get("trailing_stop_positive", 0.0)
        proposed_positive = round(current_positive + 0.01, 6) if current_positive > 0 else 0.02

        return ParameterSuggestion(
            parameter="trailing_stop_positive",
            proposed_value=proposed_positive,
            reason="Trailing stop underperforming — adjusting activation threshold",
            expected_improvement="Earlier profit protection without premature exits",
        )
