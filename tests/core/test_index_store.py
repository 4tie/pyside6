import sys, os, json
sys.path.insert(0, 'T:/ae/pyside6')
from app.core.services.backtest_results_service import BacktestResultsService
from app.core.services.run_store import RunStore, IndexStore

# Save a run (also updates index automatically)
results = BacktestResultsService.parse_backtest_zip(
    r'T:\ae\pyside6\user_data\backtest_results\backtest-result-2026-04-16_02-52-06.zip'
)
run_dir = RunStore.save(
    results=results,
    strategy_results_dir=r'T:\ae\pyside6\user_data\backtest_results\MultiMeee',
    config_path=r'T:\ae\pyside6\user_data\config\config_MultiMeee.json',
)
print("Run dir:", run_dir)
print("Files:", sorted(os.listdir(run_dir)))

# Verify index
backtest_results_dir = r'T:\ae\pyside6\user_data\backtest_results'
index_path = os.path.join(backtest_results_dir, 'index.json')
print("\nindex.json exists:", os.path.exists(index_path))

index = IndexStore.load(backtest_results_dir)
print("updated_at:", index.get("updated_at"))
print("strategies:", list(index.get("strategies", {}).keys()))

runs = IndexStore.get_strategy_runs(backtest_results_dir, "MultiMeee")
print(f"\nMultiMeee runs in index: {len(runs)}")
for r in runs:
    print(f"  {r['run_id']}  profit={r['profit_total_pct']}%  trades={r['trades_count']}")

# Test rebuild
print("\n--- Rebuild index from disk ---")
rebuilt = IndexStore.rebuild(backtest_results_dir)
print("Strategies after rebuild:", list(rebuilt.get("strategies", {}).keys()))
for strat, block in rebuilt["strategies"].items():
    print(f"  {strat}: {len(block['runs'])} run(s)")
