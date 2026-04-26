import { RefreshCcw } from 'lucide-react';
import { api } from '../api/client';
import { MetricCard } from '../components/MetricCard';
import { RunTable } from '../components/RunTable';
import { useAsync } from '../hooks/useAsync';
import type { RunResponse } from '../types/api';
import { formatDate, formatPct } from '../utils/format';

interface DashboardPageProps {
  onOpenRun: (run: RunResponse) => void;
}

export function DashboardPage({ onOpenRun }: DashboardPageProps) {
  const { data, loading, error, reload } = useAsync(api.dashboardSummary, []);

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p>Runs, strategies, and recent backtest health from the backend index.</p>
        </div>
        <button className="button" type="button" onClick={() => void reload()}>
          <RefreshCcw size={16} />
          Refresh
        </button>
      </header>

      {error ? <div className="alert error">{error}</div> : null}
      {loading ? <div className="loading-bar" /> : null}

      <section className="metric-grid">
        <MetricCard label="Runs" value={data?.metrics.total_runs ?? 0} detail="Saved backtests" />
        <MetricCard label="Strategies" value={data?.metrics.total_strategies ?? 0} detail="Indexed strategies" />
        <MetricCard
          label="Best profit"
          value={formatPct(data?.metrics.best_profit_pct)}
          tone={(data?.metrics.best_profit_pct ?? 0) >= 0 ? 'good' : 'bad'}
        />
        <MetricCard label="Best win rate" value={formatPct(data?.metrics.best_win_rate_pct)} tone="good" />
        <MetricCard label="Min drawdown" value={formatPct(data?.metrics.min_drawdown_pct)} tone="warn" />
        <MetricCard label="Latest run" value={formatDate(data?.metrics.latest_run_date)} detail="Last saved" />
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>Recent Runs</h2>
          <span className="muted">{data?.metrics.total_trades ?? 0} total trades</span>
        </div>
        <RunTable runs={data?.recent_runs ?? []} onOpen={onOpenRun} />
      </section>
    </div>
  );
}
