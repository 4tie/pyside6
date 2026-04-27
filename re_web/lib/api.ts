// API Client for FastAPI Backend
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export interface BacktestRequest {
  strategy: string;
  timeframe: string;
  timerange?: string;
  pairs?: string[];
  max_open_trades?: number;
  dry_run_wallet?: number;
}

export interface DownloadDataRequest {
  timeframe: string;
  timerange?: string;
  pairs: string[];
  prepend?: boolean;
  erase?: boolean;
}

export interface OptimizeRequest {
  strategy: string;
  timeframe: string;
  epochs: number;
  timerange?: string;
  pairs?: string[];
  spaces?: string[];
  hyperopt_loss?: string;
}

export interface BacktestRun {
  run_id: string;
  strategy: string;
  saved_at: string;
  backtest_end?: string;
  profit_total_pct?: number;
  win_rate_pct?: number;
  max_drawdown_pct?: number;
  trades_count?: number;
  avg_profit?: number;
  median_profit?: number;
  total_volume?: number;
}

export interface DashboardMetrics {
  total_runs: number;
  total_strategies: number;
  best_profit_pct: number;
  best_win_rate_pct: number;
  min_drawdown_pct: number;
  total_trades: number;
  latest_run_date: string;
}

export interface DashboardSummary {
  metrics: DashboardMetrics;
  recent_runs: BacktestRun[];
  strategies: string[];
}

export interface TradingPair {
  symbol: string;
}

export interface PairsResponse {
  categories: Record<string, string[]>;
  all_pairs: string[];
  favorites: string[];
}

export interface BacktestStatus {
  status: string;
  run_id?: string;
  message: string;
}

export interface DataAvailabilityResponse {
  available: boolean;
  available_pairs: string[];
  missing_pairs: string[];
  message: string;
}

export interface LatestBacktestRun {
  exists: boolean;
  message?: string;
  run_id?: string;
  strategy?: string;
  timeframe?: string;
  pairs?: string[];
  timerange?: string;
  backtest_start?: string;
  backtest_end?: string;
  saved_at?: string;
  profit_total_pct?: number;
  profit_total_abs?: number;
  starting_balance?: number;
  final_balance?: number;
  max_drawdown_pct?: number;
  max_drawdown_abs?: number;
  trades_count?: number;
  wins?: number;
  losses?: number;
  win_rate_pct?: number;
  sharpe?: number;
  sortino?: number;
  calmar?: number;
  profit_factor?: number;
  expectancy?: number;
  run_dir?: string;
  trades?: Array<{
    pair: string;
    profit_abs: number;
    profit: number;
    open_date: string;
    close_date: string;
    exit_reason: string;
  }>;
  params?: Record<string, any>;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }

    return response.json();
  }

  // Dashboard
  async getDashboardSummary(): Promise<DashboardSummary> {
    return this.request<DashboardSummary>('/dashboard/summary');
  }

  // Strategies
  async getStrategies(): Promise<{ name: string; config: any }[]> {
    return this.request<{ name: string; config: any }[]>('/strategies');
  }

  async getStrategy(strategyName: string): Promise<{ name: string; config: any }> {
    return this.request<{ name: string; config: any }>(`/strategies/${strategyName}`);
  }

  // Backtest
  async executeBacktest(request: BacktestRequest): Promise<{ status: string; message: string }> {
    return this.request<{ status: string; message: string }>('/backtest/execute', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async getBacktestStatus(): Promise<BacktestStatus> {
    return this.request<BacktestStatus>('/backtest/status');
  }

  async stopBacktest(): Promise<{ status: string; message: string }> {
    return this.request<{ status: string; message: string }>('/backtest/stop', {
      method: 'POST',
    });
  }

  async getBacktestConfig(): Promise<BacktestRequest> {
    return this.request<BacktestRequest>('/backtest-config');
  }

  async saveBacktestConfig(request: BacktestRequest): Promise<BacktestRequest> {
    return this.request<BacktestRequest>('/backtest-config', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Download Data
  async downloadData(request: DownloadDataRequest): Promise<{ success: boolean; message: string; task_id: string }> {
    return this.request<{ success: boolean; message: string; task_id: string }>('/download-data', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Pairs
  async getPairs(): Promise<PairsResponse> {
    return this.request<PairsResponse>('/pairs');
  }

  async checkDataAvailability(pairs: string[], timeframe: string, timerange?: string): Promise<DataAvailabilityResponse> {
    const params = new URLSearchParams({ pairs: pairs.join(','), timeframe });
    if (timerange) params.append('timerange', timerange);
    return this.request<DataAvailabilityResponse>(`/check-data?${params.toString()}`);
  }

  async getLatestBacktestRun(): Promise<LatestBacktestRun> {
    return this.request<LatestBacktestRun>('/latest-run');
  }

  async saveFavorites(favorites: string[]): Promise<{ favorites: string[] }> {
    return this.request<{ favorites: string[] }>('/favorites', {
      method: 'POST',
      body: JSON.stringify({ favorites }),
    });
  }

  // Optimization
  async runOptimize(request: OptimizeRequest): Promise<{ status: string; message: string }> {
    return this.request<{ status: string; message: string }>('/optimize/run', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Health check
  async healthCheck(): Promise<{ status: string; service: string }> {
    return this.request<{ status: string; service: string }>('/health');
  }
}

export const api = new ApiClient();
