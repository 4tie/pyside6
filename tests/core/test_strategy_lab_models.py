"""
test_strategy_lab_models.py — Unit tests for StrategyLabPreferences,
extended LoopConfig, and extended LoopIteration model fields.
"""
import json
import pytest

from app.core.models.settings_models import AppSettings, StrategyLabPreferences
from app.core.models.loop_models import LoopConfig, LoopIteration


# ---------------------------------------------------------------------------
# StrategyLabPreferences
# ---------------------------------------------------------------------------

class TestStrategyLabPreferences:
    """Tests for StrategyLabPreferences Pydantic model."""

    def test_default_values(self):
        prefs = StrategyLabPreferences()
        assert prefs.strategy == ""
        assert prefs.max_iterations == 10
        assert prefs.target_profit_pct == 5.0
        assert prefs.target_win_rate == 55.0
        assert prefs.target_max_drawdown == 20.0
        assert prefs.target_min_trades == 30
        assert prefs.stop_on_first_profitable is True
        assert prefs.date_from == ""
        assert prefs.date_to == ""
        assert prefs.timerange == ""
        assert prefs.pairs == ""
        assert prefs.oos_split_pct == 20.0
        assert prefs.walk_forward_folds == 5
        assert prefs.stress_fee_multiplier == 2.0
        assert prefs.stress_slippage_pct == 0.1
        assert prefs.stress_profit_target_pct == 50.0
        assert prefs.consistency_threshold_pct == 30.0
        assert prefs.validation_mode == "full"
        assert prefs.iteration_mode == "rule_based"
        assert prefs.hyperopt_epochs == 200
        assert prefs.hyperopt_spaces == []
        assert prefs.hyperopt_loss_function == "SharpeHyperOptLoss"
        assert prefs.ai_advisor_enabled is False

    def test_round_trip_json(self):
        """StrategyLabPreferences must survive JSON serialisation round-trip."""
        prefs = StrategyLabPreferences(
            strategy="MyStrategy",
            max_iterations=20,
            target_profit_pct=10.0,
            validation_mode="quick",
            iteration_mode="hyperopt",
            hyperopt_epochs=500,
            hyperopt_spaces=["buy", "sell", "roi"],
            hyperopt_loss_function="CalmarHyperOptLoss",
            ai_advisor_enabled=True,
            pairs="BTC/USDT,ETH/USDT",
            date_from="20240101",
            date_to="20241231",
            timerange="20240101-20241231",
        )
        serialised = prefs.model_dump_json()
        restored = StrategyLabPreferences.model_validate_json(serialised)
        assert restored == prefs

    def test_app_settings_contains_strategy_lab(self):
        """AppSettings must expose strategy_lab field with correct type."""
        settings = AppSettings()
        assert isinstance(settings.strategy_lab, StrategyLabPreferences)

    def test_app_settings_round_trip_json(self):
        """AppSettings with strategy_lab must survive JSON round-trip."""
        settings = AppSettings()
        settings.strategy_lab.strategy = "TestStrategy"
        settings.strategy_lab.hyperopt_spaces = ["buy", "sell"]
        data = json.loads(settings.model_dump_json())
        restored = AppSettings.model_validate(data)
        assert restored.strategy_lab.strategy == "TestStrategy"
        assert restored.strategy_lab.hyperopt_spaces == ["buy", "sell"]


# ---------------------------------------------------------------------------
# LoopConfig extended fields
# ---------------------------------------------------------------------------

class TestLoopConfigExtendedFields:
    """Tests for new LoopConfig fields."""

    def test_default_timeframe(self):
        """LoopConfig must default timeframe to '5m' for backward compatibility."""
        config = LoopConfig(strategy="MyStrategy")
        assert config.timeframe == "5m"

    def test_custom_timeframe(self):
        """LoopConfig must accept custom timeframe values."""
        config = LoopConfig(strategy="MyStrategy", timeframe="1h")
        assert config.timeframe == "1h"

    def test_default_extended_fields(self):
        config = LoopConfig(strategy="MyStrategy")
        assert config.iteration_mode == "rule_based"
        assert config.hyperopt_epochs == 200
        assert config.hyperopt_spaces == []
        assert config.hyperopt_loss_function == "SharpeHyperOptLoss"
        assert config.pairs == []
        assert config.ai_advisor_enabled is False

    def test_custom_extended_fields(self):
        config = LoopConfig(
            strategy="MyStrategy",
            iteration_mode="hyperopt",
            hyperopt_epochs=300,
            hyperopt_spaces=["buy", "sell"],
            hyperopt_loss_function="CalmarHyperOptLoss",
            pairs=["BTC/USDT", "ETH/USDT"],
            ai_advisor_enabled=True,
        )
        assert config.iteration_mode == "hyperopt"
        assert config.hyperopt_epochs == 300
        assert config.hyperopt_spaces == ["buy", "sell"]
        assert config.hyperopt_loss_function == "CalmarHyperOptLoss"
        assert config.pairs == ["BTC/USDT", "ETH/USDT"]
        assert config.ai_advisor_enabled is True


# ---------------------------------------------------------------------------
# LoopIteration extended fields
# ---------------------------------------------------------------------------

class TestLoopIterationExtendedFields:
    """Tests for new LoopIteration fields."""

    def test_default_extended_fields(self):
        iteration = LoopIteration(
            iteration_number=1,
            params_before={},
            params_after={},
            changes_summary=[],
        )
        assert iteration.ai_suggested is False
        assert iteration.ai_suggestion_reason is None
        assert iteration.diagnosed_structural == []

    def test_ai_suggested_fields(self):
        iteration = LoopIteration(
            iteration_number=1,
            params_before={"stoploss": -0.10},
            params_after={"stoploss": -0.08},
            changes_summary=["stoploss: -0.10 → -0.08"],
            ai_suggested=True,
            ai_suggestion_reason="AI recommended tightening stoploss based on drawdown pattern",
        )
        assert iteration.ai_suggested is True
        assert "drawdown" in iteration.ai_suggestion_reason

    def test_diagnosed_structural_list(self):
        iteration = LoopIteration(
            iteration_number=1,
            params_before={},
            params_after={},
            changes_summary=[],
            diagnosed_structural=["losers_lasting_too_long", "exits_cutting_winners_early"],
        )
        assert len(iteration.diagnosed_structural) == 2
        assert "losers_lasting_too_long" in iteration.diagnosed_structural
