# Bugfix Requirements Document

## Introduction

When running a candidate backtest in the Improve tab, freqtrade rejects the strategy parameter
file with `ERROR - Invalid parameter file provided.` The root cause is that three methods in
`ImproveService` write the flat `params.json` format directly as the strategy JSON file, but
freqtrade expects a nested format with a `strategy_name` key, a `params` sub-object, and
metadata fields (`ft_stratparam_v`, `export_time`).

The flat format stored in `params.json` looks like:
```json
{ "buy_params": {...}, "sell_params": {...}, "minimal_roi": {...}, "stoploss": -0.245 }
```

The freqtrade strategy JSON format that freqtrade actually loads looks like:
```json
{
  "strategy_name": "MultiMeee",
  "params": {
    "buy": {...},
    "sell": {...},
    "roi": {"0": 0.109, ...},
    "stoploss": {"stoploss": -0.245},
    "max_open_trades": {"max_open_trades": 2},
    "trailing": {...}
  },
  "ft_stratparam_v": 1,
  "export_time": "2026-04-16 11:16:55.409518+00:00"
}
```

Beyond the core format bug, several related workflow gaps exist: the error message shown to the
user is generic rather than surfacing the specific freqtrade error; the sandbox directory is not
cleaned up after a successful accept; `load_baseline_params` has no fallback when `params.json`
is missing; and the diagnosis and suggestion services are missing rules for profit factor and
expectancy.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN `prepare_sandbox` writes the candidate config to `{sandbox_dir}/{strategy_name}.json`
THEN the system writes the flat `params.json` format (e.g. `{"stoploss": -0.245, "minimal_roi":
{...}}`), which freqtrade rejects with `ERROR - Invalid parameter file provided.`

1.2 WHEN `accept_candidate` writes the candidate config to the live strategy JSON THEN the
system writes the flat format, corrupting the live strategy parameter file and breaking future
freqtrade runs.

1.3 WHEN `rollback` writes `baseline_params` to the live strategy JSON THEN the system writes
the flat format, corrupting the live strategy parameter file.

1.4 WHEN the candidate backtest process exits with a non-zero code THEN the system displays the
generic message "Candidate backtest failed — check the terminal output above for errors" without
extracting the specific error from the terminal output (which is accessible via
`self._terminal.get_output()`).

1.5 WHEN `accept_candidate` succeeds THEN the system leaves the sandbox directory on disk
instead of cleaning it up, accumulating stale directories under
`{user_data_path}/strategies/_improve_sandbox/`.

1.6 WHEN `load_baseline_params` is called and `params.json` is missing or empty AND a
`strategy_name` is provided THEN the system returns an empty dict without attempting to load
params from the live strategy JSON at `{user_data_path}/strategies/{strategy_name}.json`.

1.7 WHEN `ResultsDiagnosisService.diagnose` evaluates a summary with `profit_factor < 1.0`
(and `profit_factor > 0.0`) THEN the system does not flag it as an issue.

1.8 WHEN `ResultsDiagnosisService.diagnose` evaluates a summary with `expectancy < 0.0` THEN
the system does not flag it as an issue.

1.9 WHEN `RuleSuggestionService` receives a `profit_factor_low` issue THEN the system logs a
warning and returns no suggestion.

1.10 WHEN `RuleSuggestionService` receives an `expectancy_negative` issue THEN the system logs
a warning and returns no suggestion.

1.11 WHEN `IssueBadge` renders a `profit_factor_low` or `expectancy_negative` issue THEN the
system falls back to the default grey color and ⚪ icon instead of the intended severity color.

### Expected Behavior (Correct)

2.1 WHEN `prepare_sandbox` writes the candidate config to `{sandbox_dir}/{strategy_name}.json`
THEN the system SHALL write the freqtrade nested format by:
  - Reading the live strategy JSON at `{user_data_path}/strategies/{strategy_name}.json` as the
    base (to preserve `trailing`, `buy`, `sell`, and other fields not tracked in `params.json`)
  - Merging the flat candidate config into the nested `params` sub-object using the key mapping:
    - `stoploss` (scalar) → `params["stoploss"]["stoploss"]`
    - `max_open_trades` (scalar) → `params["max_open_trades"]["max_open_trades"]`
    - `minimal_roi` (dict) → `params["roi"]`
    - `buy_params` (dict) → `params["buy"]`
    - `sell_params` (dict) → `params["sell"]`
  - Updating `export_time` to the current UTC timestamp
  - Writing the merged dict as the sandbox JSON file

2.2 WHEN `accept_candidate` writes the candidate config to the live strategy JSON THEN the
system SHALL write the freqtrade nested format using the same merge logic as 2.1, preserving
trailing stop and other fields not present in the flat candidate config.

2.3 WHEN `rollback` writes `baseline_params` to the live strategy JSON THEN the system SHALL
write the freqtrade nested format using the same merge logic as 2.1, preserving trailing stop
and other fields not present in the flat baseline params.

2.4 WHEN the candidate backtest process exits with a non-zero code THEN the system SHALL call
`self._terminal.get_output()` to retrieve the terminal text, scan it for known freqtrade error
phrases (e.g. `"Invalid parameter file"`, `"Strategy not found"`, `"No data found"`,
`"Configuration error"`), and include the first matched phrase in the status label message. If
no known phrase is matched, the message SHALL fall back to the existing generic text.

