#!/usr/bin/env python3
"""
run_checks.py — Run all project checks and print a summary.

Usage:
    python tools/run_checks.py
    python tools/run_checks.py --fast   (skip slow tests)
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parents[2]


def _run(label: str, cmd: list[str], cwd: Path = ROOT) -> tuple[bool, str]:
    start = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd))
    elapsed = time.time() - start
    ok = result.returncode == 0
    output = (result.stdout + result.stderr).strip()
    status = "✓" if ok else "✗"
    print(f"  {status} {label} ({elapsed:.1f}s)")
    if not ok:
        for line in output.splitlines()[-20:]:
            print(f"      {line}")
    return ok, output


def main() -> int:
    fast = "--fast" in sys.argv
    print("\n=== Project Checks ===\n")

    results: list[tuple[str, bool]] = []

    # 1. pytest
    pytest_cmd = ["pytest", "tests/", "--tb=short", "-q"]
    if fast:
        pytest_cmd += ["-x"]
    ok, _ = _run("pytest", pytest_cmd)
    results.append(("pytest", ok))

    # 2. ruff lint
    ok, _ = _run("ruff check app/", ["ruff", "check", "app/"])
    results.append(("ruff lint", ok))

    # 3. ruff format check
    ok, _ = _run("ruff format --check app/", ["ruff", "format", "--check", "app/"])
    results.append(("ruff format", ok))

    # 4. import check (syntax)
    ok, _ = _run("python -c import app", [sys.executable, "-c", "import app"])
    results.append(("import app", ok))

    print()
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"  Result: {passed}/{total} passed")

    if passed < total:
        failed = [name for name, ok in results if not ok]
        print(f"  Failed: {', '.join(failed)}")
        return 1

    print("  All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
