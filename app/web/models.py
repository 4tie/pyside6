"""Pydantic models for the Next.js-facing web API."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    strategy: str
    timeframe: str
    timerange: Optional[str] = None
    pairs: Optional[List[str]] = None
    max_open_trades: Optional[int] = None
    dry_run_wallet: Optional[float] = None


class BacktestConfigRequest(BaseModel):
    strategy: Optional[str] = None
    timeframe: Optional[str] = None
    pairs: List[str] = Field(default_factory=list)
    timerange: Optional[str] = None
    max_open_trades: Optional[int] = None
    dry_run_wallet: Optional[float] = None


class BacktestConfigResponse(BacktestConfigRequest):
    pass


class DownloadDataRequest(BaseModel):
    timeframe: str
    timerange: Optional[str] = None
    pairs: List[str] = Field(default_factory=list)
    prepend: bool = False
    erase: bool = False


class DownloadDataResponse(BaseModel):
    success: bool
    message: str
    task_id: Optional[str] = None


class FavoritesRequest(BaseModel):
    favorites: List[str]


class FavoritesResponse(BaseModel):
    favorites: List[str]


class OptimizeRequest(BaseModel):
    strategy: str
    timeframe: str
    epochs: int
    timerange: Optional[str] = None
    pairs: List[str] = Field(default_factory=list)
    spaces: List[str] = Field(default_factory=list)
    hyperopt_loss: Optional[str] = None


class PairsResponse(BaseModel):
    categories: Dict[str, List[str]]
    all_pairs: List[str]
    favorites: List[str]


class DataAvailabilityResponse(BaseModel):
    available: bool
    available_pairs: List[str]
    missing_pairs: List[str]
    message: str


class RunResponse(BaseModel):
    run_id: str
    strategy: str
    timeframe: str = ""
    pairs: List[str] = Field(default_factory=list)
    timerange: str = ""
    backtest_start: str = ""
    backtest_end: str = ""
    saved_at: str = ""
    profit_total_pct: float = 0.0
    profit_total_abs: float = 0.0
    starting_balance: float = 0.0
    final_balance: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_abs: float = 0.0
    trades_count: int = 0
    wins: int = 0
    losses: int = 0
    win_rate_pct: float = 0.0
    sharpe: Optional[float] = None
    sortino: Optional[float] = None
    calmar: Optional[float] = None
    profit_factor: float = 0.0
    expectancy: float = 0.0
    run_dir: str = ""


class RunDetailResponse(RunResponse):
    trades: List[Dict[str, Any]] = Field(default_factory=list)
    params: Dict[str, Any] = Field(default_factory=dict)


class StrategyResponse(BaseModel):
    name: str
    config: Optional[Dict[str, Any]] = None


class DashboardMetrics(BaseModel):
    total_runs: int = 0
    total_strategies: int = 0
    best_profit_pct: float = 0.0
    best_win_rate_pct: float = 0.0
    min_drawdown_pct: float = 0.0
    total_trades: int = 0
    latest_run_date: str = ""


class DashboardSummary(BaseModel):
    metrics: DashboardMetrics = Field(default_factory=DashboardMetrics)
    recent_runs: List[RunResponse] = Field(default_factory=list)
    strategies: List[str] = Field(default_factory=list)


class SettingsResponse(BaseModel):
    user_data_path: str = ""
    venv_path: str = ""
    python_executable: str = ""
    freqtrade_executable: str = ""
    use_module_execution: bool = True
    backtest_preferences: Dict[str, Any] = Field(default_factory=dict)
    optimize_preferences: Dict[str, Any] = Field(default_factory=dict)
    download_preferences: Dict[str, Any] = Field(default_factory=dict)
    optimizer_preferences: Dict[str, Any] = Field(default_factory=dict)


class SettingsUpdate(BaseModel):
    user_data_path: Optional[str] = None
    venv_path: Optional[str] = None
    python_executable: Optional[str] = None
    freqtrade_executable: Optional[str] = None
    use_module_execution: Optional[bool] = None
    backtest_preferences: Optional[Dict[str, Any]] = None
    optimize_preferences: Optional[Dict[str, Any]] = None
    download_preferences: Optional[Dict[str, Any]] = None
    optimizer_preferences: Optional[Dict[str, Any]] = None
