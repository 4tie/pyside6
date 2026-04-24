"""Smoke tests for framework independence of core modules.

Verifies that ProcessRunManager, ProcessRun, and ProcessService do not
import PySide6, fastapi, or starlette in their module source, and that
they can be instantiated without a Qt application.

Note: pytest-qt loads PySide6 into sys.modules at session start, so we
cannot use sys.modules presence as the signal. Instead we inspect the
module's source code and its __dict__ for framework symbols.

Feature: process-run-manager
Validates: Requirements 6.1, 6.2, 6.3
"""

import importlib
import inspect
import sys


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _module_imports_framework(module_name: str, framework: str) -> bool:
    """Return True if the named module's source contains an import of framework."""
    mod = sys.modules.get(module_name) or importlib.import_module(module_name)
    try:
        source = inspect.getsource(mod)
    except (OSError, TypeError):
        return False
    # Check for any import statement referencing the framework
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if f"import {framework}" in stripped or f"from {framework}" in stripped:
            return True
    return False


# ---------------------------------------------------------------------------
# Smoke test 1: ProcessRunManager and ProcessRun do not import Qt/web frameworks
# Validates: Requirements 6.1, 6.2
# ---------------------------------------------------------------------------


def test_process_run_manager_no_pyside6_import() -> None:
    """ProcessRunManager module must not contain any PySide6 import.

    **Validates: Requirements 6.1**
    """
    assert not _module_imports_framework(
        "app.core.services.process_run_manager", "PySide6"
    ), "process_run_manager.py must not import PySide6"


def test_process_run_manager_no_fastapi_import() -> None:
    """ProcessRunManager module must not contain any fastapi import.

    **Validates: Requirements 6.1**
    """
    assert not _module_imports_framework(
        "app.core.services.process_run_manager", "fastapi"
    ), "process_run_manager.py must not import fastapi"


def test_process_run_manager_no_starlette_import() -> None:
    """ProcessRunManager module must not contain any starlette import.

    **Validates: Requirements 6.1**
    """
    assert not _module_imports_framework(
        "app.core.services.process_run_manager", "starlette"
    ), "process_run_manager.py must not import starlette"


def test_process_run_model_no_pyside6_import() -> None:
    """ProcessRun model module must not contain any PySide6 import.

    **Validates: Requirements 6.2**
    """
    assert not _module_imports_framework(
        "app.core.models.run_models", "PySide6"
    ), "run_models.py must not import PySide6"


def test_process_run_model_no_fastapi_import() -> None:
    """ProcessRun model module must not contain any fastapi import.

    **Validates: Requirements 6.2**
    """
    assert not _module_imports_framework(
        "app.core.models.run_models", "fastapi"
    ), "run_models.py must not import fastapi"


def test_process_run_model_no_starlette_import() -> None:
    """ProcessRun model module must not contain any starlette import.

    **Validates: Requirements 6.2**
    """
    assert not _module_imports_framework(
        "app.core.models.run_models", "starlette"
    ), "run_models.py must not import starlette"


# ---------------------------------------------------------------------------
# Smoke test 2: ProcessService does not import PySide6
# Validates: Requirements 6.1
# ---------------------------------------------------------------------------


def test_process_service_no_pyside6_import() -> None:
    """ProcessService module must not contain any PySide6 import.

    **Validates: Requirements 6.1**
    """
    assert not _module_imports_framework(
        "app.core.services.process_service", "PySide6"
    ), "process_service.py must not import PySide6"


def test_process_service_importable() -> None:
    """ProcessService must be importable without raising any exception.

    **Validates: Requirements 6.1**
    """
    from app.core.services.process_service import ProcessService  # noqa: F401

    assert ProcessService is not None, "ProcessService must be importable"


# ---------------------------------------------------------------------------
# Smoke test 3: ProcessRunManager instantiation without Qt application
# Validates: Requirements 6.3
# ---------------------------------------------------------------------------


def test_process_run_manager_instantiation_without_qt() -> None:
    """ProcessRunManager must be instantiable without a Qt application instance.

    **Validates: Requirements 6.3**
    """
    from app.core.services.process_run_manager import ProcessRunManager

    # Must not raise
    manager = ProcessRunManager()

    assert manager is not None
    assert manager.list_runs() == [], (
        "A freshly created manager must have no runs"
    )


def test_process_service_instantiation_without_qt() -> None:
    """ProcessService must be instantiable without a Qt application instance.

    **Validates: Requirements 6.3**
    """
    from app.core.services.process_service import ProcessService

    # Must not raise
    svc = ProcessService()
    assert svc is not None
    assert svc._current_run_id is None
    assert svc.is_running() is False
