"""Property test P1 — Service Immutability.

After the full redesign, no file in ``app/core/`` or ``app/app_state/``
should have been modified.  This is verified by checking ``git diff
--name-only`` against the base commit and asserting that none of the
changed files fall outside ``app/ui_v2/`` and ``main.py``.

**Property P1: Service Immutability — no file outside ``app/ui_v2/`` and
``main.py`` is modified.**

**Validates: Requirements 1.7**
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def _git_changed_files() -> list[str]:
    """Return a list of files changed relative to the HEAD commit.

    Uses ``git diff --name-only HEAD`` so it captures both staged and
    unstaged changes.  Falls back to an empty list if git is unavailable
    or the directory is not a repository.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return []
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return lines
    except FileNotFoundError:
        # git not available in this environment
        return []


def _is_allowed_path(path: str) -> bool:
    """Return True if *path* is within the allowed modification scope.

    Allowed paths:
    - ``main.py`` (entry-point flag addition)
    - Anything under ``app/ui_v2/``
    - Anything under ``tests/ui_v2/`` (test files for the new UI)
    - Anything under ``.kiro/`` (spec / task tracking files)

    Args:
        path: Relative file path as returned by ``git diff --name-only``.

    Returns:
        ``True`` if the path is within the allowed scope.
    """
    p = Path(path)
    allowed_prefixes = (
        "app/ui_v2/",
        "app\\ui_v2\\",
        "tests/ui_v2/",
        "tests\\ui_v2\\",
        ".kiro/",
        ".kiro\\",
    )
    allowed_exact = {"main.py"}

    if str(p) in allowed_exact or p.name in allowed_exact and len(p.parts) == 1:
        return True
    for prefix in allowed_prefixes:
        if str(p).startswith(prefix) or path.startswith(prefix):
            return True
    return False


def test_no_core_or_app_state_files_modified() -> None:
    """P1 — No file in app/core/ or app/app_state/ was modified.

    **Validates: Requirements 1.7**
    """
    changed = _git_changed_files()

    violations: list[str] = []
    for path in changed:
        p = Path(path)
        parts = p.parts
        # Flag any change inside app/core/ or app/app_state/
        if len(parts) >= 2 and parts[0] == "app" and parts[1] in ("core", "app_state"):
            violations.append(path)

    assert violations == [], (
        "Service Immutability violated — the following files in app/core/ or "
        "app/app_state/ were modified:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_all_changed_files_within_allowed_scope() -> None:
    """P1 — Every changed file is within app/ui_v2/, main.py, or test/spec files.

    **Validates: Requirements 1.7**
    """
    changed = _git_changed_files()

    violations: list[str] = []
    for path in changed:
        if not _is_allowed_path(path):
            violations.append(path)

    assert violations == [], (
        "Service Immutability violated — the following files were modified "
        "outside the allowed scope (app/ui_v2/, main.py, tests/ui_v2/, .kiro/):\n"
        + "\n".join(f"  {v}" for v in violations)
    )
