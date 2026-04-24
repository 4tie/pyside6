"""Pure mapper for transforming UI values to LoopConfig (NO logic)."""
from app.core.models.loop_models import LoopConfig

def ui_to_loop_config(
    strategy: str,
    ui_values: dict,
    timeframe: str,  # Pre-detected by service
) -> LoopConfig:
    """Transform UI widget values into LoopConfig model (pure mapping only).
    
    NOTE: No logic like timeframe detection - that belongs in service layer.
    """
    if not strategy:
        raise ValueError("Strategy required")
    
    return LoopConfig(
        strategy=strategy,
        timeframe=timeframe,
        max_iterations=ui_values.get("max_iterations", 10),
        target_profit_pct=ui_values.get("target_profit_pct", 10.0),
        target_win_rate=ui_values.get("target_win_rate", 40.0),
        target_max_drawdown=ui_values.get("target_max_drawdown", -20.0),
        target_min_trades=ui_values.get("target_min_trades", 100),
        stop_on_first_profitable=ui_values.get("stop_on_first_profitable", False),
        date_from=ui_values.get("date_from", ""),
        date_to=ui_values.get("date_to", ""),
        oos_split_pct=ui_values.get("oos_split_pct", 20),
        walk_forward_folds=ui_values.get("walk_forward_folds", 5),
        stress_fee_multiplier=ui_values.get("stress_fee_multiplier", 1.5),
        stress_slippage_pct=ui_values.get("stress_slippage_pct", 0.1),
        stress_profit_target_pct=ui_values.get("stress_profit_target_pct", 5.0),
        consistency_threshold_pct=ui_values.get("consistency_threshold_pct", 50),
        validation_mode=ui_values.get("validation_mode", "full"),
        iteration_mode=ui_values.get("iteration_mode", "rule_based"),
        hyperopt_epochs=ui_values.get("hyperopt_epochs", 100),
        hyperopt_spaces=ui_values.get("hyperopt_spaces", []),
        hyperopt_loss_function=ui_values.get("hyperopt_loss_function", "Sharpe HyperOptLoss"),
        pairs=ui_values.get("pairs", []),
        ai_advisor_enabled=ui_values.get("ai_advisor_enabled", False),
    )
