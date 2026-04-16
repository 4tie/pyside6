#!/usr/bin/env python3
"""
check_layer_violations.py — Verify services never import UI code.
Fails CI if any file in app/core/ imports from app/ui/.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent
CORE_DIR = ROOT / "app" / "core"


def _check_file(path: Path) -> list[str]:
    violations: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as e:
        violations.append(f"  SYNTAX ERROR in {path.relative_to(ROOT)}: {e}")
        return violations

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = ""
            if isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if "app.ui" in alias.name:
                        violations.append(
                            f"  VIOLATION: {path.relative_to(ROOT)}:{node.lineno} "
                            f"imports '{alias.name}'"
                        )
            if "app.ui" in module:
                violations.append(
                    f"  VIOLATION: {path.relative_to(ROOT)}:{node.lineno} "
                    f"imports from '{module}'"
                )
    return violations


def main() -> int:
    violations: list[str] = []
    files = list(CORE_DIR.rglob("*.py"))

    for f in files:
        violations.extend(_check_file(f))

    if violations:
        print("check_layer_violations: FAILED — services importing UI code:")
        for v in violations:
            print(v)
        return 1

    print(f"check_layer_violations: OK — {len(files)} core files checked, no UI imports")
    return 0


if __name__ == "__main__":
    sys.exit(main())
