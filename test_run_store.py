import sys, os
sys.path.insert(0, 'T:/ae/pyside6')
from app.core.services.backtest_results_service import BacktestResultsService
from app.core.services.run_store import RunStore

results = BacktestResultsService.parse_backtest_zip(
    r'T:\ae\pyside6\user_data\backtest_results\backtest-result-2026-04-16_02-52-06.zip'
)
run_dir = RunStore.save(
    results=results,
    strategy_results_dir=r'T:\ae\pyside6\user_data\backtest_results\MultiMeee',
    config_path=r'T:\ae\pyside6\user_data\config\config_MultiMeee.json',
)
print('Run dir:', run_dir)
for f in sorted(os.listdir(run_dir)):
    size = os.path.getsize(os.path.join(run_dir, f))
    print(f'  {f}  ({size} bytes)')
