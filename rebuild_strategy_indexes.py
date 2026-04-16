import sys
sys.path.insert(0, "T:/ae/pyside6")
from pathlib import Path
from app.core.services.run_store import StrategyIndexStore

br = Path(r"T:\ae\pyside6\user_data\backtest_results")
for strat_dir in sorted(br.iterdir()):
    if not strat_dir.is_dir():
        continue
    run_dirs = [d for d in strat_dir.iterdir() if d.is_dir() and d.name.startswith("run_")]
    if not run_dirs:
        continue
    idx_path = strat_dir / "index.json"
    if not idx_path.exists():
        result = StrategyIndexStore.rebuild(str(strat_dir), strat_dir.name)
        print(f"Built {strat_dir.name}/index.json — {len(result['runs'])} run(s)")
    else:
        import json
        data = json.loads(idx_path.read_text(encoding="utf-8"))
        print(f"Exists {strat_dir.name}/index.json — {len(data.get('runs', []))} run(s)")
