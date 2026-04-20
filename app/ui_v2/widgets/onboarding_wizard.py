"""OnboardingWizard for the v2 UI layer.

A ``QWizard`` subclass that guides first-time users through initial
configuration: venv path, user data directory, and settings validation.

Pages:
    0 — Welcome
    1 — Venv Path
    2 — User Data
    3 — Validation
    4 — Done

Requirements: 20.1, 20.2, 20.3, 20.4
"""
import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWizard,
    QWizardPage,
    QHBoxLayout,
    QFileDialog,
    QProgressBar,
    QScrollArea,
    QWidget,
)

from app.app_state.settings_state import SettingsState
from app.core.models.settings_models import AppSettings
from app.core.services.settings_service import SettingsService
from app.core.utils.app_logger import get_logger

_log = get_logger("ui_v2.onboarding_wizard")

# Page IDs
_PAGE_WELCOME = 0
_PAGE_VENV = 1
_PAGE_USER_DATA = 2
_PAGE_VALIDATION = 3
_PAGE_DONE = 4


# ---------------------------------------------------------------------------
# Page 0 — Welcome
# ---------------------------------------------------------------------------


class _WelcomePage(QWizardPage):
    """Welcome page — brief introduction."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("Welcome to Freqtrade GUI")
        self.setSubTitle(
            "This wizard will help you configure the application for first use.\n"
            "You will need a Python virtual environment with Freqtrade installed."
        )

        layout = QVBoxLayout(self)
        intro = QLabel(
            "Click <b>Next</b> to begin, or <b>Cancel</b> to configure settings manually later."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)


# ---------------------------------------------------------------------------
# Page 1 — Venv Path
# ---------------------------------------------------------------------------


class _VenvPathPage(QWizardPage):
    """Venv Path page — validates path and Python executable."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("Python Virtual Environment")
        self.setSubTitle(
            "Enter the path to the virtual environment that contains Freqtrade."
        )

        layout = QVBoxLayout(self)

        path_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("/path/to/venv  or  C:\\venv")
        self._path_edit.setAccessibleName("Virtual environment path")
        self._path_edit.setToolTip("Root directory of the Python virtual environment")
        self._path_edit.textChanged.connect(self.completeChanged)
        path_row.addWidget(self._path_edit)

        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        self._error_label = QLabel()
        self._error_label.setStyleSheet("color: #f44336;")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        layout.addWidget(self._error_label)

        # Register field so the wizard can read it
        self.registerField("venv_path*", self._path_edit)

    # ------------------------------------------------------------------

    def _browse(self) -> None:
        """Open a directory picker and populate the path field."""
        path = QFileDialog.getExistingDirectory(
            self, "Select Virtual Environment Directory"
        )
        if path:
            self._path_edit.setText(path)

    def _python_exe(self, venv: Path) -> Optional[Path]:
        """Return the Python executable path for the given venv, or None."""
        if os.name == "nt":
            candidate = venv / "Scripts" / "python.exe"
        else:
            candidate = venv / "bin" / "python"
        return candidate if candidate.exists() else None

    def isComplete(self) -> bool:
        """Return True only when the path exists and contains a Python executable."""
        text = self._path_edit.text().strip()
        if not text:
            self._error_label.hide()
            return False

        venv = Path(text).expanduser().resolve()
        if not venv.exists():
            self._error_label.setText(f"Path does not exist: {venv}")
            self._error_label.show()
            return False

        python = self._python_exe(venv)
        if python is None:
            self._error_label.setText(
                "No Python executable found in the venv.\n"
                "Expected: Scripts/python.exe (Windows) or bin/python (Unix)."
            )
            self._error_label.show()
            return False

        self._error_label.hide()
        return True

    def get_venv_path(self) -> str:
        """Return the validated venv path string."""
        return self._path_edit.text().strip()

    def get_python_exe(self) -> str:
        """Return the resolved Python executable path string."""
        venv = Path(self._path_edit.text().strip()).expanduser().resolve()
        python = self._python_exe(venv)
        return str(python) if python else ""


# ---------------------------------------------------------------------------
# Page 2 — User Data
# ---------------------------------------------------------------------------


