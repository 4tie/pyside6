from pydantic import BaseModel, Field, field_validator
from typing import Optional
from pathlib import Path


class AppSettings(BaseModel):
    """Main application settings for Freqtrade GUI."""
    venv_path: Optional[str] = Field(None, description="Path to Python virtual environment")
    python_executable: Optional[str] = Field(None, description="Full path to Python interpreter")
    freqtrade_executable: Optional[str] = Field(None, description="Full path to freqtrade executable")
    user_data_path: Optional[str] = Field(None, description="Path to freqtrade user_data directory")
    project_path: Optional[str] = Field(None, description="Path to freqtrade project root")
    shell_executable: Optional[str] = Field(None, description="Shell executable path")
    shell_args: list[str] = Field(default_factory=list, description="Arguments for shell")
    use_module_execution: bool = Field(True, description="Use python -m freqtrade instead of executable")

    @field_validator("venv_path", "python_executable", "freqtrade_executable",
                    "user_data_path", "project_path", "shell_executable", mode="before")
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
