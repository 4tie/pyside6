import sys

from PySide6.QtWidgets import QApplication

from app.app_state.settings_state import SettingsState
from app.core.utils.app_logger import setup_logging, get_logger
from app.ui.main_window import MainWindow


def main():
    """Main entry point for the application."""
    app = QApplication(sys.argv)

    # Initialize settings state
    settings_state = SettingsState()
    settings = settings_state.load_settings()

    # Set up logging — writes to user_data/logs/app.log if path is configured
    setup_logging(settings.user_data_path)
    log = get_logger()
    log.info("Application starting")
    log.debug("Settings loaded: user_data_path=%s", settings.user_data_path)

    # Create and show main window
    window = MainWindow(settings_state=settings_state)
    window.show()
    log.info("Main window shown")

    exit_code = app.exec()
    log.info("Application exiting with code %d", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