class _UserDataPage(QWizardPage):
    """User Data page — validates or creates the user_data directory."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("User Data Directory")
        self.setSubTitle(
            "Specify the Freqtrade user_data directory.  "
            "This is where strategies, configs, and results are stored."
        )

        layout = QVBoxLayout(self)

        path_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("/path/to/user_data")
        self._path_edit.setAccessibleName("User data directory path")
        self._path_edit.textChanged.connect(self._on_text_changed)
        path_row.addWidget(self._path_edit)

        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        self._status_label.hide()
        layout.addWidget(self._status_label)

        self._create_btn = QPushButton("Create Directory")
        self._create_btn.hide()
        self._create_btn.clicked.connect(self._create_directory)
        layout.addWidget(self._create_btn)

        self.registerField("user_data_path*", self._path_edit)

    # ------------------------------------------------------------------

    def _browse(self) -> None:
        """Open a directory picker."""
        path = QFileDialog.getExistingDirectory(
            self, "Select User Data Directory"
        )
        if path:
            self._path_edit.setText(path)

    def _on_text_changed(self, text: str) -> None:
        """Update status label and create button visibility."""
        text = text.strip()
        if not text:
            self._status_label.hide()
            self._create_btn.hide()
            self.completeChanged.emit()
            return

        path = Path(text).expanduser().resolve()
        if path.exists() and path.is_dir():
            self._status_label.setText("✓ Directory exists.")
            self._status_label.setStyleSheet("color: #4caf50;")
            self._status_label.show()
            self._create_btn.hide()
        else:
            self._status_label.setText(
                f"Directory does not exist: {path}\n"
                "Click 'Create Directory' to create it."
            )
            self._status_label.setStyleSheet("color: #ff9800;")
            self._status_label.show()
            self._create_btn.show()

        self.completeChanged.emit()

    def _create_directory(self) -> None:
        """Attempt to create the specified directory."""
        text = self._path_edit.text().strip()
        if not text:
            return
        path = Path(text).expanduser().resolve()
        try:
            path.mkdir(parents=True, exist_ok=True)
            _log.info("Created user_data directory: %s", path)
            self._on_text_changed(str(path))
        except OSError as exc:
            self._status_label.setText(f"Failed to create directory: {exc}")
            self._status_label.setStyleSheet("color: #f44336;")
            self._status_label.show()

    def isComplete(self) -> bool:
        """Return True only when the directory exists."""
        text = self._path_edit.text().strip()
        if not text:
            return False
        path = Path(text).expanduser().resolve()
        return path.exists() and path.is_dir()

    def get_user_data_path(self) -> str:
        """Return the validated user_data path string."""
        return self._path_edit.text().strip()


# ---------------------------------------------------------------------------
# Page 3 — Validation
# ---------------------------------------------------------------------------


class _ValidationPage(QWizardPage):
    """Validation page — runs SettingsService.validate_settings and shows results."""

    def __init__(self, settings_service: SettingsService, parent=None) -> None:
        super().__init__(parent)
        self._settings_service = settings_service
        self._complete = False

        self.setTitle("Validating Settings")
        self.setSubTitle(
            "Checking that Python and Freqtrade are accessible from the configured venv."
        )

        layout = QVBoxLayout(self)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # indeterminate
        self._progress.hide()
        layout.addWidget(self._progress)

        # Scrollable results area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._results_widget = QWidget()
        self._results_layout = QVBoxLayout(self._results_widget)
        self._results_layout.setSpacing(4)
        scroll.setWidget(self._results_widget)
        layout.addWidget(scroll)

    # ------------------------------------------------------------------

    def initializePage(self) -> None:
        """Run validation when the page is shown."""
        # Clear previous results
        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._progress.show()
        self._complete = False
        self.completeChanged.emit()

        # Build a temporary AppSettings from wizard fields
        venv_path = self.wizard().field("venv_path") or ""
        user_data_path = self.wizard().field("user_data_path") or ""

        # Resolve python executable from venv
        python_exe = ""
        if venv_path:
            venv = Path(venv_path).expanduser().resolve()
            if os.name == "nt":
                candidate = venv / "Scripts" / "python.exe"
            else:
                candidate = venv / "bin" / "python"
            if candidate.exists():
                python_exe = str(candidate)

        settings = AppSettings(
            venv_path=venv_path or None,
            python_executable=python_exe or None,
            user_data_path=user_data_path or None,
        )

        try:
            result = self._settings_service.validate_settings(settings)
        except Exception as exc:
            _log.error("Validation error: %s", exc)
            self._add_result("Validation error", False, str(exc))
            self._progress.hide()
            self._complete = True
            self.completeChanged.emit()
            return

        self._progress.hide()

        # Display per-item results
        checks = [
            ("Python executable", result.python_ok),
            ("Freqtrade installation", result.freqtrade_ok),
            ("User data directory", result.user_data_ok),
        ]
        for label, ok in checks:
            self._add_result(label, ok)

        # Show extra details
        for key, val in result.details.items():
            detail_label = QLabel(f"  {key}: {val}")
            detail_label.setStyleSheet("color: #888; font-size: 11px;")
            self._results_layout.addWidget(detail_label)

        self._results_layout.addStretch()
        self._complete = True
        self.completeChanged.emit()
        _log.info("Onboarding validation: valid=%s", result.valid)

    def _add_result(self, label: str, ok: bool, detail: str = "") -> None:
        """Add a pass/fail row to the results layout."""
        icon = "✓" if ok else "✗"
        color = "#4caf50" if ok else "#f44336"
        text = f"<span style='color:{color};'>{icon}</span>  {label}"
        if detail:
            text += f"<br><small style='color:#888;'>{detail}</small>"
        lbl = QLabel(text)
        lbl.setTextFormat(Qt.RichText)
        self._results_layout.addWidget(lbl)

    def isComplete(self) -> bool:
        """Return True once validation has finished."""
        return self._complete


# ---------------------------------------------------------------------------
# Page 4 — Done
# ---------------------------------------------------------------------------


class _DonePage(QWizardPage):
    """Done page — confirms setup is complete."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("Setup Complete")
        self.setSubTitle("Freqtrade GUI is ready to use.")

        layout = QVBoxLayout(self)
        msg = QLabel(
            "Your settings have been saved.  "
            "Click <b>Finish</b> to start using the application."
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)


