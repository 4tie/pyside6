#!/usr/bin/env python3
"""
check_strategy_json.py — Verify all strategy JSON parameter files have the correct format.
Freqtrade requires: {"strategy_name": "...", "params": {...}}
Fails CI if any .json file in user_data/strategies/ is malformed.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent
STRATEGIES_DIR = ROOT / "user_data" / "strategies"


def _check_file(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        errors.append(f"  INVALID JSON: {path.name} — {e}")
        return errors

    # Must have strategy_name
    if "strategy_name" not in data:
        errors.append(
            f"  MISSING 'strategy_name': {path.name}"
        )

    # Must have params dict
    if "params" not in data:
        errors.append(
            f"  MISSING 'params': {path.name}"
        )
    elif not isinstance(data["params"], dict):
        errors.append(
            f"  'params' must be a dict: {path.name}"
        )

    # strategy_name must match filename (stem)
    if "strategy_name" in data:
        expected = path.stem
        actual = data["strategy_name"]
        if actual != expected:
            errors.append(
                f"  MISMATCH: {path.name} has strategy_name='{actual}' "
                f"but filename is '{expected}'"
            )

    return errors


def main() -> int:
    if not STRATEGIES_DIR.exists():
        print("check_strategy_json: SKIP — user_data/strategies/ not found")
        return 0

    json_files = list(STRATEGIES_DIR.glob("*.json"))
    if not json_files:
        print("check_strategy_json: SKIP — no JSON files found")
        return 0

    errors: list[str] = []
    for f in sorted(json_files):
        errors.extend(_check_file(f))

    if errors:
        print("check_strategy_json: FAILED — invalid parameter files:")
        for e in errors:
            print(e)
        print("\n  Required format:")
        print('  {"strategy_name": "MyStrategy", "params": {"buy": {...}, "sell": {...}}}')
        return 1

    print(f"check_strategy_json: OK — {len(json_files)} strategy JSON files valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
