"""
decision_engine.py — Pure function decision engine for action selection.

Part of the 4-layer diagnostic architecture.
Ranks actions and selects the best one, handling conflicts.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from app.core.models.pattern_models import (
    Action,
    FailurePattern,
    PatternDiagnosis,
)


class DecisionEngine:
    """Pure function decision engine.
    
    Selects the best action from pattern diagnoses.
    """

    @staticmethod
    def select(
        diagnoses: List[PatternDiagnosis],
        patterns: List[FailurePattern],
        knowledge: dict,
        iteration: int = 0
    ) -> Optional[Action]:
        """Select the best action from diagnoses.
        
        Pure function: input → output only.
        
        Args:
            diagnoses: List of pattern diagnoses
            patterns: List of failure patterns (for action lookup)
            knowledge: Dict mapping action_id to success_rate
            iteration: Current iteration number (for exploration tracking)
            
        Returns:
            Single best Action or None if no valid action
        """
        if not diagnoses:
            return None
        
        # Build pattern map for O(1) lookup
        pattern_map = {p.id: p for p in patterns}
        
        # Collect all suggested actions
        all_actions: List[Tuple[Action, float]] = []
        
        for diag in diagnoses:
            pattern = pattern_map.get(diag.pattern_id)
            if not pattern:
                continue
            
            for action_def in pattern.actions:
                # Exploration bonus for unknown actions (encourages trying new things)
                exploration_bonus = 0.1 if action_def.id not in knowledge else 0
                
                # Score = confidence * 0.4 + success_rate * 0.4 + severity * 0.2 + exploration_bonus
                score = (
                    diag.confidence * 0.4 +
                    knowledge.get(action_def.id, 0.5) * 0.4 +
                    diag.severity * 0.2 +
                    exploration_bonus
                )
                
                all_actions.append((Action.from_def(action_def, diag.pattern_id), score))
        
        if not all_actions:
            return None
        
        # Detect conflicts and choose highest-ranked
        top_action = DecisionEngine._resolve_conflicts(all_actions)
        return top_action

    @staticmethod
    def _resolve_conflicts(actions: List[Tuple[Action, float]]) -> Optional[Action]:
        """Resolve conflicting actions on same parameter by choosing highest score.
        
        Args:
            actions: List of (action, score) tuples
            
        Returns:
            Highest scoring action after conflict resolution
        """
        # Group by parameter
        grouped = {}
        
        for action, score in actions:
            key = action.parameter
            if key not in grouped or grouped[key][1] < score:
                grouped[key] = (action, score)
        
        if not grouped:
            return None
        
        # Return highest score action across all parameters
        return max(grouped.values(), key=lambda x: x[1])[0]
