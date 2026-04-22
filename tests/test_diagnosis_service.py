"""test_diagnosis_service.py — Unit tests for DiagnosisService.

Tests each of the 5 diagnostic rules in isolation and in combination.
"""
import pytest

from app.core.backtests.results_models import BacktestSummary, PairAnalysis, PairMetrics
from app.core.services.diagnosis_service import DiagnosisService


@pytest.fixture
def baseline_summary() -> BacktestSummary:
    """Create a baseline BacktestSummary that fires no rules."""
    return BacktestSummary(
        strategy="TestStrategy",
        timeframe="5m",
        total_trades=100,
        wins=50,
        losses=50,
        draws=0,
        win_rate=50.0,  # >= 40
        avg_profit=0.5,  # > 0
        total_profit=50.0,
        total_profit_abs=50.0,
        sharpe_ratio=1.0,
        sortino_ratio=1.0,
        calmar_ratio=1.0,
        max_drawdown=10.0,  # <= 15
        max_drawdown_abs=10.0,
        trade_duration_avg=60,
    )


@pytest.fixture
def baseline_analysis() -> PairAnalysis:
    """Create a baseline PairAnalysis with no concentration."""
    return PairAnalysis(
        pair_metrics=[
            PairMetrics(
                pair="BTC/USDT",
                total_profit_pct=20.0,
                win_rate=50.0,
                trade_count=50,
                max_drawdown_pct=5.0,
                profit_share=0.4,
            ),
            PairMetrics(
                pair="ETH/USDT",
                total_profit_pct=30.0,
                win_rate=55.0,
                trade_count=50,
                max_drawdown_pct=6.0,
                profit_share=0.6,
            ),
        ],
        best_pairs=[],
        worst_pairs=[],
        dominance_flags=[],
    )


