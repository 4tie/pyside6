import os
import subprocess
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from app.core.models.settings_models import (
    AppSettings,
    SettingsValidationResult,
    update_preference_fields,
)
from app.core.parsing.json_parser import parse_json_file, write_json_file_atomic, ParseError
from app.core.utils.app_logger import get_logger

_log = get_logger("settings")


class SettingsService:
    """Manages application settings persistence and resolution."""

    _PREFERENCE_SECTIONS = frozenset(
        {
            "backtest_preferences",
            "optimize_preferences",
            "download_preferences",
            "optimizer_preferences",
            "strategy_lab",
            "terminal_preferences",
            "ai",
            "shared_inputs",
        }
    )

    def __init__(self, settings_file: Optional[str] = None):
        if settings_file:
            self.settings_file = Path(settings_file)
        else:
            # Store settings in the project's data directory
            self.settings_file = Path(__file__).parent.parent.parent.parent / "data" / "settings.json"
        self.settings: Optional[AppSettings] = None

    def load_settings(self) -> AppSettings:
        """Load settings from file or return defaults."""
        if self.settings_file.exists():
            try:
                data = parse_json_file(self.settings_file)
                self.settings = AppSettings(**data)
                _log.debug("Settings loaded from %s", self.settings_file)
                return self.settings
            except ParseError as e:
                _log.error("Failed to load settings from %s: %s", self.settings_file, e)
                print(f"Failed to load settings: {e}")
        else:
            _log.info("No settings file found at %s — using defaults", self.settings_file)

        self.settings = AppSettings()
        return self.settings

    def save_settings(self, settings: AppSettings) -> bool:
        """Save settings to file."""
        try:
            write_json_file_atomic(self.settings_file, settings.model_dump())
            self.settings = settings
            _log.info("Settings saved to %s", self.settings_file)
            _log.debug("Saved: python=%s venv=%s user_data=%s",
                       settings.python_executable, settings.venv_path, settings.user_data_path)
            return True
        except ParseError as e:
            _log.error("Failed to save settings to %s: %s", self.settings_file, e)
            print(f"Failed to save settings: {e}")
            return False

    def get_preferences(self, section: str) -> BaseModel:
        """Return a specific preference section from the current settings."""
        if section not in self._PREFERENCE_SECTIONS:
            raise ValueError(f"Unknown settings preference section: {section}")
        settings = self.load_settings()
        preferences = getattr(settings, section)
        if not isinstance(preferences, BaseModel):
            raise ValueError(f"Settings section is not a preference model: {section}")
        return preferences

    def update_preferences(self, section: str, **kwargs) -> BaseModel:
        """Partially update one preference section and persist settings atomically."""
        if section not in self._PREFERENCE_SECTIONS:
            raise ValueError(f"Unknown settings preference section: {section}")
        settings = self.load_settings()
        current = getattr(settings, section)
        if not isinstance(current, BaseModel):
            raise ValueError(f"Settings section is not a preference model: {section}")
        updated = update_preference_fields(current, kwargs)
        setattr(settings, section, updated)
        if not self.save_settings(settings):
            raise RuntimeError(f"Failed to save settings preference section: {section}")
        return updated

    def resolve_python_executable(self, venv_path: Optional[str] = None) -> Optional[str]:
        """Resolve Python executable from venv path."""
        if venv_path:
            return self._resolve_python_from_venv(venv_path)
        if self.settings and self.settings.python_executable:
            return self.settings.python_executable
        return None

    def resolve_freqtrade_executable(self, venv_path: Optional[str] = None) -> Optional[str]:
        """Resolve freqtrade executable from venv path."""
        if venv_path:
            return self._resolve_freqtrade_from_venv(venv_path)
        if self.settings and self.settings.freqtrade_executable:
            return self.settings.freqtrade_executable
        return None

    @staticmethod
    def _resolve_python_from_venv(venv_path: str) -> str:
        """Get Python executable path from venv."""
        venv = Path(venv_path)
        if os.name == "nt":
            python_path = venv / "Scripts" / "python.exe"
        else:
            python_path = venv / "bin" / "python"
        return str(python_path)

    @staticmethod
    def _resolve_freqtrade_from_venv(venv_path: str) -> Optional[str]:
        """Get freqtrade executable path from venv."""
        venv = Path(venv_path)
        if os.name == "nt":
            exe_path = venv / "Scripts" / "freqtrade.exe"
        else:
            exe_path = venv / "bin" / "freqtrade"
        return str(exe_path) if exe_path.exists() else None

    def validate_settings(self, settings: AppSettings) -> SettingsValidationResult:
        """Validate application settings in order."""
        _log.info("Validating settings...")
        details = {}

        # 1. Python exists
        python_ok = False
        if settings.python_executable:
            python_path = Path(settings.python_executable)
            python_ok = python_path.exists()
            details["python_exists"] = python_ok

            # 2. Python works
            if python_ok:
                try:
                    result = subprocess.run(
                        [settings.python_executable, "--version"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    python_ok = result.returncode == 0
                    details["python_version"] = result.stdout.strip() or result.stderr.strip()
                except Exception as e:
                    python_ok = False
                    details["python_error"] = str(e)

        # 3. Freqtrade exists
        freqtrade_ok = False
        if settings.use_module_execution and python_ok:
            try:
                result = subprocess.run(
                    [settings.python_executable, "-m", "freqtrade", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                freqtrade_ok = result.returncode == 0
                details["freqtrade_version"] = result.stdout.strip() or result.stderr.strip()
            except Exception as e:
                details["freqtrade_error"] = str(e)

                # Try executable if module execution fails
                if settings.freqtrade_executable:
                    try:
                        result = subprocess.run(
                            [settings.freqtrade_executable, "--version"],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        freqtrade_ok = result.returncode == 0
                        details["freqtrade_version"] = result.stdout.strip() or result.stderr.strip()
                    except Exception as e2:
                        details["freqtrade_executable_error"] = str(e2)
        elif settings.freqtrade_executable:
            try:
                result = subprocess.run(
                    [settings.freqtrade_executable, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                freqtrade_ok = result.returncode == 0
                details["freqtrade_version"] = result.stdout.strip() or result.stderr.strip()
            except Exception as e:
                details["freqtrade_error"] = str(e)

        # 4. user_data exists
        user_data_ok = False
        if settings.user_data_path:
            user_data_path = Path(settings.user_data_path)
            user_data_ok = user_data_path.exists() and user_data_path.is_dir()
            details["user_data_exists"] = user_data_ok

        valid = python_ok and freqtrade_ok and user_data_ok
        message = "Settings are valid" if valid else "Settings validation failed"
        _log.info("Validation result: valid=%s python=%s freqtrade=%s user_data=%s",
                  valid, python_ok, freqtrade_ok, user_data_ok)
        if details.get("python_version"):
            _log.info("  %s", details["python_version"])
        if details.get("freqtrade_version"):
            _log.info("  %s", details["freqtrade_version"])

        return SettingsValidationResult(
            valid=valid,
            python_ok=python_ok,
            freqtrade_ok=freqtrade_ok,
            user_data_ok=user_data_ok,
            message=message,
            details=details
        )
