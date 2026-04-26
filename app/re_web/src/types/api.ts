export type ThemeMode = 'dark' | 'light';

export interface PreferenceSection {
  last_strategy?: string;
  default_timeframe?: string;
  default_timerange?: string;
  default_pairs?: string;
  last_timerange_preset?: string;
  dry_run_wallet?: number;
  max_open_trades?: number;
  total_trials?: number;
  score_metric?: string;
  score_mode?: string;
  target_min_trades?: number;
  target_profit_pct?: number;
  max_drawdown_limit?: number;
  target_romad?: number;
  epochs?: number;
  spaces?: string;
  hyperopt_loss?: string;
  prepend?: boolean;
  erase?: boolean;
  paired_favorites?: string[];
}

export interface SettingsResponse {
  user_data_path: string;
  venv_path: string;
  python_executable: string;
  freqtrade_executable: string;
  use_module_execution: boolean;
  backtest_preferences: PreferenceSection;
  optimize_preferences: PreferenceSection;
  download_preferences: PreferenceSection;
  optimizer_preferences: PreferenceSection;
}

export type SettingsUpdate = Partial<SettingsResponse>;

export interface StrategyResponse {
  name: string;
  config?: Record<string, unknown> | null;
}

export interface RunResponse {
  run_id: string;
  strategy: string;
  timeframe: string;
  pairs: string[];
  timerange: string;
  backtest_start: string;
  backtest_end: string;
  saved_at: string;
  profit_total_pct: number;
  profit_total_abs: number;
  starting_balance: number;
  final_balance: number;
  max_drawdown_pct: number;
  max_drawdown_abs: number;
  trades_count: number;
  wins: number;
  losses: number;
  win_rate_pct: number;
  sharpe?: number | null;
  sortino?: number | null;
  calmar?: number | null;
  profit_factor: number;
  expectancy: number;
  run_dir: string;
}

export interface TradeResponse {
  pair: string;
  profit_abs: number;
  profit: number;
  open_date: string;
  close_date?: string | null;
  exit_reason: string;
}

export interface RunDetailResponse extends RunResponse {
  trades: TradeResponse[];
  params: Record<string, unknown>;
}

export interface DashboardSummary {
  metrics: {
    total_runs: number;
    total_strategies: number;
    best_profit_pct: number;
    best_win_rate_pct: number;
    min_drawdown_pct: number;
    total_trades: number;
    latest_run_date: string;
  };
  recent_runs: RunResponse[];
  strategies: string[];
}

export interface PairsResponse {
  pairs: string[];
  favorites: string[];
}

export interface BacktestRequest {
  strategy: string;
  timeframe: string;
  timerange?: string;
  pairs?: string[];
  max_open_trades?: number;
  dry_run_wallet?: number;
}

export interface BacktestStatus {
  status: string;
  run_id?: string | null;
  message?: string;
}

export interface ParamDef {
  name: string;
  param_type: string;
  default: unknown;
  low?: number | null;
  high?: number | null;
  categories?: unknown[] | null;
  space: string;
  enabled: boolean;
}

export interface StrategyParamsResponse {
  strategy_class: string;
  timeframe: string;
  params: ParamDef[];
}

export interface OptimizerSessionSummary {
  session_id: string;
  strategy_name?: string;
  status: string;
  trials_completed: number;
  started_at?: string | null;
  config?: Record<string, unknown>;
  best_pointer?: { trial_number: number; score: number } | null;
}

export interface TrialRecord {
  trial_number: number;
  status: string;
  score?: number | null;
  score_mode?: string;
  score_metric?: string;
  metrics?: Record<string, number | string | null> | null;
  candidate_params?: Record<string, unknown>;
  is_best?: boolean;
}

export interface TrialListResponse {
  trials: TrialRecord[];
  total: number;
}

export interface ComparisonResponse {
  run_a_id: string;
  run_b_id: string;
  profit_diff: number;
  winrate_diff: number;
  drawdown_diff: number;
  verdict: string;
  score_a: number;
  score_b: number;
  score_diff: number;
  score_pct_change: number;
  sharpe_diff: number;
  sortino_diff: number;
  calmar_diff: number;
  profit_factor_diff: number;
  expectancy_diff: number;
  confidence_score: number;
  confidence_reason: string;
  is_statistically_significant: boolean;
  recommendations: string[];
}
