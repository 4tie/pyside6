#!/usr/bin/env python3
"""
check_hardcoded_paths.py — Detect hardcoded absolute paths in Python source files.
Fails CI if any .py file in app/ or data/tools/ contains hardcoded Windows/Unix paths.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent

# Patterns that indicate hardcoded paths
_PATTERNS = [
    # Windows absolute paths like T:/ae/... or C:\Users\...
    # Must be a string literal (in quotes), not an f-string variable
    re.compile(r'["\'][A-Za-z]:[/\\\\]', re.IGNORECASE),
    # Unix absolute paths like /home/user/... or /Users/...
    re.compile(r'["\']/(home|Users|root|opt|srv)/'),
    # sys.path.insert with absolute path
    re.compile(r'sys\.path\.insert\s*\(\s*0\s*,\s*["\'][A-Za-z/\\\\]'),
]

# Files/patterns to skip
_SKIP_PATTERNS = [
    "ci_checks",
    "__pycache__",
    ".pyc",
]

SCAN_DIRS = [
    ROOT / "app",
    ROOT / "data" / "tools",
]


def _should_skip(path: Path) -> bool:
    return any(skip in str(path) for skip in _SKIP_PATTERNS)


def _check_file(path: Path) -> list[str]:
    violations: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return violations

    for i, line in enumerate(lines, 1):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for pattern in _PATTERNS:
            if pattern.search(line):
                violations.append(
                    f"  HARDCODED PATH: {path.relative_to(ROOT)}:{i}\n"
                    f"    {stripped[:120]}"
                )
                break
    return violations


def main() -> int:
    violations: list[str] = []
    checked = 0

    for scan_dir in SCAN_DIRS:
        for f in scan_dir.rglob("*.py"):
            if _should_skip(f):
                continue
            violations.extend(_check_file(f))
            checked += 1

    if violations:
        print("check_hardcoded_paths: FAILED — hardcoded paths detected:")
        for v in violations:
            print(v)
        return 1

    print(f"check_hardcoded_paths: OK — {checked} files checked, no hardcoded paths")
    return 0


if __name__ == "__main__":
    sys.exit(main())
