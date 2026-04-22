"""onboarding_wizard.py — First-run setup wizard for the Freqtrade GUI.

Guides the user through configuring the venv path and user_data directory
before the main window is shown. Uses Qt's built-in QWizard framework.

Pages:
    1. Welcome       — introduction, no fields
    2. Venv Path     — browse for venv directory; validates Python executable exists
    3. User Data     — browse for user_data directory; offers to create if absent
    4. Validation    — runs SettingsService.validate_settings and shows per-item results
    5. Done          — confirmation message
"""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWizard,
    QWizardPage,
    QMessageBox,
)

from app.app_state.settings_state import SettingsState
from app.core.models.settings_models import AppSettings
from app.core.utils.app_logger import get_logger
from app.ui.theme import FONT, PALETTE, SPACING

_log = get_logger("ui.onboarding_wizard")

# QWizard page IDs
_PAGE_WELCOME = 0
_PAGE_VENV = 1
_PAGE_USER_DATA = 2
_PAGE_VALIDATION = 3
_PAGE_DONE = 4


def _python_exe_for_venv(venv_path: str) -> Path:
    """Return the expected Python executable path for a given venv directory.

    Args:
        venv_path: Path to the virtual environment root.

    Returns:
        Path object pointing to the Python executable.
    """
    venv = Path(venv_path)
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


# ---------------------------------------------------------------------------
# Page 1 — Welcome
# ---------------------------------------------------------------------------

