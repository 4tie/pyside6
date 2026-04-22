"""
rl_advisor_service.py — Service for reinforcement learning based suggestions.

Uses Q-learning to recommend parameter adjustments based on historical outcomes.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from app.core.models.improve_models import ParameterSuggestion
from app.core.models.rl_models import RLAgentState
from app.core.utils.app_logger import get_logger

_log = get_logger("services.rl_advisor")


class RLAdvisorService:
    """Service providing RL-based parameter adjustment recommendations.

    Learns which adjustments work best in different diagnostic contexts.
    """

    _STATE_FILE = "rl_agent_state.json"

    def __init__(self, user_data_path: str) -> None:
        """Initialize with user data path.

        Args:
            user_data_path: Path to user_data directory.
        """
        self._user_data_path = Path(user_data_path)
        self._state_file = self._user_data_path / self._STATE_FILE
        self._agent = RLAgentState()
        self._load()

    def _load(self) -> None:
        """Load agent state from disk."""
        self._agent = RLAgentState.load(self._state_file)
        _log.debug(
            "Loaded RL agent: %d states, %d episodes",
            len(self._agent.q_table),
            self._agent.episode_count,
        )

    def _save(self) -> None:
        """Save agent state to disk."""
        try:
            self._agent.save(self._state_file)
        except Exception as e:
            _log.error("Failed to save RL state: %s", e)

    def get_suggestions(
        self,
        summary: any,
        params: dict,
        exit_analysis: Optional[any] = None,
        num_suggestions: int = 2,
    ) -> List[ParameterSuggestion]:
        """Get RL-based parameter suggestions.

        Args:
            summary: BacktestSummary with metrics.
            exit_analysis: Optional ExitReasonAnalysis.
            params: Current strategy parameters.
            num_suggestions: Number of suggestions to return.

        Returns:
            List of ParameterSuggestion objects.
        """
        # Get current state
        state = self._agent.get_state_signature(summary, exit_analysis)

        # Get top actions
        actions = self._agent.get_action_recommendation(state, top_k=num_suggestions)

        suggestions = []
        for action, q_value in actions:
            suggestion = self._action_to_suggestion(action, params, q_value)
            if suggestion:
                suggestions.append(suggestion)

        _log.debug(
            "RL advisor generated %d suggestions for state '%s'",
            len(suggestions),
            state,
        )

        return suggestions

    def _action_to_suggestion(
        self,
        action: str,
        params: dict,
        q_value: float,
    ) -> Optional[ParameterSuggestion]:
        """Convert an action to a ParameterSuggestion."""

        if action == "tighten_stoploss":
            current = params.get("stoploss", -0.10)
            proposed = round(max(-0.30, current + 0.02), 10)
            if proposed != current:
                return ParameterSuggestion(
                    parameter="stoploss",
                    proposed_value=proposed,
                    reason=f"RL advisor (Q={q_value:.3f}): Tighten stoploss to reduce drawdown",
                    expected_improvement="Lower max drawdown",
                )

        elif action == "widen_stoploss":
            current = params.get("stoploss", -0.10)
            proposed = round(min(-0.05, current - 0.02), 10)
            if proposed != current:
                return ParameterSuggestion(
                    parameter="stoploss",
                    proposed_value=proposed,
                    reason=f"RL advisor (Q={q_value:.3f}): Widen stoploss to avoid whipsaws",
                    expected_improvement="Fewer premature stoploss hits",
                )

        elif action == "increase_roi":
            minimal_roi = params.get("minimal_roi", {})
            if minimal_roi:
                proposed = {k: round(v + 0.01, 6) for k, v in minimal_roi.items()}
                return ParameterSuggestion(
                    parameter="minimal_roi",
                    proposed_value=proposed,
                    reason=f"RL advisor (Q={q_value:.3f}): Widen ROI targets",
                    expected_improvement="Capture larger moves",
                )

        elif action == "decrease_roi":
            minimal_roi = params.get("minimal_roi", {})
            if minimal_roi:
                proposed = {k: round(v - 0.005, 6) for k, v in minimal_roi.items()}
                return ParameterSuggestion(
                    parameter="minimal_roi",
                    proposed_value=proposed,
                    reason=f"RL advisor (Q={q_value:.3f}): Tighten ROI targets",
                    expected_improvement="Secure profits earlier",
                )

        elif action == "tighten_buy_params":
            buy_params = params.get("buy_params", {})
            if buy_params:
                # Find first numeric param and tighten
                for key, val in buy_params.items():
                    if isinstance(val, (int, float)) and not isinstance(val, bool):
                        delta = -2 if isinstance(val, int) else -0.02
                        proposed_val = val + delta
                        proposed_group = dict(buy_params)
                        proposed_group[key] = round(proposed_val, 6) if isinstance(val, float) else int(round(proposed_val))
                        return ParameterSuggestion(
                            parameter="buy_params",
                            proposed_value=proposed_group,
                            reason=f"RL advisor (Q={q_value:.3f}): Tighten entry criteria",
                            expected_improvement="More selective entries",
                        )

        elif action == "relax_buy_params":
            buy_params = params.get("buy_params", {})
            if buy_params:
                for key, val in buy_params.items():
                    if isinstance(val, (int, float)) and not isinstance(val, bool):
                        delta = 2 if isinstance(val, int) else 0.02
                        proposed_val = val + delta
                        proposed_group = dict(buy_params)
                        proposed_group[key] = round(proposed_val, 6) if isinstance(val, float) else int(round(proposed_val))
                        return ParameterSuggestion(
                            parameter="buy_params",
                            proposed_value=proposed_group,
                            reason=f"RL advisor (Q={q_value:.3f}): Relax entry criteria",
                            expected_improvement="More trade opportunities",
                        )

        elif action == "increase_mot":
            current = params.get("max_open_trades", 3)
            proposed = min(current + 1, 10)
            if proposed != current:
                return ParameterSuggestion(
                    parameter="max_open_trades",
                    proposed_value=proposed,
                    reason=f"RL advisor (Q={q_value:.3f}): Increase trade concurrency",
                    expected_improvement="More exposure to opportunities",
                )

        elif action == "decrease_mot":
            current = params.get("max_open_trades", 3)
            proposed = max(current - 1, 1)
            if proposed != current:
                return ParameterSuggestion(
                    parameter="max_open_trades",
                    proposed_value=proposed,
                    reason=f"RL advisor (Q={q_value:.3f}): Decrease trade concurrency",
                    expected_improvement="Reduce drawdown risk",
                )

        elif action == "enable_trailing":
            if not params.get("trailing_stop", False):
                return ParameterSuggestion(
                    parameter="trailing_stop",
                    proposed_value=True,
                    reason=f"RL advisor (Q={q_value:.3f}): Enable trailing stop",
                    expected_improvement="Better profit protection",
                )

        elif action == "disable_trailing":
            if params.get("trailing_stop", False):
                return ParameterSuggestion(
                    parameter="trailing_stop",
                    proposed_value=False,
                    reason=f"RL advisor (Q={q_value:.3f}): Disable trailing stop",
                    expected_improvement="Avoid premature exits",
                )

        elif action == "tighten_trailing":
            if params.get("trailing_stop", False):
                current = params.get("trailing_stop_positive", 0.0)
                proposed = round(current + 0.01, 6) if current > 0 else 0.02
                return ParameterSuggestion(
                    parameter="trailing_stop_positive",
                    proposed_value=proposed,
                    reason=f"RL advisor (Q={q_value:.3f}): Tighten trailing stop",
                    expected_improvement="Earlier profit capture",
                )

        elif action == "widen_trailing":
            if params.get("trailing_stop", False):
                current = params.get("trailing_stop_positive", 0.0)
                proposed = round(max(0.005, current - 0.01), 6)
                return ParameterSuggestion(
                    parameter="trailing_stop_positive",
                    proposed_value=proposed,
                    reason=f"RL advisor (Q={q_value:.3f}): Widen trailing stop",
                    expected_improvement="Let winners run longer",
                )

        return None

    def train(
        self,
        prev_summary: any,
        new_summary: any,
        action: str,
        exit_analysis: Optional[any] = None,
    ) -> None:
        """Train the agent based on outcome of an action.

        Args:
            prev_summary: BacktestSummary before modification.
            new_summary: BacktestSummary after modification.
            action: The action that was taken.
            exit_analysis: Optional ExitReasonAnalysis.
        """
        # Calculate reward based on score/profit improvement
        prev_score = getattr(prev_summary, 'total_profit', 0)
        new_score = getattr(new_summary, 'total_profit', 0)
        improvement = new_score - prev_score

        # Normalize reward
        reward = improvement / 10.0  # Scale so 10% improvement = 1.0 reward
        reward = max(-1.0, min(1.0, reward))  # Clip to [-1, 1]

        # Get states
        prev_state = self._agent.get_state_signature(prev_summary, exit_analysis)
        new_state = self._agent.get_state_signature(new_summary, exit_analysis)

        # Update Q-value
        self._agent.update_q_value(prev_state, action, reward, new_state)
        self._agent.record_episode(reward)

        _log.debug(
            "RL training: state='%s', action='%s', reward=%.3f, episode=%d",
            prev_state,
            action,
            reward,
            self._agent.episode_count,
        )

        self._save()

    def get_stats(self) -> dict:
        """Get current RL agent statistics."""
        return {
            "episode_count": self._agent.episode_count,
            "exploration_rate": self._agent.exploration_rate,
            "learning_rate": self._agent.learning_rate,
            "total_reward": self._agent.total_reward,
            "num_states": len(self._agent.q_table),
            "avg_reward_per_episode": (
                self._agent.total_reward / max(1, self._agent.episode_count)
            ),
        }

    def reset(self) -> None:
        """Reset the RL agent to initial state."""
        self._agent = RLAgentState()
        self._save()
        _log.info("Reset RL advisor to initial state")

    def export_state(self, export_path: Path) -> bool:
        """Export agent state to file."""
        try:
            self._agent.save(export_path)
            return True
        except Exception as e:
            _log.error("Failed to export RL state: %s", e)
            return False

    def import_state(self, import_path: Path) -> bool:
        """Import agent state from file."""
        try:
            self._agent = RLAgentState.load(import_path)
            self._save()
            return True
        except Exception as e:
            _log.error("Failed to import RL state: %s", e)
            return False
