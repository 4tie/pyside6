import json
from pathlib import Path

user_data = Path("user_data")
strategy_name = "MultiMeee"
strategies_dir = user_data / "strategies"

sidecar_path = strategies_dir / f"{strategy_name}.json"
named_path   = user_data / "config" / f"config_{strategy_name}.json"
py_path      = strategies_dir / f"{strategy_name}.py"

print("=== Config Resolution Chain (--config candidates) ===")
candidates = [
    ("1. sidecar",        sidecar_path),
    ("2. project root",   Path("config.json")),
    ("3. user_data root", user_data / "config.json"),
]
print(f"  [reference only, never --config]: {named_path}  exists={named_path.exists()}")
print()

resolved = None
for label, path in candidates:
    exists = path.exists()
    tag = " <-- SELECTED" if exists and resolved is None else ""
    if exists and resolved is None:
        resolved = path
    print(f"  {label}: {path}  exists={exists}{tag}")

print()
if resolved is None:
    print("ERROR: No config file found!")
    raise SystemExit(1)
print(f"Resolved: {resolved}")

# Source of truth: sidecar if present, else named config
if sidecar_path.exists():
    src = json.loads(sidecar_path.read_text(encoding="utf-8"))
    src_label = f"sidecar ({sidecar_path})"
else:
    src = json.loads(named_path.read_text(encoding="utf-8"))
    src_label = f"config/named ({named_path})"

named = json.loads(named_path.read_text(encoding="utf-8"))
py_text = py_path.read_text(encoding="utf-8")

print()
print(f"=== Source of truth: {src_label} ===")
skip = {"minimal_roi", "INTERFACE_VERSION", "buy_params", "sell_params"}
for k, v in src.items():
    if k not in skip:
        print(f"  {k}: {v}")

all_ok = True

print()
print("=== Validation: source of truth vs config_MultiMeee.json ===")
param_keys = ["buy_ma_count", "buy_ma_gap", "sell_ma_count", "sell_ma_gap",
              "timeframe", "stoploss", "trailing_stop"]
for k in param_keys:
    sv, nv = src.get(k), named.get(k)
    ok = sv == nv
    if not ok:
        all_ok = False
    print(f"  {'OK' if ok else 'MISMATCH'}  {k}: source={sv}  config={nv}")

print()
print("=== Validation: .py defaults vs source of truth ===")
py_defaults = {
    "buy_ma_count":  5,
    "buy_ma_gap":    13,
    "sell_ma_count": 14,
    "sell_ma_gap":   66,
}
for k, py_val in py_defaults.items():
    sc_val = src.get(k)
    match = py_val == sc_val
    note = "(matches)" if match else f"(config overrides .py default {py_val} -> {sc_val})"
    print(f"  {k}: .py default={py_val}  config={sc_val}  {note}")

print()
print("=== Validation: .py structural checks ===")
struct_checks = {
    "class MultiMeee(IStrategy) defined": "class MultiMeee(IStrategy)" in py_text,
    "timeframe = '4h'":                   'timeframe = "4h"' in py_text,
    "stoploss = -0.345":                  "stoploss = -0.345" in py_text,
    "minimal_roi[0] = 0.523":             '"0": 0.523' in py_text,
    "populate_entry_trend defined":       "def populate_entry_trend" in py_text,
    "populate_exit_trend defined":        "def populate_exit_trend" in py_text,
    "populate_indicators defined":        "def populate_indicators" in py_text,
}
for k, v in struct_checks.items():
    if not v:
        all_ok = False
    print(f"  {'OK' if v else 'MISSING'}  {k}")

print()
print("All checks passed." if all_ok else "VALIDATION FAILED — see mismatches above.")
