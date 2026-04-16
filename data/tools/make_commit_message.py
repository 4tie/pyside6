#!/usr/bin/env python3
"""
make_commit_message.py — Generate a conventional commit message from staged changes.

Usage:
    python tools/make_commit_message.py
    python tools/make_commit_message.py --type fix --scope backtest
    python tools/make_commit_message.py --type feat --scope ui --body "Added run picker"
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def _git(args: list[str]) -> str:
    result = subprocess.run(
        ["git"] + args, capture_output=True, text=True, cwd=str(ROOT)
    )
    return result.stdout.strip()


def _staged_files() -> list[str]:
    out = _git(["diff", "--cached", "--name-only"])
    return [f.strip() for f in out.splitlines() if f.strip()]


def _infer_scope(files: list[str]) -> str:
    """Infer scope from changed file paths."""
    paths = [Path(f) for f in files]
    parts: list[str] = []
    for p in paths:
        if "ui/pages" in str(p):
            parts.append(p.stem.replace("_page", ""))
        elif "ui/widgets" in str(p):
            parts.append(p.stem.replace("_widget", ""))
        elif "core/services" in str(p):
            parts.append(p.stem.replace("_service", ""))
        elif "core/freqtrade" in str(p):
            parts.append("command")
        elif "core/utils" in str(p):
            parts.append(p.stem)
        elif "core/models" in str(p):
            parts.append("models")
        elif "data/docs" in str(p):
            parts.append("docs")
        elif "data/tools" in str(p):
            parts.append("tools")
        elif "tests" in str(p):
            parts.append("tests")
    unique = list(dict.fromkeys(parts))
    return ",".join(unique[:2]) if unique else ""


def _infer_type(files: list[str]) -> str:
    """Infer change type from file paths."""
    paths_str = " ".join(files)
    if "data/docs" in paths_str and len(files) <= 3:
        return "docs"
    if "tests/" in paths_str and all("tests/" in f for f in files):
        return "test"
    return "feat"


def _diff_summary() -> str:
    """Get a short summary of staged changes."""
    stat = _git(["diff", "--cached", "--stat"])
    return stat


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a commit message.")
    parser.add_argument("--type", dest="change_type", default=None,
                        choices=["fix", "feat", "refactor", "docs", "chore", "test", "style"])
    parser.add_argument("--scope", default=None)
    parser.add_argument("--body", default=None, help="Optional commit body")
    parser.add_argument("--breaking", action="store_true", help="Mark as breaking change")
    args = parser.parse_args()

    files = _staged_files()
    if not files:
        print("No staged files. Stage your changes first with: git add <files>")
        return 1

    change_type = args.change_type or _infer_type(files)
    scope = args.scope or _infer_scope(files)

    print("\n=== Staged Files ===")
    for f in files:
        print(f"  {f}")

    print("\n=== Diff Stat ===")
    print(_diff_summary())

    # Build subject line
    scope_str = f"({scope})" if scope else ""
    breaking_str = "!" if args.breaking else ""
    subject = f"{change_type}{scope_str}{breaking_str}: "

    print("\n=== Suggested Commit Message ===")
    print(f"\n  {subject}<your description here>")

    if args.body:
        print(f"\n  {args.body}")

    if args.breaking:
        print("\n  BREAKING CHANGE: <describe what breaks>")

    print("\n=== Copy-paste template ===")
    print(f"\ngit commit -m \"{subject}<description>\"")

    if args.body:
        print(f"git commit -m \"{subject}<description>\" -m \"{args.body}\"")

    return 0


if __name__ == "__main__":
    sys.exit(main())
