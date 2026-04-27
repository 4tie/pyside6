"""
Pydantic v2 data models for the Strategy Optimizer feature.

Defines enums and models used across the optimizer subsystem:
- Session and trial lifecycle enums (SessionStatus, TrialStatus)
- Parameter type enum (ParamType)
- Parameter definition and strategy parameter models (ParamDef, StrategyParams)
- Trial metrics and record models (TrialMetrics, TrialRecord)
- Session configuration and session models (SessionConfig, OptimizerSession)
- Best pointer model (BestPointer)
- Optimizer UI preferences (OptimizerPreferences)
- Export result model (ExportResult)
- Selected-trial diff/apply models (TrialParamChange, TrialDiff, ApplyTrialResult)

Architecture boundary: NO PySide6 imports in this module.
"""

import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.utils.app_logger import get_logger

_log = get_logger("models.optimizer")


class SessionStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    STOPPED   = "stopped"
    COMPLETED = "completed"


class TrialStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED  = "failed"


class ParamType(str, Enum):
    INT         = "int"
    DECIMAL     = "decimal"
    CATEGORICAL = "categorical"
    BOOLEAN     = "boolean"


class ParamDef(BaseModel):
    """One parameter definition extracted from a strategy .py file."""

    name: str
    param_type: ParamType
    default: Any
    low: Optional[float] = None       # None for categorical/boolean
    high: Optional[float] = None
    categories: Optional[List[Any]] = None  # for CategoricalParameter
    space: str = "buy"                # "buy" | "sell" | "roi" | "stoploss" | "trailing"
    enabled: bool = True              # user can disable to hold at default


class StrategyParams(BaseModel):
    """Full parameter metadata extracted from a strategy .py file."""

    strategy_class: str
    timeframe: str = "5m"
    minimal_roi: Dict[str, float] = Field(default_factory=dict)
    stoploss: float = -0.10
    trailing_stop: bool = False
    trailing_stop_positive: Optional[float] = None
    trailing_stop_positive_offset: Optional[float] = None
    buy_params: Dict[str, ParamDef] = Field(default_factory=dict)
    sell_params: Dict[str, ParamDef] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyParams":
        return cls.model_validate(data)


class TrialMetrics(BaseModel):
    """Extracted backtest metrics for one trial."""

    total_profit_pct: float = 0.0
    total_profit_abs: float = 0.0
    win_rate: float = 0.0
    max_drawdown_pct: float = 0.0
    total_trades: int = 0
    profit_factor: float = 0.0
    sharpe_ratio: Optional[float] = None
    best_pair: str = ""
    worst_pair: str = ""
    final_balance: float = 0.0
    best_trade_profit_pct: float = 0.0
    worst_trade_profit_pct: float = 0.0


class TrialRecord(BaseModel):
    """Persisted artefact for one trial."""

    session_id: str
    trial_number: int
    status: TrialStatus = TrialStatus.PENDING
    candidate_params: Dict[str, Any] = Field(default_factory=dict)
    metrics: Optional[TrialMetrics] = None
    score: Optional[float] = None
    score_metric: str = "total_profit_pct"
    score_mode: str = "single_metric"
    score_breakdown: Dict[str, float] = Field(default_factory=dict)
    log_excerpt: str = ""
    is_best: bool = False


class BestPointer(BaseModel):
    """Lightweight pointer to the current Accepted_Best trial."""

    session_id: str
    trial_number: int
    score: float


class SessionConfig(BaseModel):
    """Configuration snapshot saved at session start."""

    strategy_name: str
    strategy_class: str
    pairs: List[str] = Field(default_factory=list)
    timeframe: str = "5m"
    timerange: Optional[str] = None
    dry_run_wallet: float = 80.0
    max_open_trades: int = 2
    config_file_path: str = ""
    total_trials: int = 50
    score_metric: str = "total_profit_pct"
    score_mode: str = "composite"
    target_min_trades: int = 100
    target_profit_pct: float = 50.0
    max_drawdown_limit: float = 25.0
    target_romad: float = 2.0
    param_defs: List[ParamDef] = Field(default_factory=list)


class OptimizerSession(BaseModel):
    """One complete optimizer session."""

    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: SessionStatus = SessionStatus.PENDING
    config: SessionConfig
    trials_completed: int = 0
    best_pointer: Optional[BestPointer] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class OptimizerPreferences(BaseModel):
    """Persisted optimizer UI preferences (added to AppSettings)."""

    last_strategy: str = ""
    default_timeframe: str = "5m"
    default_timerange: str = ""
    default_pairs: str = ""
    last_timerange_preset: str = "30d"
    dry_run_wallet: float = 80.0
    max_open_trades: int = 2
    total_trials: int = 50
    score_metric: str = "composite"
    score_mode: str = "composite"
    target_min_trades: int = 100
    target_profit_pct: float = 50.0
    max_drawdown_limit: float = 25.0
    target_romad: float = 2.0

    @field_validator("dry_run_wallet")
    @classmethod
    def validate_dry_run_wallet(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(
                f"dry_run_wallet must be greater than 0, got {v}"
            )
        return v

    @field_validator("max_open_trades")
    @classmethod
    def validate_max_open_trades(cls, v: int) -> int:
        if v < 1:
            raise ValueError(
                f"max_open_trades must be at least 1, got {v}"
            )
        return v


class OptimizerConfigUpdate(BaseModel):
    """Partial update payload for PUT /api/optimizer/config.

    All fields are optional — only provided fields are updated.
    Unknown fields are rejected with HTTP 422 via extra='forbid'.
    """

    model_config = ConfigDict(extra="forbid")

    last_strategy: str | None = None
    default_timeframe: str | None = None
    last_timerange_preset: str | None = None
    default_timerange: str | None = None
    default_pairs: str | None = None
    dry_run_wallet: float | None = None
    max_open_trades: int | None = None


class OptimizerConfigResponse(BaseModel):
    """Full state returned by GET and PUT /api/optimizer/config."""

    last_strategy: str
    default_timeframe: str
    last_timerange_preset: str
    default_timerange: str
    default_pairs: str
    pairs_list: list[str]
    dry_run_wallet: float
    max_open_trades: int


class ExportResult(BaseModel):
    """Result of exporting the best trial parameters to the live strategy JSON."""

    success: bool
    live_json_path: str = ""
    backup_path: str = ""
    error_message: str = ""


class TrialParamChange(BaseModel):
    """One parameter value difference between live params and a selected trial."""

    key: str
    current_value: Any = None
    trial_value: Any = None


class TrialDiff(BaseModel):
    """Diff preview for applying a selected optimizer trial."""

    success: bool
    param_changes: List[TrialParamChange] = Field(default_factory=list)
    strategy_diff: str = ""
    live_strategy_path: str = ""
    trial_strategy_path: str = ""
    live_json_path: str = ""
    trial_json_path: str = ""
    error_message: str = ""


class ApplyTrialResult(BaseModel):
    """Result of applying selected trial artifacts to strategy files."""

    success: bool
    strategy_py_path: str = ""
    strategy_json_path: str = ""
    backup_paths: List[str] = Field(default_factory=list)
    error_message: str = ""
