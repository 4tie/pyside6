from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Any
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


class AISettings(BaseModel):
    """AI panel configuration."""

    provider: str = Field("ollama", description="Active provider: 'ollama' or 'openrouter'")
    ollama_base_url: str = Field("http://localhost:11434", description="Ollama server base URL")
    openrouter_api_key: Optional[str] = Field(None, description="OpenRouter API key")
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
    def migrate_legacy_selected_model(cls, data: Any) -> Any:
        """Map legacy 'selected_model' key to 'chat_model' if present."""
        if isinstance(data, dict):
            if "selected_model" in data and "chat_model" not in data:
                data = dict(data)
                data["chat_model"] = data.pop("selected_model")
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
