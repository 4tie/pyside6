import type {
  BacktestRequest,
  BacktestStatus,
  ComparisonResponse,
  DashboardSummary,
  PairsResponse,
  RunDetailResponse,
  RunResponse,
  SettingsResponse,
  SettingsUpdate,
  StrategyParamsResponse,
  StrategyResponse,
  TrialListResponse,
  OptimizerSessionSummary
} from '../types/api';

type QueryValue = string | number | boolean | undefined | null;

class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

function query(params: Record<string, QueryValue>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      search.set(key, String(value));
    }
  }
  const serialized = search.toString();
  return serialized ? `?${serialized}` : '';
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(path, { ...init, headers });
  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      detail = await response.json();
    } catch {
      detail = await response.text();
    }
    const message =
      typeof detail === 'object' && detail && 'detail' in detail
        ? String((detail as { detail: unknown }).detail)
        : String(detail);
    throw new ApiError(response.status, message, detail);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  dashboardSummary: () => request<DashboardSummary>('/api/dashboard/summary'),
  settings: () => request<SettingsResponse>('/api/settings'),
  updateSettings: (payload: SettingsUpdate) =>
    request<SettingsResponse>('/api/settings', { method: 'PUT', body: JSON.stringify(payload) }),
  strategies: () => request<StrategyResponse[]>('/api/strategies'),
  optimizerStrategies: () => request<string[]>('/api/optimizer/strategies'),
  pairs: () => request<PairsResponse>('/api/pairs'),
  runs: (strategy?: string) => request<RunResponse[]>(`/api/runs${query({ strategy })}`),
  run: (runId: string) => request<RunDetailResponse>(`/api/runs/${encodeURIComponent(runId)}`),
  diagnosis: (runId: string) => request<unknown>(`/api/diagnosis/${encodeURIComponent(runId)}`),
  diff: (runId: string) => request<unknown>(`/api/runs/${encodeURIComponent(runId)}/diff`),
  compare: (runAId: string, runBId: string, detailed = true) =>
    request<ComparisonResponse>(
      `/api/comparison${query({ run_a_id: runAId, run_b_id: runBId, detailed })}`
    ),
  executeBacktest: (payload: BacktestRequest) =>
    request<{ status: string; run_id?: string; message?: string }>('/api/backtest/execute', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  stopBacktest: () => request<{ status: string; message?: string }>('/api/backtest/stop', { method: 'POST' }),
  backtestStatus: () => request<BacktestStatus>('/api/backtest/status'),
  downloadData: (payload: { timeframe: string; timerange?: string; pairs?: string[]; prepend?: boolean; erase?: boolean }) =>
    request<{ success: boolean; message: string; task_id?: string }>('/api/download-data', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  strategyParams: (strategy: string) =>
    request<StrategyParamsResponse>(`/api/optimizer/strategy-params${query({ strategy })}`),
  sessions: () => request<OptimizerSessionSummary[]>('/api/optimizer/sessions'),
  session: (sessionId: string) =>
    request<OptimizerSessionSummary>(`/api/optimizer/sessions/${encodeURIComponent(sessionId)}`),
  sessionTrials: (sessionId: string) =>
    request<TrialListResponse>(`/api/optimizer/sessions/${encodeURIComponent(sessionId)}/trials`),
  createSession: (payload: Record<string, unknown>) =>
    request<{ session_id: string; status: string }>('/api/optimizer/sessions', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  startSession: (sessionId: string) =>
    request<{ status: string; session_id: string }>(`/api/optimizer/sessions/${encodeURIComponent(sessionId)}/start`, {
      method: 'POST'
    }),
  stopSession: (sessionId: string) =>
    request<{ status: string; session_id: string }>(`/api/optimizer/sessions/${encodeURIComponent(sessionId)}/stop`, {
      method: 'POST'
    })
};

export { ApiError };
