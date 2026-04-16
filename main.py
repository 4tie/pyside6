import sys
import platform

from PySide6.QtWidgets import QApplication
from PySide6 import __version__ as pyside_version

from app.app_state.settings_state import SettingsState
from app.core.utils.app_logger import setup_logging, get_logger
from app.ui.main_window import MainWindow


def main():
    """Main entry point for the application."""
    app = QApplication(sys.argv)

    # Load settings first so we know the log path
    settings_state = SettingsState()
    settings = settings_state.load_settings()

    setup_logging(settings.user_data_path)
    log = get_logger("startup")

    log.info("=" * 60)
    log.info("Freqtrade GUI starting")
    log.info("Python     : %s", sys.version.split()[0])
    log.info("Platform   : %s %s", platform.system(), platform.release())
    log.info("PySide6    : %s", pyside_version)
    log.info("user_data  : %s", settings.user_data_path)
    log.info("venv       : %s", settings.venv_path)
    log.info("python_exe : %s", settings.python_executable)
    log.info("freqtrade  : %s", settings.freqtrade_executable)
    log.info("use_module : %s", settings.use_module_execution)
    log.info("=" * 60)

    window = MainWindow(settings_state=settings_state)
    window.show()
    log.info("Main window shown")

    exit_code = app.exec()
    log.info("Application exiting — code=%d", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