# ---------------------------------------------------------------------------
# OnboardingWizard
# ---------------------------------------------------------------------------


class OnboardingWizard(QWizard):
    """First-run setup wizard.

    Pages: Welcome → Venv Path → User Data → Validation → Done

    Args:
        settings_state:   Application settings state used to persist the
                          configured values on ``accept()``.
        parent:           Optional parent widget.
    """

    def __init__(
        self,
        settings_state: SettingsState,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._settings_state = settings_state
        self._settings_service = SettingsService()

        self.setWindowTitle("Freqtrade GUI — First-Run Setup")
        self.setWizardStyle(QWizard.ModernStyle)
        self.setMinimumSize(560, 420)

        # Add pages in order
        self._welcome_page = _WelcomePage()
        self._venv_page = _VenvPathPage()
        self._user_data_page = _UserDataPage()
        self._validation_page = _ValidationPage(self._settings_service)
        self._done_page = _DonePage()

        self.addPage(self._welcome_page)       # id 0
        self.addPage(self._venv_page)          # id 1
        self.addPage(self._user_data_page)     # id 2
        self.addPage(self._validation_page)    # id 3
        self.addPage(self._done_page)          # id 4

        self.accepted.connect(self._on_accepted)

    # ------------------------------------------------------------------

    def _on_accepted(self) -> None:
        """Persist the wizard-collected settings when the user clicks Finish."""
        venv_path = self.field("venv_path") or ""
        user_data_path = self.field("user_data_path") or ""

        # Resolve python executable
        python_exe = ""
        if venv_path:
            venv = Path(venv_path).expanduser().resolve()
            if os.name == "nt":
                candidate = venv / "Scripts" / "python.exe"
            else:
                candidate = venv / "bin" / "python"
            if candidate.exists():
                python_exe = str(candidate)

        # Load current settings and update paths
        current = self._settings_state.current_settings or AppSettings()
        updated = current.model_copy(
            update={
                "venv_path": venv_path or None,
                "python_executable": python_exe or None,
                "user_data_path": user_data_path or None,
            }
        )
        self._settings_state.save_settings(updated)
        _log.info(
            "OnboardingWizard: settings saved — venv=%s user_data=%s",
            venv_path,
            user_data_path,
        )
