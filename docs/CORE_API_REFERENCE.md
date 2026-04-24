# Core API Reference

This document provides a comprehensive reference for the public API functions used by the UI and web layers in `app/core`.

## Table of Contents

- [Services](#services)
  - [BacktestService](#backtestservice)
  - [OptimizeService](#optimizeservice)
  - [DownloadDataService](#downloaddataservice)
  - [ProcessService](#processservice)
  - [LoopService](#loopservice)
  - [AIAdvisorService](#aiadvisorservice)
  - [StrategyConfigService](#strategyconfigservice)
  - [ImproveService](#improveservice)
  - [ResultsDiagnosisService](#resultsdiagnosisservice)
  - [RuleSuggestionService](#rulesuggestionservice)
  - [ExitReasonAnalysisService](#exitreasonanalysisservice)
- [Backtests](#backtests)
  - [IndexStore](#indexstore)
  - [StrategyIndexStore](#strategyindexstore)
  - [RunStore](#runstore)
  - [Parser Functions](#parser-functions)
- [Freqtrade](#freqtrade)
  - [Command Builders](#command-builders)
  - [Path Resolvers](#path-resolvers)
- [AI Tools](#ai-tools)
  - [Tool Registration](#tool-registration)
- [Utils](#utils)
  - [Logging](#logging)

---

## Services

### BacktestService

Service for running and managing backtests.

```python
from app.core.services.backtest_service import BacktestService
```

**Methods:**
- `run_backtest(config, settings) -> BacktestResults`: Execute a backtest with the given configuration.
- `parse_results(zip_path) -> BacktestResults`: Parse backtest results from a zip file.

---

### OptimizeService

Service for hyperparameter optimization.

```python
from app.core.services.optimize_service import OptimizeService
```

**Methods:**
- `run_hyperopt(config, settings) -> OptimizeResult`: Execute hyperparameter optimization.
- `get_suggestion(strategy, user_data_path) -> HyperoptSuggestion`: Get optimization suggestions.

---

### DownloadDataService

Service for downloading market data.

```python
from app.core.services.download_data_service import DownloadDataService
```

**Methods:**
- `download_data(timeframe, timerange, pairs, settings) -> DownloadResult`: Download market data for the given parameters.

---

### ProcessService

Service for managing external processes.

```python
from app.core.services.process_service import ProcessService
```

**Methods:**
- `start_process(command, cwd) -> ProcessHandle`: Start an external process.
- `stop_process(handle) -> None`: Stop a running process.
- `get_process_status(handle) -> ProcessStatus`: Get the status of a process.

---

### LoopService

Service for auto-optimization loop management and scoring.

```python
from app.core.services.loop_service import LoopService
```

**Public Functions:**

#### `calculate_robust_score(input: RobustScoreInput) -> RobustScore`
Compute a multi-dimensional robust score for a backtest result bundle.

**Formula:**
```
robust_score = profitability_score + consistency_score + stability_score - fragility_score
```

**Parameters:**
- `input`: RobustScoreInput bundling in-sample summary, optional fold summaries, optional stress summary, and optional pair profit distribution.

**Returns:**
- `RobustScore` with total and four component scores.

---

#### `create_diagnosis_input(in_sample_results: BacktestResults, oos_results: Optional[BacktestResults] = None, fold_results: Optional[List[BacktestResults]] = None) -> DiagnosisInput`
Build a DiagnosisInput bundle from parsed backtest results.

**Parameters:**
- `in_sample_results`: In-sample backtest results.
- `oos_results`: Optional out-of-sample backtest results.
- `fold_results`: Optional list of fold backtest results.

**Returns:**
- `DiagnosisInput` bundle for diagnosis service.

---

#### `create_score_input(in_sample_results: BacktestResults, fold_results: Optional[List[BacktestResults]] = None, stress_results: Optional[BacktestResults] = None) -> RobustScoreInput`
Build a RobustScoreInput bundle from parsed backtest results.

**Parameters:**
- `in_sample_results`: In-sample backtest results.
- `fold_results`: Optional list of fold backtest results.
- `stress_results`: Optional stress test backtest results.

**Returns:**
- `RobustScoreInput` bundle for robust score calculation.

---

#### `check_targets_met(summary: BacktestSummary, config: LoopConfig) -> bool`
Return True if all profitability targets in config are satisfied.

**Parameters:**
- `summary`: Backtest summary to evaluate.
- `config`: Loop configuration containing target thresholds.

**Returns:**
- `bool`: True if every target is met simultaneously.

---

### AIAdvisorService

Service for AI-powered trading advice.

```python
from app.core.services.ai_advisor_service import AIAdvisorService
```

**Methods:**
- `get_advice(backtest_results, strategy) -> AdviceResult`: Get AI-generated trading advice.

---

### StrategyConfigService

Service for strategy configuration management.

```python
from app.core.services.strategy_config_service import StrategyConfigService
```

**Methods:**
- `load_config(strategy_path) -> StrategyConfig`: Load strategy configuration.
- `save_config(strategy_path, config) -> None`: Save strategy configuration.

---

### ImproveService

Service for strategy improvement suggestions.

```python
from app.core.services.improve_service import ImproveService
```

**Methods:**
- `analyze_strategy(strategy_path, backtest_results) -> ImprovementSuggestions`: Analyze strategy and provide improvement suggestions.

---

### ResultsDiagnosisService

Service for diagnosing backtest results.

```python
from app.core.services.results_diagnosis_service import ResultsDiagnosisService
```

**Methods:**
- `diagnose(diagnosis_input) -> DiagnosisResult`: Diagnose backtest results and provide insights.

---

### RuleSuggestionService

Service for suggesting trading rules.

```python
from app.core.services.rule_suggestion_service import RuleSuggestionService
```

**Methods:**
- `suggest_rules(backtest_results) -> RuleSuggestions`: Suggest trading rules based on backtest results.

---

### ExitReasonAnalysisService

Service for analyzing trade exit reasons.

```python
from app.core.services.exit_reason_analysis_service import ExitReasonAnalysisService
```

**Methods:**
- `analyze(trades: List[BacktestTrade]) -> ExitReasonAnalysis`: Analyze exit reasons from trades.

---

## Backtests

### IndexStore

Manages the global backtest index across all strategies.

```python
from app.core.backtests.results_index import IndexStore
```

**Static Methods:**

#### `update(backtest_results_dir: str, run_id: str, run_dir: Path, results: BacktestResults, version_id: Optional[str] = None) -> None`
Add or update a run entry in the global index.

#### `load(backtest_results_dir: str) -> dict`
Load the full global index.

#### `get_strategy_runs(backtest_results_dir: str, strategy: str) -> List[Dict]`
Return all run entries for a strategy, newest first.

#### `get_all_strategies(backtest_results_dir: str) -> List[str]`
Return sorted list of strategy names in the index.

#### `rebuild(backtest_results_dir: str) -> dict`
Rebuild global index by scanning all run folders.

---

### StrategyIndexStore

Manages per-strategy backtest indices.

```python
from app.core.backtests.results_index import StrategyIndexStore
```

**Static Methods:**

#### `update(strategy_dir: Path, run_id: str, run_dir: Path, results: BacktestResults, version_id: Optional[str] = None) -> None`
Add or update a run entry in the strategy-level index.

#### `load(strategy_dir: str, strategy: str) -> dict`
Load the strategy-level index.

#### `rebuild(strategy_dir: str, strategy: str) -> dict`
Rebuild strategy index by scanning run folders.

---

### RunStore

Persists and loads backtest runs.

```python
from app.core.backtests.results_store import RunStore
```

**Static Methods:**

#### `save(strategy_results_dir: str, run_id: str, results: BacktestResults, config_path: Optional[str] = None, run_params: Optional[dict] = None, version_id: Optional[str] = None) -> Path`
Save a backtest run to disk.

**Parameters:**
- `strategy_results_dir`: Directory to save the run.
- `run_id`: Unique identifier for the run.
- `results`: BacktestResults to save.
- `config_path`: Optional path to config file for snapshot.
- `run_params`: Optional run parameters.
- `version_id`: Optional version identifier.

**Returns:**
- `Path`: Directory where the run was saved.

#### `load_run(run_dir: Path) -> BacktestResults`
Load a backtest run from disk.

---

### Parser Functions

Functions for parsing backtest results.

```python
from app.core.backtests.results_parser import parse_backtest_results_from_zip, parse_backtest_results_from_json
```

#### `parse_backtest_results_from_zip(zip_path: str) -> BacktestResults`
Parse a freqtrade backtest zip and return structured results.

**Parameters:**
- `zip_path`: Path to the .zip file written by freqtrade.

**Returns:**
- `BacktestResults`: Parsed backtest results.

**Raises:**
- `FileNotFoundError`: If zip does not exist.
- `ValueError`: If JSON is malformed or missing.

---

#### `parse_backtest_results_from_json(json_path: str) -> BacktestResults`
Parse a bt-*.result.json file directly.

**Parameters:**
- `json_path`: Path to the result JSON file.

**Returns:**
- `BacktestResults`: Parsed backtest results.

**Raises:**
- `FileNotFoundError`: If file does not exist.
- `ValueError`: If JSON is malformed.

---

## Freqtrade

### Command Builders

Functions for building freqtrade commands.

```python
from app.core.freqtrade.runners.base_runner import create_command, format_command_string
from app.core.freqtrade.runners.backtest_runner import create_backtest_command
from app.core.freqtrade.runners.optimize_runner import create_optimize_command
from app.core.freqtrade.runners.download_data_runner import create_download_data_command
```

#### `create_command(settings: AppSettings, *ft_args: str) -> RunCommand`
Build a freqtrade command using python -m freqtrade or direct executable.

**Parameters:**
- `settings`: AppSettings with python/freqtrade paths configured.
- `*ft_args`: freqtrade subcommand and flags.

**Returns:**
- `RunCommand`: Command ready for ProcessService.

**Raises:**
- `ValueError`: If no valid execution method is configured.

---

#### `format_command_string(command: Sequence[str]) -> str`
Render a tokenized command for display/copy without re-splitting it later.

---

#### `create_backtest_command(settings, strategy_name, timeframe, timerange=None, pairs=None, max_open_trades=None, dry_run_wallet=None, extra_flags=None) -> BacktestRunCommand`
Build a freqtrade backtesting command.

---

#### `create_optimize_command(settings, strategy_name, timeframe, epochs, timerange=None, pairs=None, spaces=None, hyperopt_loss=None, extra_flags=None) -> OptimizeRunCommand`
Build a freqtrade hyperopt command.

---

#### `create_download_data_command(settings, timeframe, timerange=None, pairs=None) -> RunCommand`
Build a freqtrade download-data command.

---

### Path Resolvers

Functions for resolving filesystem paths.

```python
from app.core.freqtrade.resolvers.runtime_resolver import find_run_paths, find_user_data_directory, find_project_directory
from app.core.freqtrade.resolvers.strategy_resolver import find_strategy_file_path, list_available_strategies
from app.core.freqtrade.resolvers.config_resolver import find_config_file_path
```

#### `find_run_paths(settings: AppSettings, strategy_name: Optional[str] = None) -> ResolvedRunPaths`
Resolve user_data, config, and optional strategy paths for a freqtrade run.

---

#### `find_user_data_directory(settings: AppSettings) -> Path`
Resolve and validate the configured user_data directory.

---

#### `find_project_directory(settings: AppSettings, user_data_dir: Path) -> Path`
Resolve the working directory used for freqtrade execution.

---

#### `find_strategy_file_path(user_data: Path, strategy_name: str) -> Path`
Resolve the absolute path to a strategy .py file.

---

#### `list_available_strategies(user_data: Path) -> List[str]`
List available strategy names from user_data/strategies/.

---

#### `find_config_file_path(user_data: Path, strategy_name: Optional[str] = None) -> Path`
Resolve the freqtrade config.json to use for a run.

---

## AI Tools

### Tool Registration

Functions for registering AI tools.

```python
from app.core.ai.tools.backtest_tools import register_backtest_tools
from app.core.ai.tools.app_tools import register_app_tools
from app.core.ai.tools.strategy_tools import register_strategy_tools
```

#### `register_backtest_tools(registry: ToolRegistry, settings=None) -> None`
Register all backtest tools into the given registry.

**Tools registered:**
- `get_latest_backtest_result`: Most recent run summary
- `load_run_history`: List of run summaries for a strategy
- `compare_runs`: Side-by-side metric comparison of two runs

---

#### `register_app_tools(registry: ToolRegistry, settings=None, event_journal=None) -> None`
Register all app tools into the given registry.

**Tools registered:**
- `get_application_status`: Current app status
- `read_recent_log_lines`: Recent application log lines
- `get_most_recent_error`: Most recent error from logs
- `list_recent_application_events`: Recent events from event journal

---

#### `register_strategy_tools(registry: ToolRegistry, settings=None) -> None`
Register all strategy tools into the given registry.

**Tools registered:**
- `list_available_strategies`: List all strategy names
- `read_strategy_source_code`: Read strategy source code
- `read_strategy_parameters`: Read strategy parameters

---

## Utils

### Logging

Logging configuration and logger retrieval.

```python
from app.core.utils.app_logger import configure_logging, get_logger
```

#### `configure_logging(log_dir_path: Optional[str] = None) -> logging.Logger`
Configure application logging.

**Parameters:**
- `log_dir_path`: Path to write log files. Defaults to data/log/ next to main.py.

**Returns:**
- `logging.Logger`: Root logger instance.

---

#### `get_logger(name: Optional[str] = None) -> logging.Logger`
Return a child logger under freqtrade_gui.<name>.

**Parameters:**
- `name`: Sub-module name e.g. 'ui.backtest_page', 'services.backtest', 'process'.

**Returns:**
- `logging.Logger`: Logger instance.

---

## Notes

- All functions follow snake_case naming convention
- Classes follow PascalCase naming convention
- Private helper functions (prefixed with `_`) are not part of the public API
- This documentation reflects the renamed functions after the core cleanup refactoring
