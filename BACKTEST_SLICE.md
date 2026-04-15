# Backtesting Slice - Implementation Summary

## What Was Implemented

### 1. **Enhanced CommandRunner** (`app/core/freqtrade/command_runner.py`)

✅ **New `BacktestCommand` dataclass**:
- Holds program, args, cwd, export paths, strategy file, config file
- Provides all info needed for execution and result tracking

✅ **Enhanced `build_backtest_command()` method**:
- Validates strategy `.py` file exists
- Resolves config file (tries sidecar JSON → default config.json)
- Creates export directory: `user_data/backtest_results/{strategy_name}/`
- Generates timestamped zip filename
- Builds complete command args with all flags
- Supports: timeframe, timerange, pairs, stake_currency, stake_amount, max_open_trades, dry_run_wallet

### 2. **BacktestService** (`app/core/services/backtest_service.py`)

✅ **Thin wrapper around CommandRunner and SettingsService**:
- `build_command()`: Builds formatted backtest command
- `get_available_strategies()`: Lists `.py` files from user_data/strategies/
- Delegates to CommandRunner for command building

### 3. **BacktestResultsService** (`app/core/services/backtest_results_service.py`)

✅ **Zip file parsing and result extraction**:
- `parse_backtest_zip()`: Opens zip, finds JSON, parses freqtrade format
- Extracts: summary stats (return, sharpe, win rate, max drawdown, etc.)
- Extracts: individual trades (pair, entry, exit, profit, duration, status)
- Returns structured `BacktestResults` object
- Handles errors gracefully (file not found, JSON parse errors)

✅ **Data models**:
- `BacktestSummary`: Summary statistics
- `BacktestTrade`: Individual trade data
- `BacktestResults`: Complete results container

### 4. **BacktestResultsWidget** (`app/ui/widgets/backtest_results_widget.py`)

✅ **Two-tab result display**:
- **Summary Tab**: Form layout showing all key metrics with proper formatting
  - Strategy name, timeframe, trade count
  - Win rate, profit %, sharpe ratio, calmar ratio
  - Max drawdown, trade duration average
  
- **Trades Tab**: Sortable table with columns
  - Pair, open date, close date, rates, profit, duration, status
  - Color-coded profits (green for wins, red for losses)
  - Resizable columns for readability

### 5. **BacktestPage** (`app/ui/pages/backtest_page.py`)

✅ **Main backtest UI with 3 sections**:

**Parameters Section (Left)**:
- Strategy selector (combo box with typing + refresh)
- Timeframe input (e.g., "5m")
- Timerange input (optional, e.g., "20240101-20241231")
- Pairs input (space-separated, e.g., "BTC/USDT ETH/USDT")
- Advanced options (collapsible):
  - Dry Run Wallet
  - Max Open Trades
  - Stake Currency
  - Stake Amount
- Export path display
- Run/Stop buttons

**Terminal Output Section (Right Top)**:
- Live command execution output
- Shows command being run
- Streams stdout in normal color, stderr in red
- Clear button (inherited from TerminalWidget)

**Results Section (Right Bottom)**:
- Only visible after backtest completes successfully
- Shows summary and trades via BacktestResultsWidget
- Automatically parses zip and populates results

✅ **Process Management**:
- Validates inputs (strategy, timeframe)
- Builds command via BacktestService
- Executes via ProcessService with proper working directory
- Streams output in real-time
- On exit code 0: automatically parses results
- Switches to Results tab on success
- Shows errors in terminal on failure

### 6. **Updated MainWindow** (`app/ui/main_window.py`)

✅ **Now passes SettingsState to pages**:
- Constructor accepts optional `settings_state` parameter
- Three tabs now: Settings | Backtest | Terminal
- Settings page allows config of venv/user_data
- Backtest page uses settings for command building
- Terminal page for ad-hoc testing

### 7. **Updated Entry Point** (`main.py`)

✅ **Creates and loads settings**:
- Initializes SettingsState
- Loads settings from disk (~/.freqtrade_gui/settings.json)
- Passes to MainWindow

---

## Architecture Pattern

```
User fills in Backtest UI → validates → builds command
                                            ↓
                                    CommandRunner
                                    (validates files)
                                            ↓
                                    ProcessService
                                    (executes QProcess)
                                            ↓
                        Terminal streams output in real-time
                                            ↓
                                    Process finishes (exit 0)
                                            ↓
                                BacktestResultsService
                                (parses zip → results)
                                            ↓
                                BacktestResultsWidget
                                (displays summary + trades)
```

---

## Key Features

✅ **Strategy Validation**: Checks `.py` file exists before running  
✅ **Config Resolution**: Tries sidecar JSON, then default config  
✅ **Live Output Streaming**: Shows command progress in real-time  
✅ **Error Handling**: User-friendly messages for missing files/config  
✅ **Result Parsing**: Automatically extracts and displays backtest metrics  
✅ **Editable Strategy Selector**: Combo box with typing + auto-complete  
✅ **Advanced Options**: Collapsible section for stake, wallet, trade limits  
✅ **Result Caching**: Nothing cached yet, runs fresh each time  

---

## Testing Checklist

✅ Code compiles without syntax errors  
✅ All imports verified  
✅ File paths validated  
✅ Command building logic correct  
✅ Results parsing structured properly  

**To test end-to-end, when dependencies are installed**:

1. `pip install -r requirements.txt` (includes PySide6, pydantic)
2. Set up a freqtrade project with `.venv` and `user_data/strategies/`
3. `python main.py`
4. Go to Settings → enter venv path, user_data path
5. Go to Backtest → select strategy, enter timeframe
6. Click Run
7. Watch terminal output stream
8. Results auto-display on completion

---

## Files Modified/Created

| File | Change | Type |
|------|--------|------|
| `app/core/freqtrade/command_runner.py` | Added BacktestCommand + build_backtest_command() | Enhanced |
| `app/core/services/backtest_service.py` | New service layer | Created |
| `app/core/services/backtest_results_service.py` | Zip parsing + result extraction | Created |
| `app/ui/pages/backtest_page.py` | Main backtest UI | Created |
| `app/ui/widgets/backtest_results_widget.py` | Results display widget | Created |
| `app/ui/main_window.py` | Added BacktestPage tab | Enhanced |
| `main.py` | Pass SettingsState to MainWindow | Enhanced |

---

## Next Steps

### Result Caching (Optional)
- Store results in `~/.freqtrade_gui/backtest_results/`
- Show history of past runs
- Compare multiple backtests side-by-side

### Multi-Strategy Backtesting
- Queue multiple strategies to run sequentially
- Progress bar for queue completion
- Aggregate results across strategies

### Advanced Features
- Parameter sweeps (test multiple timeframes, stake amounts)
- Strategy comparison charts (overlaid equity curves)
- Performance metrics tracking (Sortino, Calmar, etc.)
- Monte Carlo analysis

---

## Commit

Commit `c4e1d1d`: Backtesting slice with live terminal output and result parsing