2.5 WHEN `accept_candidate` succeeds THEN the system SHALL clean up the sandbox directory by
calling `self._improve_service.reject_candidate(self._sandbox_dir)` before clearing
`self._sandbox_dir`.

2.6 WHEN `load_baseline_params` is called and `params.json` is missing or empty AND
`strategy_name` is provided THEN the system SHALL attempt to load params from the live strategy
JSON at `{user_data_path}/strategies/{strategy_name}.json` and convert it to the flat format
using the reverse key mapping:
  - `params["stoploss"]["stoploss"]` → `stoploss` (scalar)
  - `params["max_open_trades"]["max_open_trades"]` → `max_open_trades` (scalar)
  - `params["roi"]` → `minimal_roi` (dict)
  - `params["buy"]` → `buy_params` (dict)
  - `params["sell"]` → `sell_params` (dict)
  If the live strategy JSON also does not exist, the system SHALL return an empty dict.

2.7 WHEN `ResultsDiagnosisService.diagnose` evaluates a summary where `profit_factor` is
greater than zero and less than 1.0 THEN the system SHALL append a `profit_factor_low` issue
with the description `"Profit factor {value:.2f} is below 1.0 — losses exceed gains over the
backtest period."`.

2.8 WHEN `ResultsDiagnosisService.diagnose` evaluates a summary where `expectancy` is less than
0.0 THEN the system SHALL append an `expectancy_negative` issue with the description
`"Expectancy {value:.4f} is negative — the average trade loses money."`.

2.9 WHEN `RuleSuggestionService` receives a `profit_factor_low` issue THEN the system SHALL
return an advisory `ParameterSuggestion` with `parameter="entry_conditions"`,
`is_advisory=True`, `reason="Profit factor below 1.0 — losses exceed gains"`, and
`expected_effect="Review entry/exit conditions to improve trade quality"`.

2.10 WHEN `RuleSuggestionService` receives an `expectancy_negative` issue THEN the system SHALL
return an advisory `ParameterSuggestion` with `parameter="entry_filters"`,
`is_advisory=True`, `reason="Negative expectancy — average trade loses money"`, and
`expected_effect="Consider tightening entry filters to improve trade selectivity"`.

2.11 WHEN `IssueBadge` renders a `profit_factor_low` issue THEN the system SHALL display it
with orange (`_C_ORANGE`) severity color and the 🟠 icon.

2.12 WHEN `IssueBadge` renders an `expectancy_negative` issue THEN the system SHALL display it
with orange (`_C_ORANGE`) severity color and the 🟠 icon.

### Unchanged Behavior (Regression Prevention)

3.1 WHEN `prepare_sandbox` is called with a valid strategy name and candidate config THEN the
system SHALL CONTINUE TO create a timestamped sandbox directory under
`{user_data_path}/strategies/_improve_sandbox/`, copy the strategy `.py` file into it, and
return the sandbox path.

3.2 WHEN `accept_candidate` is called with a valid strategy name and candidate config THEN the
system SHALL CONTINUE TO atomically write the file using a `.tmp` → `os.replace()` pattern.

3.3 WHEN `rollback` is called with a valid strategy name and baseline params THEN the system
SHALL CONTINUE TO atomically write the file using a `.tmp` → `os.replace()` pattern.

3.4 WHEN `load_baseline_params` is called and `params.json` exists and is valid THEN the system
SHALL CONTINUE TO return the parsed dict from `params.json` without consulting the live strategy
JSON.

3.5 WHEN `ResultsDiagnosisService.diagnose` evaluates a summary that triggers existing rules
(`stoploss_too_wide`, `trades_too_low`, `weak_win_rate`, `drawdown_high`,
`poor_pair_concentration`, `negative_profit`) THEN the system SHALL CONTINUE TO return those
issues unchanged.

3.6 WHEN `RuleSuggestionService.suggest` handles existing issue types THEN the system SHALL
CONTINUE TO return the same suggestions as before.

3.7 WHEN `IssueBadge` renders existing issue types THEN the system SHALL CONTINUE TO display
them with their existing severity colors and icons.

3.8 WHEN the candidate backtest process exits with code 0 THEN the system SHALL CONTINUE TO
parse the candidate zip and display the comparison view.

3.9 WHEN `prepare_sandbox` is called and the live strategy JSON does not exist THEN the system
SHALL CONTINUE TO write a valid freqtrade-format JSON using only the candidate config values,
with `ft_stratparam_v: 1` and the current UTC timestamp as `export_time`.

## Bug Condition

The bug condition `C(X)` is:

> A strategy parameter file written by `ImproveService` (`prepare_sandbox`, `accept_candidate`,
> or `rollback`) is in the flat `params.json` format rather than the freqtrade nested format,
> causing freqtrade to reject it with `ERROR - Invalid parameter file provided.`

**Preservation check**: The bug condition is preserved across the call chain because
`_candidate_config` is loaded from `params.json` (flat format) and passed unchanged to
`prepare_sandbox`, `accept_candidate`, and `rollback`, all of which write it directly without
format conversion.

**Fix check**: The bug condition is eliminated when a `_build_freqtrade_params_file` helper
reads the live strategy JSON, merges the flat candidate config into the nested `params`
sub-object using the key mapping defined in 2.1, and all three write methods use this helper
instead of writing the flat dict directly.
