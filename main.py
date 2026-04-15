import sys

from PySide6.QtWidgets import QApplication

from app.app_state.settings_state import SettingsState
from app.ui.main_window import MainWindow


def main():
    """Main entry point for the application."""
    app = QApplication(sys.argv)

    # Initialize settings state
    settings_state = SettingsState()
    settings_state.load_settings()

    # Create and show main window
    window = MainWindow(settings_state=settings_state)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
