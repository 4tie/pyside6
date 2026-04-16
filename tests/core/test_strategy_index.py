import sys, json, os
sys.path.insert(0, 'T:/ae/pyside6')
from pathlib import Path
from app.core.services.backtest_results_service import BacktestResultsService
from app.core.services.run_store import RunStore, StrategyIndexStore

ZIP = r'T:\ae\pyside6\user_data\backtest_results\backtest-result-2026-04-16_05-02-01.zip'
STRATEGY_DIR = r'T:\ae\pyside6\user_data\backtest_results\MultiMeee'

results = BacktestResultsService.parse_backtest_zip(ZIP)
run_dir = RunStore.save(
    results=results,
    strategy_results_dir=STRATEGY_DIR,
    config_path=r'T:\ae\pyside6\user_data\config\config_MultiMeee.json',
)
print("Run dir:", run_dir)

# Verify strategy index exists
idx_path = Path(STRATEGY_DIR) / 'index.json'
print("Strategy index exists:", idx_path.exists())

idx = json.loads(idx_path.read_text(encoding='utf-8'))
print("strategy:", idx['strategy'])
print("updated_at:", idx['updated_at'])
print("runs count:", len(idx['runs']))
print()
for r in idx['runs']:
    print(f"  {r['run_id']}  profit={r['profit_total_pct']}%  trades={r['trades_count']}  saved={r['saved_at'][:19]}")

# Verify run_dir is just the folder name (not full path)
print()
print("run_dir field (should be folder name only):", idx['runs'][0]['run_dir'])
assert '/' not in idx['runs'][0]['run_dir'] and '\\' not in idx['runs'][0]['run_dir'], \
    "run_dir should be folder name only"

# Test rebuild
print()
print("--- Testing rebuild ---")
rebuilt = StrategyIndexStore.rebuild(STRATEGY_DIR, 'MultiMeee')
print("Rebuilt runs:", len(rebuilt['runs']))

print()
print("All checks passed.")
