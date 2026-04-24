"""
ai_advisor_service.py — AI-powered parameter suggestion layer for the Strategy Lab.

Builds prompts from backtest context and diagnosed issues, calls the configured
AI model via AIService, and returns a parameter suggestion dict.
"""
from __future__ import annotations

import re
from typing import Dict, Optional

from app.core.utils.app_logger import get_logger
from app.core.parsing.json_parser import parse_json_string, json_dumps

_log = get_logger("services.ai_advisor")

# Valid parameter ranges for clamping AI suggestions
_PARAM_RANGES: Dict[str, tuple] = {
    "stoploss": (-0.99, -0.001),
    "max_open_trades": (1, 100),
    "trailing_stop_positive": (0.001, 0.50),
    "trailing_stop_positive_offset": (0.001, 0.50),
}


class AIAdvisorService:
    """AI-powered suggestion layer for the Strategy Lab loop.

    Builds structured prompts from backtest context and diagnosed issues,
    calls the configured AI model, and returns a parameter suggestion dict.
    Clamps out-of-range values and returns None on failure.

    Args:
        ai_service: The application AIService instance (optional). When None,
            request_suggestion() always returns None.
    """

    def __init__(self, ai_service: Optional[Any] = None) -> None:
        self._ai_service = ai_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_prompt(
        self,
        strategy_name: str,
        params: dict,
        summary: Any,
        issues: List[Any],
    ) -> str:
        """Build a structured prompt for the AI model.

        Includes strategy name, current parameter values, backtest metrics,
        and diagnosed issues.

        Args:
            strategy_name: Strategy class name.
            params: Current strategy parameter dict.
            summary: BacktestSummary with backtest metrics.
            issues: List of DiagnosedIssue or StructuralDiagnosis objects.

        Returns:
            Formatted prompt string.
        """
        # Format parameters
        params_lines = []
        for k, v in params.items():
            if isinstance(v, dict):
                params_lines.append(f"  {k}: {json_dumps(v)}")
            else:
                params_lines.append(f"  {k}: {v}")
        params_str = "\n".join(params_lines) if params_lines else "  (none)"

        # Format metrics
        metrics_str = (
            f"  profit: {getattr(summary, 'total_profit', 'N/A'):.2f}%\n"
            f"  win_rate: {getattr(summary, 'win_rate', 'N/A'):.2f}%\n"
            f"  max_drawdown: {getattr(summary, 'max_drawdown', 'N/A'):.2f}%\n"
            f"  sharpe_ratio: {getattr(summary, 'sharpe_ratio', 'N/A')}\n"
            f"  total_trades: {getattr(summary, 'total_trades', 'N/A')}\n"
            f"  expectancy: {getattr(summary, 'expectancy', 'N/A'):.4f}\n"
            f"  profit_factor: {getattr(summary, 'profit_factor', 'N/A'):.2f}"
        )

        # Format issues
        issue_lines = []
        for issue in issues:
            if hasattr(issue, "failure_pattern"):
                issue_lines.append(
                    f"  - [{issue.failure_pattern}] {issue.evidence} "
                    f"→ {issue.mutation_direction}"
                )
            elif hasattr(issue, "issue_id"):
                issue_lines.append(f"  - [{issue.issue_id}] {issue.description}")
        issues_str = "\n".join(issue_lines) if issue_lines else "  (none)"

        return (
            f"You are an expert Freqtrade strategy optimizer.\n\n"
            f"Strategy: {strategy_name}\n\n"
            f"Current parameters:\n{params_str}\n\n"
            f"Latest backtest metrics:\n{metrics_str}\n\n"
            f"Diagnosed issues:\n{issues_str}\n\n"
            f"Based on the above, suggest ONE specific parameter change that would most "
            f"improve the strategy's robustness. Respond ONLY with a JSON object mapping "
            f"parameter names to their proposed values. Example: "
            f'{{\"stoploss\": -0.08, \"max_open_trades\": 4}}\n'
            f"Do not include any explanation outside the JSON object."
        )

    def request_suggestion(self, prompt: str) -> Optional[dict]:
        """Call the AI model with the given prompt and return a parameter suggestion.

        Clamps any out-of-range values in the returned suggestion. Returns None
        on timeout, API failure, or parse error.

        Args:
            prompt: The structured prompt built by build_prompt().

        Returns:
            Dict of parameter suggestions, or None on failure.
        """
        if self._ai_service is None:
            _log.debug("AIAdvisorService: no AI service configured — returning None")
            return None

        try:
            ai_settings = None
            if hasattr(self._ai_service, "_settings_state"):
                s = self._ai_service._settings_state
                if s is not None and hasattr(s, "current_settings") and s.current_settings:
                    ai_settings = s.current_settings.ai

            runtime = self._ai_service.get_runtime(ai_settings)

            # Use a synchronous call via the runtime's provider directly
            provider = runtime._provider if hasattr(runtime, "_provider") else None
            if provider is None:
                # Fall back to building a provider from settings
                from app.core.ai.providers.provider_factory import ProviderFactory
                if ai_settings is not None:
                    provider = ProviderFactory.create(ai_settings)
                else:
                    _log.warning("AIAdvisorService: cannot build provider — no settings")
                    return None

            model = (
                ai_settings.task_model or ai_settings.chat_model
                if ai_settings else ""
            )
            response = provider.complete(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                stream=False,
            )
            text = response.content if hasattr(response, "content") else str(response)
            return self._parse_suggestion(text)

        except Exception as exc:
            _log.warning("AIAdvisorService.request_suggestion failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_suggestion(self, text: str) -> Optional[dict]:
        """Extract and validate a JSON parameter dict from the AI response.

        Args:
            text: Raw AI response text.

        Returns:
            Validated and clamped parameter dict, or None if parsing fails.
        """
        import re
        # Extract the first JSON object from the response
        match = re.search(r"\{[^{}]+\}", text, re.DOTALL)
        if not match:
            _log.warning("AIAdvisorService: no JSON object found in response")
            return None

        try:
            suggestion = parse_json_string(match.group())
        except Exception as exc:
            _log.warning("AIAdvisorService: JSON parse error: %s", exc)
            return None

        if not isinstance(suggestion, dict):
            return None

        # Clamp out-of-range values
        clamped = {}
        for k, v in suggestion.items():
            if k in _PARAM_RANGES and isinstance(v, (int, float)):
                lo, hi = _PARAM_RANGES[k]
                if v < lo or v > hi:
                    _log.warning(
                        "AIAdvisorService: clamping %s from %s to [%s, %s]",
                        k, v, lo, hi,
                    )
                    v = max(lo, min(hi, v))
            clamped[k] = v

        return clamped if clamped else None
