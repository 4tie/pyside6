import sys
sys.path.insert(0, 'T:/ae/pyside6')
from app.core.utils.app_logger import setup_logging, get_logger

setup_logging(r'T:\ae\pyside6\user_data')

get_logger('startup').info('=' * 60)
get_logger('startup').info('Freqtrade GUI starting')
get_logger('startup').info('Python     : 3.12.0')
get_logger('startup').info('user_data  : T:/ae/pyside6/user_data')
get_logger('startup').info('=' * 60)
get_logger('settings').debug('Settings loaded from ~/.freqtrade_gui/settings.json')
get_logger('settings').info('Settings saved to ~/.freqtrade_gui/settings.json')
get_logger('settings').debug('Saved: python=T:/venv/Scripts/python.exe venv=T:/venv user_data=T:/ae/pyside6/user_data')
get_logger('settings').info('Validating settings...')
get_logger('settings').info('Validation result: valid=True python=True freqtrade=True user_data=True')
get_logger('settings').info('  Python 3.12.0')
get_logger('settings').info('  freqtrade 2024.1')
get_logger('backtest').info('Backtest requested | strategy=MultiMeee | timeframe=5m | timerange=20250101-20260101 | pairs=[ADA/USDT, ETH/USDT]')
get_logger('backtest').info('Command built | strategy=MultiMeee | config=user_data/strategies/MultiMeee.json | export=user_data/backtest_results/MultiMeee/MultiMeee_20260416_043238.backtest.zip')
get_logger('process').info('Process started | cmd=python -m freqtrade backtesting --strategy MultiMeee | cwd=T:/ae/pyside6')
get_logger('process').debug('stdout chunk: 1024 bytes')
get_logger('process').debug('stderr chunk: 256 bytes')
get_logger('process').info('Backtest process finished | exit_code=0')
get_logger('results').debug('Parsing zip: backtest-result-2026-04-16_05-02-01.zip | json_file=backtest-result-2026-04-16_05-02-01.json')
get_logger('results').info('Zip parsed | strategy=MultiMeee | trades=231 | profit=-4.6510%')
get_logger('run_store').info('Saving run | id=run_2026-04-16_05-02-01_abc123 | strategy=MultiMeee | trades=231 | profit=-4.6510%')
get_logger('run_store').debug('Index updated | strategy=MultiMeee | run_id=run_2026-04-16_05-02-01_abc123')
get_logger('run_store').info('Run saved -> T:/ae/pyside6/user_data/backtest_results/MultiMeee/run_2026-04-16_05-02-01_abc123')
get_logger('backtest').info('Index rebuild: scanning 11 zip(s) in backtest_results/')
get_logger('backtest').debug('Skipping already-indexed zip: backtest-result-2026-04-16_02-52-06.zip')
get_logger('backtest').info('Index rebuild complete: imported=1 skipped=10')
get_logger('backtest').info('Loading run | id=run_2026-04-16_05-02-01_abc123 | strategy=MultiMeee | profit=-4.6510%')
get_logger('backtest').info('Run loaded from disk | strategy=MultiMeee | trades=231')

# Print last 30 lines of log file
log_path = r'T:\ae\pyside6\user_data\logs\app.log'
with open(log_path, encoding='utf-8') as f:
    lines = f.readlines()
print(f"\n=== Last {min(30, len(lines))} lines of {log_path} ===")
for line in lines[-30:]:
    print(line.rstrip())
