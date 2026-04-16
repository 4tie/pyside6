from pydantic import BaseModel, Field, field_validator
from typing import Optional
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
    download_preferences: DownloadPreferences = Field(
        default_factory=DownloadPreferences, description="Download data UI preferences"
    )
    terminal_preferences: TerminalPreferences = Field(
        default_factory=TerminalPreferences, description="Terminal appearance preferences"
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