class TestDiagnosisServiceRules:
    """Test each diagnostic rule fires/doesn't fire correctly."""

    def test_entry_too_aggressive_fires_below_threshold(self, baseline_summary, baseline_analysis):
        """Rule 1: entry_too_aggressive fires when win_rate < 40."""
        summary = baseline_summary
        summary.win_rate = 39.9
        suggestions = DiagnosisService.diagnose(baseline_analysis, summary)
        rule_ids = [s.rule_id for s in suggestions]
        assert "entry_too_aggressive" in rule_ids

    def test_entry_too_aggressive_not_fires_above_threshold(self, baseline_summary, baseline_analysis):
        """Rule 1: entry_too_aggressive does NOT fire when win_rate >= 40."""
        summary = baseline_summary
        summary.win_rate = 40.0
        suggestions = DiagnosisService.diagnose(baseline_analysis, summary)
        rule_ids = [s.rule_id for s in suggestions]
        assert "entry_too_aggressive" not in rule_ids

    def test_stoploss_too_loose_fires_above_threshold(self, baseline_summary, baseline_analysis):
        """Rule 2: stoploss_too_loose fires when max_drawdown > 15."""
        summary = baseline_summary
        summary.max_drawdown = 15.1
        suggestions = DiagnosisService.diagnose(baseline_analysis, summary)
        rule_ids = [s.rule_id for s in suggestions]
        assert "stoploss_too_loose" in rule_ids

    def test_stoploss_too_loose_not_fires_below_threshold(self, baseline_summary, baseline_analysis):
        """Rule 2: stoploss_too_loose does NOT fire when max_drawdown <= 15."""
        summary = baseline_summary
        summary.max_drawdown = 15.0
        suggestions = DiagnosisService.diagnose(baseline_analysis, summary)
        rule_ids = [s.rule_id for s in suggestions]
        assert "stoploss_too_loose" not in rule_ids

    def test_overfitting_risk_fires_above_threshold(self, baseline_summary, baseline_analysis):
        """Rule 3: overfitting_risk fires when max profit_share > 0.50."""
        analysis = baseline_analysis
        # Add a dominant pair
        analysis.pair_metrics.append(
            PairMetrics(
                pair="ADA/USDT",
                total_profit_pct=100.0,
                win_rate=60.0,
                trade_count=30,
                max_drawdown_pct=3.0,
                profit_share=0.51,
            )
        )
        suggestions = DiagnosisService.diagnose(analysis, baseline_summary)
        rule_ids = [s.rule_id for s in suggestions]
        assert "overfitting_risk" in rule_ids

    def test_overfitting_risk_not_fires_below_threshold(self, baseline_summary):
        """Rule 3: overfitting_risk does NOT fire when max profit_share <= 0.50."""
        # Create analysis with profit_share at boundary (exactly 0.50)
        analysis = PairAnalysis(
            pair_metrics=[
                PairMetrics(
                    pair="BTC/USDT",
                    total_profit_pct=20.0,
                    win_rate=50.0,
                    trade_count=50,
                    max_drawdown_pct=5.0,
                    profit_share=0.50,  # Exactly 0.50 should NOT fire
                ),
                PairMetrics(
                    pair="ETH/USDT",
                    total_profit_pct=20.0,
                    win_rate=55.0,
                    trade_count=50,
                    max_drawdown_pct=6.0,
                    profit_share=0.50,
                ),
            ],
            best_pairs=[],
            worst_pairs=[],
            dominance_flags=[],
        )
        suggestions = DiagnosisService.diagnose(analysis, baseline_summary)
        rule_ids = [s.rule_id for s in suggestions]
        assert "overfitting_risk" not in rule_ids

    def test_insufficient_trades_fires_below_threshold(self, baseline_summary, baseline_analysis):
        """Rule 4: insufficient_trades fires when total_trades < 50."""
        summary = baseline_summary
        summary.total_trades = 49
        suggestions = DiagnosisService.diagnose(baseline_analysis, summary)
        rule_ids = [s.rule_id for s in suggestions]
        assert "insufficient_trades" in rule_ids

    def test_insufficient_trades_not_fires_above_threshold(self, baseline_summary, baseline_analysis):
        """Rule 4: insufficient_trades does NOT fire when total_trades >= 50."""
        summary = baseline_summary
        summary.total_trades = 50
        suggestions = DiagnosisService.diagnose(baseline_analysis, summary)
        rule_ids = [s.rule_id for s in suggestions]
        assert "insufficient_trades" not in rule_ids

    def test_negative_expectancy_fires_below_zero(self, baseline_summary, baseline_analysis):
        """Rule 5: negative_expectancy fires when avg_profit < 0."""
        summary = baseline_summary
        summary.avg_profit = -0.1
        suggestions = DiagnosisService.diagnose(baseline_analysis, summary)
        rule_ids = [s.rule_id for s in suggestions]
        assert "negative_expectancy" in rule_ids

    def test_negative_expectancy_not_fires_above_zero(self, baseline_summary, baseline_analysis):
        """Rule 5: negative_expectancy does NOT fire when avg_profit >= 0."""
        summary = baseline_summary
        summary.avg_profit = 0.0
        suggestions = DiagnosisService.diagnose(baseline_analysis, summary)
        rule_ids = [s.rule_id for s in suggestions]
        assert "negative_expectancy" not in rule_ids

    def test_multiple_rules_fire_simultaneously(self, baseline_summary):
        """Multiple rules can fire at the same time (independent)."""
        summary = baseline_summary
        summary.win_rate = 39.9  # Triggers entry_too_aggressive
        summary.max_drawdown = 15.1  # Triggers stoploss_too_loose
        summary.total_trades = 40  # Triggers insufficient_trades
        summary.avg_profit = 0.5  # Still positive, no negative_expectancy

        # Create analysis with NO concentration (profit_share at 0.50 boundary)
        analysis = PairAnalysis(
            pair_metrics=[
                PairMetrics(
                    pair="BTC/USDT",
                    total_profit_pct=20.0,
                    win_rate=39.9,
                    trade_count=20,
                    max_drawdown_pct=15.1,
                    profit_share=0.50,
                ),
                PairMetrics(
                    pair="ETH/USDT",
                    total_profit_pct=20.0,
                    win_rate=39.9,
                    trade_count=20,
                    max_drawdown_pct=15.1,
                    profit_share=0.50,
                ),
            ],
            best_pairs=[],
            worst_pairs=[],
            dominance_flags=[],
        )

        suggestions = DiagnosisService.diagnose(analysis, summary)
        rule_ids = [s.rule_id for s in suggestions]

        assert "entry_too_aggressive" in rule_ids
        assert "stoploss_too_loose" in rule_ids
        assert "insufficient_trades" in rule_ids
        assert len(suggestions) == 3

    def test_no_rules_fire_returns_empty_list(self, baseline_summary):
        """Empty list when all conditions are healthy."""
        # Create a clean analysis with no concentration
        analysis = PairAnalysis(
            pair_metrics=[
                PairMetrics(
                    pair="BTC/USDT",
                    total_profit_pct=20.0,
                    win_rate=50.0,
                    trade_count=50,
                    max_drawdown_pct=5.0,
                    profit_share=0.50,
                ),
                PairMetrics(
                    pair="ETH/USDT",
                    total_profit_pct=30.0,
                    win_rate=55.0,
                    trade_count=50,
                    max_drawdown_pct=6.0,
                    profit_share=0.50,
                ),
            ],
            best_pairs=[],
            worst_pairs=[],
            dominance_flags=[],
        )
        suggestions = DiagnosisService.diagnose(analysis, baseline_summary)
        assert suggestions == []

    def test_all_rules_fire_simultaneously(self, baseline_analysis):
        """All 5 rules can fire together."""
        summary = BacktestSummary(
            strategy="BadStrategy",
            timeframe="5m",
            total_trades=30,  # < 50 → insufficient_trades
            wins=5,
            losses=25,
            draws=0,
            win_rate=16.7,  # < 40 → entry_too_aggressive
            avg_profit=-0.5,  # < 0 → negative_expectancy
            total_profit=-15.0,
            total_profit_abs=15.0,
            sharpe_ratio=None,
            sortino_ratio=None,
            calmar_ratio=None,
            max_drawdown=20.0,  # > 15 → stoploss_too_loose
            max_drawdown_abs=20.0,
            trade_duration_avg=45,
        )

        # Add dominant pair for overfitting_risk
        analysis = PairAnalysis(
            pair_metrics=[
                PairMetrics(
                    pair="BTC/USDT",
                    total_profit_pct=-15.0,
                    win_rate=16.7,
                    trade_count=30,
                    max_drawdown_pct=20.0,
                    profit_share=1.0,  # > 0.50 → overfitting_risk
                ),
            ],
            best_pairs=[],
            worst_pairs=[],
            dominance_flags=["profit_concentration"],
        )

        suggestions = DiagnosisService.diagnose(analysis, summary)
        rule_ids = [s.rule_id for s in suggestions]

        assert len(suggestions) == 5
        assert "entry_too_aggressive" in rule_ids
        assert "stoploss_too_loose" in rule_ids
        assert "overfitting_risk" in rule_ids
        assert "insufficient_trades" in rule_ids
        assert "negative_expectancy" in rule_ids

    def test_suggestion_has_required_fields(self, baseline_summary, baseline_analysis):
        """Each DiagnosisSuggestion has rule_id, message, and severity."""
        baseline_summary.win_rate = 39.0
        suggestions = DiagnosisService.diagnose(baseline_analysis, baseline_summary)

        for suggestion in suggestions:
            assert hasattr(suggestion, "rule_id")
            assert hasattr(suggestion, "message")
            assert hasattr(suggestion, "severity")
            assert suggestion.rule_id != ""
            assert suggestion.message != ""
            assert suggestion.severity in ["critical", "warning"]
