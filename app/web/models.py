"""Pydantic models for API request and response validation.

Defines request models for incoming API calls and response models for
outgoing data, ensuring type safety and validation.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ============================================================================
# Request Models
# ============================================================================

class BacktestRequest(BaseModel):
    """Request model for starting a new backtest."""
    strategy: str = Field(..., description="Strategy name")
    timeframe: str = Field(..., description="Timeframe (e.g., '5m', '1h')")
    timerange: Optional[str] = Field(None, description="Date range (e.g., '20240101-20241231')")
    pairs: Optional[List[str]] = Field(None, description="List of trading pairs")
    max_open_trades: Optional[int] = Field(None, description="Maximum open trades")
    dry_run_wallet: Optional[float] = Field(None, description="Starting wallet balance")


class LoopStartRequest(BaseModel):
    """Request model for starting the optimization loop."""
    strategy: str = Field(..., description="Strategy name")
    max_iterations: int = Field(10, description="Maximum number of iterations")
    target_profit_pct: float = Field(5.0, description="Target profit percentage")
    target_win_rate: float = Field(55.0, description="Target win rate percentage")
    target_max_drawdown: float = Field(20.0, description="Target max drawdown percentage")
    target_min_trades: int = Field(30, description="Minimum trades required")
    validation_mode: str = Field("full", description="Validation mode: 'full' or 'quick'")
    timerange: Optional[str] = Field(None, description="Date range for backtests")
    pairs: Optional[str] = Field(None, description="Comma-separated pairs")


class SettingsUpdate(BaseModel):
    """Request model for updating application settings."""
    # Include relevant settings fields from AppSettings
    # This will be expanded based on actual settings structure
    user_data_path: Optional[str] = None
    venv_path: Optional[str] = None
    python_executable: Optional[str] = None
    freqtrade_executable: Optional[str] = None


# ============================================================================
# Response Models
# ============================================================================

class RunResponse(BaseModel):
    """Response model for a single backtest run."""
    run_id: str
    strategy: str
    timeframe: str
    pairs: List[str]
    timerange: str
    backtest_start: str
    backtest_end: str
    saved_at: str
    profit_total_pct: float
    profit_total_abs: float
    starting_balance: float
    final_balance: float
    max_drawdown_pct: float
    max_drawdown_abs: float
    trades_count: int
    wins: int
    losses: int
    win_rate_pct: float
    sharpe: Optional[float]
    sortino: Optional[float]
    calmar: Optional[float]
    profit_factor: float
    expectancy: float
    run_dir: str


class RunDetailResponse(RunResponse):
    """Extended response model with full run details."""
    trades: List[Dict[str, Any]]
    params: Dict[str, Any]


class StrategyResponse(BaseModel):
    """Response model for a strategy."""
    name: str
    config: Optional[Dict[str, Any]] = None


class DiagnosisResponse(BaseModel):
    """Response model for diagnosis results."""
    run_id: str
    issues: List[Dict[str, Any]]
    suggestions: List[Dict[str, Any]]


class ComparisonResponse(BaseModel):
    """Response model for run comparison with detailed analysis."""
    run_a_id: str
    run_b_id: str

    # Basic metrics
    profit_diff: float
    winrate_diff: float
    drawdown_diff: float
    verdict: str

    # Multi-objective scores
    score_a: float = 0.0
    score_b: float = 0.0
    score_diff: float = 0.0
    score_pct_change: float = 0.0

    # Risk-adjusted metrics
    sharpe_diff: float = 0.0
    sortino_diff: float = 0.0
    calmar_diff: float = 0.0
    profit_factor_diff: float = 0.0

    # Trade quality
    trade_frequency_diff: float = 0.0
    avg_duration_diff: float = 0.0
    expectancy_diff: float = 0.0

    # Pattern detection
    patterns_a: List[str] = Field(default_factory=list)
    patterns_b: List[str] = Field(default_factory=list)
    patterns_diff: List[str] = Field(default_factory=list)

    # Confidence scoring
    confidence_score: float = 0.5
    confidence_reason: str = ""
    is_statistically_significant: bool = False

    # Detailed breakdown
    metric_scores: Dict[str, float] = Field(default_factory=dict)
    recommendations: List[str] = Field(default_factory=list)


class SettingsResponse(BaseModel):
    """Response model for application settings."""
    user_data_path: str
    venv_path: str
    python_executable: str
    freqtrade_executable: str
    use_module_execution: bool


class LoopStatusResponse(BaseModel):
    """Response model for loop status."""
    running: bool
    current_iteration: Optional[int] = None
    total_iterations: Optional[int] = None
    strategy: Optional[str] = None


class LoopIterationResponse(BaseModel):
    """Response model for a single loop iteration."""
    iteration: int
    run_id: str
    is_improvement: bool
    score: Optional[float] = None
    params_before: Dict[str, Any]
    params_after: Dict[str, Any]
    summary: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    service: str


# ============================================================================
# WebSocket Message Models
# ============================================================================

class WebSocketMessage(BaseModel):
    """Base model for WebSocket messages."""
    type: str
    data: Dict[str, Any]


class BacktestProgressMessage(BaseModel):
    """WebSocket message for backtest progress updates."""
    type: str = "progress"
    data: Dict[str, Any] = Field(default_factory=lambda: {
        "progress_pct": 0.0,
        "current_step": "",
        "message": ""
    })


class BacktestCompleteMessage(BaseModel):
    """WebSocket message for backtest completion."""
    type: str = "complete"
    data: Dict[str, Any] = Field(default_factory=lambda: {
        "run_id": "",
        "success": True
    })


class BacktestErrorMessage(BaseModel):
    """WebSocket message for backtest errors."""
    type: str = "error"
    data: Dict[str, Any] = Field(default_factory=lambda: {
        "error": "",
        "details": ""
    })


class LoopIterationStartMessage(BaseModel):
    """WebSocket message for loop iteration start."""
    type: str = "iteration_start"
    data: Dict[str, Any] = Field(default_factory=lambda: {
        "iteration": 0,
        "params": {}
    })


class LoopGateResultMessage(BaseModel):
    """WebSocket message for loop gate results."""
    type: str = "gate_result"
    data: Dict[str, Any] = Field(default_factory=lambda: {
        "gate_name": "",
        "passed": False,
        "metrics": {}
    })


class LoopDiagnosisMessage(BaseModel):
    """WebSocket message for loop diagnosis."""
    type: str = "diagnosis"
    data: Dict[str, Any] = Field(default_factory=lambda: {
        "issues": [],
        "suggestions": []
    })


class LoopSuggestionMessage(BaseModel):
    """WebSocket message for loop suggestions."""
    type: str = "suggestion"
    data: Dict[str, Any] = Field(default_factory=lambda: {
        "parameter": "",
        "proposed_value": None,
        "reason": ""
    })


class LoopCompleteMessage(BaseModel):
    """WebSocket message for loop completion."""
    type: str = "complete"
    data: Dict[str, Any] = Field(default_factory=lambda: {
        "total_iterations": 0,
        "best_run_id": "",
        "stop_reason": ""
    })
