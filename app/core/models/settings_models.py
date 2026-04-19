from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Any
from pathlib import Path


class TerminalPreferences(BaseModel):
    """Terminal appearance preferences."""

    font_family: str = Field("Courier", description="Terminal font family")
    font_size: int = Field(10, description="Terminal font size")
    background_color: str = Field("#ffffff", description="Terminal background color (hex)")
    text_color: str = Field("#000000", description="Terminal text color (hex)")


class DownloadPreferences(BaseModel):
    """Download data user preferences."""

    default_timeframe: str = Field("5m", description="Default timeframe")
    default_timerange: str = Field("", description="Default timerange")
    default_pairs: str = Field("", description="Comma-separated pairs")
    paired_favorites: list[str] = Field(
        default_factory=lambda: ["BTC/USDT", "ETH/USDT", "ADA/USDT"],
        description="Favorite pairs",
    )
    last_timerange_preset: str = Field("30d", description="Last used timerange preset")


class BacktestPreferences(BaseModel):
    """Backtest-specific user preferences."""

    last_strategy: str = Field("", description="Last used strategy")
    default_timeframe: str = Field("5m", description="Default timeframe")
    default_timerange: str = Field("", description="Default timerange")
    default_pairs: str = Field("", description="Comma-separated pairs")
    paired_favorites: list[str] = Field(
        default_factory=lambda: ["BTC/USDT", "ETH/USDT", "ADA/USDT"],
        description="Common pairs for quick selection",
    )
    last_timerange_preset: str = Field("30d", description="Last used timerange preset")
    dry_run_wallet: float = Field(80.0, description="Dry run wallet balance")
    max_open_trades: int = Field(2, description="Max open trades")


class OptimizePreferences(BaseModel):
    """Hyperopt-specific user preferences."""

    last_strategy: str = Field("", description="Last used strategy")
    default_timeframe: str = Field("5m", description="Default timeframe")
    default_timerange: str = Field("", description="Default timerange")
    default_pairs: str = Field("", description="Comma-separated pairs")
    paired_favorites: list[str] = Field(
        default_factory=lambda: ["BTC/USDT", "ETH/USDT", "ADA/USDT"],
        description="Common pairs for quick selection",
    )
    last_timerange_preset: str = Field("30d", description="Last used timerange preset")
    epochs: int = Field(100, description="Hyperopt epochs")
    spaces: str = Field("all", description="Hyperopt spaces")
    hyperopt_loss: str = Field("SharpeHyperOptLoss", description="Hyperopt loss class")


class StrategyLabPreferences(BaseModel):
    """Strategy Lab (loop) user preferences."""

    strategy: str = Field("", description="Last used strategy")
    max_iterations: int = Field(10, description="Maximum number of backtest iterations")
    target_profit_pct: float = Field(5.0, description="Target total profit (%)")
    target_win_rate: float = Field(55.0, description="Target win rate (%)")
    target_max_drawdown: float = Field(20.0, description="Target max drawdown (%)")
    target_min_trades: int = Field(30, description="Minimum trades required")
    stop_on_first_profitable: bool = Field(True, description="Stop as soon as all targets are met")
    date_from: str = Field("", description="Start date for Strategy Lab backtests (YYYYMMDD)")
    date_to: str = Field("", description="End date for Strategy Lab backtests (YYYYMMDD)")
    timerange: str = Field("", description="Date range for backtests (YYYYMMDD-YYYYMMDD)")
    pairs: str = Field("", description="Comma-separated pairs for backtests")
    oos_split_pct: float = Field(20.0, description="Percentage of date range held out for OOS gate")
    walk_forward_folds: int = Field(5, description="Number of folds for walk-forward validation")
    stress_fee_multiplier: float = Field(2.0, description="Fee multiplier for stress-test gate")
    stress_slippage_pct: float = Field(0.1, description="Per-trade slippage for stress-test gate (%)")
    stress_profit_target_pct: float = Field(50.0, description="Min profit required in stress gate as % of main target")
    consistency_threshold_pct: float = Field(30.0, description="Max allowed CV of per-fold profit (%)")
    validation_mode: str = Field("full", description="Validation mode: 'full' or 'quick'")
    iteration_mode: str = Field("rule_based", description="Iteration mode: 'rule_based' or 'hyperopt'")
    hyperopt_epochs: int = Field(200, description="Hyperopt epochs per iteration (50–2000)")
    hyperopt_spaces: List[str] = Field(
        default_factory=list,
        description="Hyperopt spaces to search (buy, sell, roi, stoploss, trailing)",
    )
    hyperopt_loss_function: str = Field(
        "SharpeHyperOptLoss", description="Hyperopt loss function class name"
    )
    ai_advisor_enabled: bool = Field(False, description="Enable AI Advisor suggestion layer")


