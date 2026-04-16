#!/usr/bin/env python3
"""
check_docs.py — Verify all required documentation files exist.
Fails CI if any required doc is missing.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent

REQUIRED_DOCS = [
    "data/docs/PRODUCT.md",
    "data/docs/ARCHITECTURE.md",
    "data/docs/STRUCTURE.md",
    "data/docs/WORKFLOW.md",
    "data/docs/CHANGELOG_RULES.md",
    "data/docs/CHANGELOG.md",
    "data/docs/AGENTS.md",
]

REQUIRED_RULES = [
    "data/rules/guidelines.md",
    "data/rules/product.md",
    "data/rules/structure.md",
    "data/rules/tech.md",
]


def main() -> int:
    errors: list[str] = []

    for path in REQUIRED_DOCS + REQUIRED_RULES:
        full = ROOT / path
        if not full.exists():
            errors.append(f"  MISSING: {path}")

    if errors:
        print("check_docs: FAILED — missing required files:")
        for e in errors:
            print(e)
        return 1

    print(f"check_docs: OK — {len(REQUIRED_DOCS + REQUIRED_RULES)} required files present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
