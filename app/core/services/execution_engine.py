"""
execution_engine.py — Deterministic execution engine for parameter changes.

Part of the 4-layer diagnostic architecture.
Applies actions to parameters with bounds checking.
"""
from __future__ import annotations

from typing import Any, Dict

from app.core.models.pattern_models import Action

# Safe default values for common parameters
PARAM_DEFAULTS = {
    "stoploss": -0.1,
    "minimal_roi": {},
    "trailing_stop": False,
    "trailing_stop_positive_offset": 0.0,
    "trailing_stop_positive": 0.0,
    "max_open_trades": 5,
    "position_adjustment_enable": False,
    "amend_last_stake_amount": False,
}


class ExecutionEngine:
    """Deterministic execution engine.
    
    Applies actions to parameters with bounds checking.
    """

    @staticmethod
    def apply(action: Action, current_params: dict) -> dict:
        """Apply an action to current parameters.
        
        Deterministic: same inputs always produce same outputs.
        
        Args:
            action: The action to apply
            current_params: Current parameter values
            
        Returns:
            New parameters with action applied
            
        Raises:
            Exception: If parameter not in PARAM_DEFAULTS (prevents silent errors)
        """
        new_params = current_params.copy()
        param = action.parameter
        
        # Safe parameter access with explicit defaults
        if param not in PARAM_DEFAULTS:
            raise Exception(f"Unknown parameter: {param}")
        
        current = current_params.get(param, PARAM_DEFAULTS[param])
        
        if action.type == "scale":
            new_value = current * action.factor
            # Apply bounds (enforce sorted min/max)
            if action.bounds:
                min_val, max_val = sorted(action.bounds)
                new_value = max(min_val, min(max_val, new_value))
            new_params[param] = new_value
        
        elif action.type == "add":
            new_value = current + action.delta
            if action.bounds:
                min_val, max_val = sorted(action.bounds)
                new_value = max(min_val, min(max_val, new_value))
            new_params[param] = new_value
        
        elif action.type == "set":
            new_params[param] = action.value
        
        elif action.type == "toggle":
            new_params[param] = not current_params.get(param, PARAM_DEFAULTS[param])
        
        return new_params
    
    @staticmethod
    def get_param_default(param: str) -> Any:
        """Get default value for a parameter."""
        return PARAM_DEFAULTS.get(param)
    
    @staticmethod
    def is_known_param(param: str) -> bool:
        """Check if parameter is known."""
        return param in PARAM_DEFAULTS