class AISettings(BaseModel):
    """AI panel configuration."""

    provider: str = Field("ollama", description="Active provider: 'ollama' or 'openrouter'")
    ollama_base_url: str = Field("http://localhost:11434", description="Ollama server base URL")
    openrouter_api_key: Optional[str] = Field(None, description="OpenRouter API key (active/first key, kept for backward compat)")
    openrouter_api_keys: list[str] = Field(default_factory=list, description="Multiple OpenRouter API keys for rotation")
    chat_model: str = Field("", description="Model for plain conversation")
    task_model: str = Field("", description="Model for tool-using task runs")
    routing_mode: str = Field("single_model", description="'single_model' or 'dual_model'")
    cloud_fallback_enabled: bool = Field(False, description="Reserved — no runtime effect in this version")
    openrouter_free_only: bool = Field(True, description="Filter OpenRouter to free models only")
    timeout_seconds: int = Field(60, description="HTTP request timeout in seconds")
    stream_enabled: bool = Field(True, description="Use streaming responses")
    tools_enabled: bool = Field(False, description="Enable tool calling")
    max_history_messages: int = Field(50, description="Max messages retained in history")
    max_tool_steps: int = Field(8, description="Max tool call iterations per run_task()")

    @field_validator("routing_mode")
    @classmethod
    def validate_routing_mode(cls, v: str) -> str:
        """Reject any routing_mode value other than the two supported modes."""
        if v not in ("single_model", "dual_model"):
            raise ValueError(f"routing_mode must be 'single_model' or 'dual_model', got: {v!r}")
        return v

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_fields(cls, data: Any) -> Any:
        """Migrate legacy fields and backfill openrouter_api_keys from single key if needed."""
        if isinstance(data, dict):
            data = dict(data)
            # Migrate old 'selected_model' -> 'chat_model'
            if "selected_model" in data and "chat_model" not in data:
                data["chat_model"] = data.pop("selected_model")
            # Migrate single key into keys list if list is empty
            single_key = data.get("openrouter_api_key")
            keys_list = data.get("openrouter_api_keys", [])
            if single_key and not keys_list:
                data["openrouter_api_keys"] = [single_key]
        return data


class AppSettings(BaseModel):
    """Main application settings for Freqtrade GUI."""

    venv_path: Optional[str] = Field(
        None, description="Path to Python virtual environment"
    )
    python_executable: Optional[str] = Field(
        None, description="Full path to Python interpreter"
    )
    freqtrade_executable: Optional[str] = Field(
        None, description="Full path to freqtrade executable"
    )
    user_data_path: Optional[str] = Field(
        None, description="Path to freqtrade user_data directory"
    )
    project_path: Optional[str] = Field(
        None, description="Path to freqtrade project root"
    )
    use_module_execution: bool = Field(
        True, description="Use python -m freqtrade instead of executable"
    )
    backtest_preferences: BacktestPreferences = Field(
        default_factory=BacktestPreferences, description="Backtest UI preferences"
    )
    optimize_preferences: OptimizePreferences = Field(
        default_factory=OptimizePreferences, description="Hyperopt UI preferences"
    )
    download_preferences: DownloadPreferences = Field(
        default_factory=DownloadPreferences, description="Download data UI preferences"
    )
    terminal_preferences: TerminalPreferences = Field(
        default_factory=TerminalPreferences, description="Terminal appearance preferences"
    )
    ai: AISettings = Field(
        default_factory=AISettings, description="AI panel configuration"
    )
    strategy_lab: StrategyLabPreferences = Field(
        default_factory=StrategyLabPreferences, description="Strategy Lab loop preferences"
    )
    favorite_pairs: list[str] = Field(
        default_factory=list,
        description="Shared favorite trading pairs across all sections",
    )
    theme_mode: str = Field("dark", description="UI colour mode: dark or light")

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_favorites(cls, data: Any) -> Any:
        """Merge per-section paired_favorites into top-level favorite_pairs."""
        if not isinstance(data, dict):
            return data
        data = dict(data)
        # Only migrate when top-level field is absent or empty
        if data.get("favorite_pairs"):
            return data
        collected: list[str] = []
        for section_key in ("backtest_preferences", "optimize_preferences", "download_preferences"):
            section = data.get(section_key)
            if isinstance(section, dict):
                for pair in section.get("paired_favorites", []):
                    if pair not in collected:
                        collected.append(pair)
        if collected:
            data["favorite_pairs"] = collected
        return data

    @field_validator(
        "venv_path",
        "python_executable",
        "freqtrade_executable",
        "user_data_path",
        "project_path",
        mode="before",
    )
    @classmethod
    def normalize_paths(cls, v):
        """Normalize path strings to absolute paths."""
        if v is None:
            return None
        return str(Path(v).expanduser().resolve())


class SettingsValidationResult(BaseModel):
    """Result of settings validation."""

    valid: bool
    python_ok: bool
    freqtrade_ok: bool
    user_data_ok: bool
    message: str
    details: dict = Field(default_factory=dict)


class ProcessOutput(BaseModel):
    """Captured process output and metadata."""

    stdout: str
    stderr: str
    exit_code: Optional[int]
    completed: bool