class _WelcomePage(QWizardPage):
    """Welcome page: title + brief description, no fields."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("Welcome to Freqtrade GUI")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING["md"])

        desc = QLabel(
            "This wizard will help you configure the application for first use.\n\n"
            "You will need:\n"
            "  • A Python virtual environment with Freqtrade installed\n"
            "  • A Freqtrade user_data directory\n\n"
            "Click Next to begin."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {PALETTE['text_primary']}; font-size: {FONT['size_base']}px;")
        layout.addWidget(desc)
        layout.addStretch()


# ---------------------------------------------------------------------------
# Page 2 — Venv Path
# ---------------------------------------------------------------------------

class _VenvPathPage(QWizardPage):
    """Venv path page: browse for venv directory and validate Python executable."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("Virtual Environment")
        self.setSubTitle(
            "Select the Python virtual environment that contains Freqtrade."
        )
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING["sm"])

        row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Path to venv directory…")
        self._path_edit.setAccessibleName("Venv path")
        self._path_edit.setToolTip("Root directory of the Python virtual environment")
        row.addWidget(self._path_edit)

        browse_btn = QPushButton("Browse…")
        browse_btn.setToolTip("Open folder browser")
        browse_btn.clicked.connect(self._browse)
        row.addWidget(browse_btn)
        layout.addLayout(row)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)
        layout.addStretch()

        # Register field so QWizard can access it
        self.registerField("venv_path*", self._path_edit)
        self._path_edit.textChanged.connect(self._validate_path)

    def _browse(self) -> None:
        """Open a directory browser and populate the path field."""
        path = QFileDialog.getExistingDirectory(
            self, "Select Virtual Environment Directory", str(Path.home())
        )
        if path:
            self._path_edit.setText(path)

    def _validate_path(self, text: str) -> None:
        """Show inline feedback about the selected venv path."""
        if not text.strip():
            self._status_label.setText("")
            return

        python_exe = _python_exe_for_venv(text.strip())
        if python_exe.exists():
            self._status_label.setText(
                f"✓ Python found: {python_exe}"
            )
            self._status_label.setStyleSheet(f"color: {PALETTE['success']};")
        else:
            self._status_label.setText(
                f"✗ Python not found at {python_exe}\n"
                "Make sure this is a valid virtual environment."
            )
            self._status_label.setStyleSheet(f"color: {PALETTE['danger']};")

    def validatePage(self) -> bool:  # noqa: N802 — Qt override
        """Validate that the venv path contains a Python executable."""
        path = self._path_edit.text().strip()
        if not path:
            return False
        venv_dir = Path(path)
        if not venv_dir.is_dir():
            QMessageBox.warning(
                self,
                "Invalid Path",
                f"The directory does not exist:\n{path}",
            )
            return False
        python_exe = _python_exe_for_venv(path)
        if not python_exe.exists():
            result = QMessageBox.question(
                self,
                "Python Not Found",
                f"Could not find Python at:\n{python_exe}\n\n"
                "Continue anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            return result == QMessageBox.Yes
        return True


# ---------------------------------------------------------------------------
# Page 3 — User Data
# ---------------------------------------------------------------------------

class _UserDataPage(QWizardPage):
    """User data page: browse for user_data directory; offer to create if absent."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("User Data Directory")
        self.setSubTitle(
            "Select the Freqtrade user_data directory. "
            "This is where strategies, configs, and results are stored."
        )
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING["sm"])

        row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Path to user_data directory…")
        self._path_edit.setAccessibleName("User data path")
        self._path_edit.setToolTip("Freqtrade user_data directory containing strategies and configs")
        row.addWidget(self._path_edit)

        browse_btn = QPushButton("Browse…")
        browse_btn.setToolTip("Open folder browser")
        browse_btn.clicked.connect(self._browse)
        row.addWidget(browse_btn)
        layout.addLayout(row)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)
        layout.addStretch()

        self.registerField("user_data_path*", self._path_edit)
        self._path_edit.textChanged.connect(self._check_path)

    def _browse(self) -> None:
        """Open a directory browser and populate the path field."""
        path = QFileDialog.getExistingDirectory(
            self, "Select user_data Directory", str(Path.home())
        )
        if path:
            self._path_edit.setText(path)

    def _check_path(self, text: str) -> None:
        """Show inline feedback about the selected user_data path."""
        if not text.strip():
            self._status_label.setText("")
            return
        p = Path(text.strip())
        if p.is_dir():
            self._status_label.setText("✓ Directory exists.")
            self._status_label.setStyleSheet(f"color: {PALETTE['success']};")
        else:
            self._status_label.setText(
                "Directory does not exist. It will be created when you click Next."
            )
            self._status_label.setStyleSheet(f"color: {PALETTE['warning']};")

    def validatePage(self) -> bool:  # noqa: N802
        """Validate or offer to create the user_data directory."""
        path = self._path_edit.text().strip()
        if not path:
            return False
        p = Path(path)
        if p.is_dir():
            return True
        result = QMessageBox.question(
            self,
            "Directory Not Found",
            f"The directory does not exist:\n{path}\n\nCreate it now?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if result == QMessageBox.Yes:
            try:
                p.mkdir(parents=True, exist_ok=True)
                _log.info("Created user_data directory: %s", p)
                return True
            except OSError as exc:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Could not create directory:\n{exc}",
                )
                return False
        return False


# ---------------------------------------------------------------------------
# Page 4 — Validation
# ---------------------------------------------------------------------------

class _ValidationPage(QWizardPage):
    """Validation page: runs SettingsService.validate_settings and shows results."""

    def __init__(self, settings_state: SettingsState, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("Validating Configuration")
        self.setSubTitle("Checking that all configured paths are accessible.")
        self._settings_state = settings_state
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING["sm"])

        self._python_label = QLabel("Python executable: checking…")
        self._freqtrade_label = QLabel("Freqtrade: checking…")
        self._user_data_label = QLabel("User data directory: checking…")
        self._overall_label = QLabel("")
        self._overall_label.setWordWrap(True)

        for lbl in (
            self._python_label,
            self._freqtrade_label,
            self._user_data_label,
            self._overall_label,
        ):
            layout.addWidget(lbl)

        layout.addStretch()

    def initializePage(self) -> None:  # noqa: N802
        """Run validation when the page is shown."""
        venv_path = self.field("venv_path") or ""
        user_data_path = self.field("user_data_path") or ""

        python_exe = str(_python_exe_for_venv(venv_path)) if venv_path else None

        settings = AppSettings(
            venv_path=venv_path or None,
            python_executable=python_exe,
            user_data_path=user_data_path or None,
        )

        result = self._settings_state.settings_service.validate_settings(settings)

        def _status(ok: bool, ok_text: str, fail_text: str) -> tuple[str, str]:
            if ok:
                return f"✓ {ok_text}", f"color: {PALETTE['success']};"
            return f"✗ {fail_text}", f"color: {PALETTE['danger']};"

        txt, style = _status(result.python_ok, "Python OK", "Python not found or not working")
        self._python_label.setText(txt)
        self._python_label.setStyleSheet(style)

        txt, style = _status(result.freqtrade_ok, "Freqtrade OK", "Freqtrade not found or not working")
        self._freqtrade_label.setText(txt)
        self._freqtrade_label.setStyleSheet(style)

        txt, style = _status(result.user_data_ok, "User data directory OK", "User data directory not found")
        self._user_data_label.setText(txt)
        self._user_data_label.setStyleSheet(style)

        if result.valid:
            self._overall_label.setText("All checks passed. Click Next to finish setup.")
            self._overall_label.setStyleSheet(f"color: {PALETTE['success']}; font-weight: bold;")
        else:
            self._overall_label.setText(
                "Some checks failed. You can still continue, but the application "
                "may not work correctly until the issues are resolved."
            )
            self._overall_label.setStyleSheet(f"color: {PALETTE['warning']};")


# ---------------------------------------------------------------------------
# Page 5 — Done
# ---------------------------------------------------------------------------

class _DonePage(QWizardPage):
    """Done page: confirmation message."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("Setup Complete!")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING["md"])

        msg = QLabel(
            "Freqtrade GUI is now configured.\n\n"
            "Click Finish to start using the application."
        )
        msg.setWordWrap(True)
        msg.setStyleSheet(f"color: {PALETTE['text_primary']}; font-size: {FONT['size_base']}px;")
        layout.addWidget(msg)
        layout.addStretch()


# ---------------------------------------------------------------------------
# OnboardingWizard
# ---------------------------------------------------------------------------

class OnboardingWizard(QWizard):
    """First-run setup wizard: Welcome → Venv Path → User Data → Validation → Done.

    Args:
        settings_state: Application settings state used to save the configured paths.
        parent: Optional parent widget.
    """

    def __init__(self, settings_state: SettingsState, parent=None) -> None:
        super().__init__(parent)
        self._settings_state = settings_state
        self.setWindowTitle("Freqtrade GUI — Setup Wizard")
        self.setWizardStyle(QWizard.ModernStyle)
        self.setMinimumSize(560, 400)

        self.setPage(_PAGE_WELCOME, _WelcomePage(self))
        self.setPage(_PAGE_VENV, _VenvPathPage(self))
        self.setPage(_PAGE_USER_DATA, _UserDataPage(self))
        self.setPage(_PAGE_VALIDATION, _ValidationPage(settings_state, self))
        self.setPage(_PAGE_DONE, _DonePage(self))

        self.setStartId(_PAGE_WELCOME)

        # Save settings when the wizard finishes
        self.finished.connect(self._on_finished)

        _log.info("OnboardingWizard initialised")

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_finished(self, result: int) -> None:
        """Save configured paths to AppSettings when the wizard is accepted.

        Args:
            result: QDialog.Accepted (1) or QDialog.Rejected (0).
        """
        if result != QWizard.Accepted:
            _log.info("OnboardingWizard cancelled — settings not saved")
            return

        venv_path = self.field("venv_path") or ""
        user_data_path = self.field("user_data_path") or ""

        settings = self._settings_state.current_settings
        if settings is None:
            settings = AppSettings()

        # Build a new settings object with the wizard values merged in
        updated = settings.model_copy(
            update={
                "venv_path": venv_path or None,
                "python_executable": str(_python_exe_for_venv(venv_path)) if venv_path else None,
                "user_data_path": user_data_path or None,
            }
        )

        self._settings_state.save_settings(updated)
        _log.info(
            "OnboardingWizard finished — venv=%r user_data=%r", venv_path, user_data_path
        )
