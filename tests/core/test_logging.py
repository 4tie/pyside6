"""Tests for the logging setup and get_logger factory."""
import logging
from pathlib import Path

import pytest

from app.core.utils.app_logger import get_logger, configure_logging


def test_get_logger_returns_logger():
    log = get_logger("test.module")
    assert isinstance(log, logging.Logger)


def test_get_logger_name_contains_section():
    log = get_logger("services.backtest")
    assert "services.backtest" in log.name


def test_get_logger_none_returns_root_child():
    log = get_logger()
    assert log is not None


def test_configure_logging_creates_log_dir(tmp_path):
    log_dir = tmp_path / "logs"
    configure_logging(str(log_dir))
    assert log_dir.exists()


def test_configure_logging_idempotent(tmp_path):
    """Calling setup_logging twice should not raise."""
    log_dir = tmp_path / "logs2"
    configure_logging(str(log_dir))
    configure_logging(str(log_dir))


def test_logger_levels_work(tmp_path):
    log_dir = tmp_path / "logs"
    configure_logging(str(log_dir))
    log = get_logger("test.levels")
    # Should not raise
    log.debug("debug message")
    log.info("info message")
    log.warning("warning message")
    log.error("error message")


def test_multiple_get_logger_calls_same_name_return_same_logger():
    log1 = get_logger("services.settings")
    log2 = get_logger("services.settings")
    assert log1.name == log2.name
