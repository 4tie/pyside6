"""
rl_models.py — Data models for reinforcement learning advisor.

Provides RLAgentState for Q-learning based parameter adjustment recommendations.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.core.parsing.json_parser import parse_json_file, write_json_file_atomic

from app.core.utils.app_logger import get_logger

_log = get_logger("models.rl")


@dataclass
class RLAgentState:
    """State for Q-learning reinforcement learning agent.

    Attributes:
        q_table: Q-values mapping (state, action) -> value.
        learning_rate: Alpha - how much to update Q-values.
        discount_factor: Gamma - importance of future rewards.
        exploration_rate: Epsilon - probability of random action.
        min_exploration_rate: Minimum epsilon for exploration.
        exploration_decay: Decay factor for epsilon after each episode.
        episode_count: Number of training episodes completed.
        total_reward: Cumulative reward across all episodes.
    """

    q_table: Dict[str, Dict[str, float]] = field(default_factory=dict)
    learning_rate: float = 0.1
    discount_factor: float = 0.95
    exploration_rate: float = 0.2
    min_exploration_rate: float = 0.05
    exploration_decay: float = 0.995
    episode_count: int = 0
    total_reward: float = 0.0

    # Known states and actions
    KNOWN_STATES = [
        "high_dd_high_wr",      # High drawdown, high win rate
        "high_dd_low_wr",       # High drawdown, low win rate
        "low_dd_high_wr",       # Low drawdown, high win rate
        "low_dd_low_wr",        # Low drawdown, low win rate
        "high_profit",          # High profit
        "negative_profit",      # Negative profit
        "low_trade_count",      # Few trades
        "stoploss_dominant",    # Stoploss exits dominate
        "roi_dominant",         # ROI exits dominate
        "signal_dominant",      # Signal exits dominate
        "trailing_underperf",   # Trailing stop underperforming
        "high_volatility",      # High volatility environment
        "choppy_market",        # Choppy/sideways market
        "trending_market",      # Trending market
        "default",              # Default/unknown state
    ]

    KNOWN_ACTIONS = [
        "tighten_stoploss",
        "widen_stoploss",
        "increase_roi",
        "decrease_roi",
        "tighten_buy_params",
        "relax_buy_params",
        "increase_mot",
        "decrease_mot",
        "enable_trailing",
        "disable_trailing",
        "tighten_trailing",
        "widen_trailing",
        "no_change",
    ]

    def get_state_signature(
        self,
        summary: any,
        exit_analysis: Optional[any] = None,
    ) -> str:
        """Generate state signature from backtest summary.

        Args:
            summary: BacktestSummary with metrics.
            exit_analysis: Optional ExitReasonAnalysis.

        Returns:
            State identifier string.
        """
        parts = []

        # Drawdown classification
        if hasattr(summary, 'max_drawdown'):
            dd = summary.max_drawdown
            if dd > 20:
                parts.append("high_dd")
            elif dd < 10:
                parts.append("low_dd")

        # Win rate classification
        if hasattr(summary, 'win_rate'):
            wr = summary.win_rate
            if wr > 55:
                parts.append("high_wr")
            elif wr < 45:
                parts.append("low_wr")

        # Profit classification
        if hasattr(summary, 'total_profit'):
            profit = summary.total_profit
            if profit > 10:
                parts.append("high_profit")
            elif profit < 0:
                parts.append("negative_profit")

        # Trade count
        if hasattr(summary, 'total_trades'):
            if summary.total_trades < 30:
                parts.append("low_trade_count")

        # Exit reason analysis
        if exit_analysis:
            if exit_analysis.has_high_stoploss_rate:
                parts.append("stoploss_dominant")
            if exit_analysis.has_roi_dominance:
                parts.append("roi_dominant")
            if exit_analysis.signal_rate_pct > 40:
                parts.append("signal_dominant")

        if not parts:
            return "default"

        return "_".join(parts)

    def get_q_value(self, state: str, action: str) -> float:
        """Get Q-value for a state-action pair."""
        if state not in self.q_table:
            self.q_table[state] = {}
        if action not in self.q_table[state]:
            self.q_table[state][action] = 0.0
        return self.q_table[state][action]

    def update_q_value(
        self,
        state: str,
        action: str,
        reward: float,
        next_state: str,
    ) -> None:
        """Update Q-value using Q-learning update rule.

        Q(s,a) = Q(s,a) + alpha * [reward + gamma * max(Q(s',a')) - Q(s,a)]
        """
        current_q = self.get_q_value(state, action)

        # Get max Q-value for next state
        next_q_values = [
            self.get_q_value(next_state, a)
            for a in self.KNOWN_ACTIONS
        ]
        max_next_q = max(next_q_values) if next_q_values else 0.0

        # Q-learning update
        new_q = current_q + self.learning_rate * (
            reward + self.discount_factor * max_next_q - current_q
        )

        if state not in self.q_table:
            self.q_table[state] = {}
        self.q_table[state][action] = new_q

    def select_action(self, state: str) -> str:
        """Select action using epsilon-greedy policy.

        Args:
            state: Current state.

        Returns:
            Selected action.
        """
        if random.random() < self.exploration_rate:
            # Exploration: random action
            return random.choice(self.KNOWN_ACTIONS)

        # Exploitation: best known action
        q_values = {
            action: self.get_q_value(state, action)
            for action in self.KNOWN_ACTIONS
        }

        max_q = max(q_values.values())
        best_actions = [a for a, q in q_values.items() if q == max_q]

        return random.choice(best_actions)

    def decay_exploration(self) -> None:
        """Decay exploration rate after an episode."""
        self.exploration_rate = max(
            self.min_exploration_rate,
            self.exploration_rate * self.exploration_decay,
        )

    def record_episode(self, reward: float) -> None:
        """Record completion of an episode."""
        self.episode_count += 1
        self.total_reward += reward
        self.decay_exploration()

    def get_action_recommendation(
        self,
        state: str,
        top_k: int = 3,
    ) -> List[Tuple[str, float]]:
        """Get top-k action recommendations for a state.

        Args:
            state: Current state.
            top_k: Number of recommendations.

        Returns:
            List of (action, q_value) tuples.
        """
        q_values = [
            (action, self.get_q_value(state, action))
            for action in self.KNOWN_ACTIONS
        ]

        q_values.sort(key=lambda x: x[1], reverse=True)
        return q_values[:top_k]

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "q_table": self.q_table,
            "learning_rate": self.learning_rate,
            "discount_factor": self.discount_factor,
            "exploration_rate": self.exploration_rate,
            "min_exploration_rate": self.min_exploration_rate,
            "exploration_decay": self.exploration_decay,
            "episode_count": self.episode_count,
            "total_reward": self.total_reward,
        }

    @classmethod
    def from_dict(cls, data: dict) -> RLAgentState:
        """Create from dictionary."""
        return cls(
            q_table=data.get("q_table", {}),
            learning_rate=data.get("learning_rate", 0.1),
            discount_factor=data.get("discount_factor", 0.95),
            exploration_rate=data.get("exploration_rate", 0.2),
            min_exploration_rate=data.get("min_exploration_rate", 0.05),
            exploration_decay=data.get("exploration_decay", 0.995),
            episode_count=data.get("episode_count", 0),
            total_reward=data.get("total_reward", 0.0),
        )

    def save(self, file_path: Path) -> None:
        """Save agent state to disk."""
        write_json_file_atomic(file_path, self.to_dict())
        _log.debug("Saved RL agent state to %s", file_path)

    @classmethod
    def load(cls, file_path: Path) -> RLAgentState:
        """Load agent state from disk."""
        if not file_path.exists():
            _log.debug("No saved RL state found at %s, creating new", file_path)
            return cls()

        try:
            data = parse_json_file(file_path)
            return cls.from_dict(data)
        except Exception as e:
            _log.error("Failed to load RL state: %s", e)
            return cls()
