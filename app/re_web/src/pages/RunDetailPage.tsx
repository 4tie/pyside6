import { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import { MetricCard } from '../components/MetricCard';
import { Tabs } from '../components/Tabs';
import type { RunDetailResponse, RunResponse } from '../types/api';
import { formatDate, formatNumber, formatPct } from '../utils/format';

interface RunDetailPageProps {
  runId?: string;
  onOpenRun: (run: RunResponse) => void;
}

export function RunDetailPage({ runId, onOpenRun }: RunDetailPageProps) {
  const [runs, setRuns] = useState<RunResponse[]>([]);
  const [detail, setDetail] = useState<RunDetailResponse | null>(null);
  const [diagnosis, setDiagnosis] = useState<unknown>(null);
  const [diff, setDiff] = useState<unknown>(null);
  const [activeTab, setActiveTab] = useState('trades');
  const [error, setError] = useState('');

  useEffect(() => {
    void api.runs().then(setRuns).catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  useEffect(() => {
    const selected = runId || runs[0]?.run_id;
    if (!selected) return;
    void Promise.all([
      api.run(selected),
      api.diagnosis(selected).catch((err) => ({ error: err instanceof Error ? err.message : String(err) })),
      api.diff(selected).catch((err) => ({ error: err instanceof Error ? err.message : String(err) }))
    ])
      .then(([runDetail, runDiagnosis, runDiff]) => {
        setDetail(runDetail);
        setDiagnosis(runDiagnosis);
        setDiff(runDiff);
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, [runId, runs]);

  const equityPoints = useMemo(() => {
    let balance = detail?.starting_balance ?? 0;
    return (detail?.trades ?? []).map((trade, index) => {
      balance += trade.profit_abs;
      return { index, balance };
    });
  }, [detail]);

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Run Detail</h1>
          <p>{detail ? `${detail.strategy} · ${detail.run_id}` : 'Select a saved run.'}</p>
        </div>
        <select
          value={detail?.run_id ?? runId ?? ''}
          onChange={(event) => {
            const next = runs.find((run) => run.run_id === event.target.value);
            if (next) onOpenRun(next);
          }}
        >
          <option value="">Select run</option>
          {runs.map((run) => (
            <option key={run.run_id} value={run.run_id}>
              {run.strategy} · {run.run_id}
            </option>
          ))}
        </select>
      </header>

      {error ? <div className="alert error">{error}</div> : null}
      {detail ? (
        <>
          <section className="metric-grid">
            <MetricCard label="Profit" value={formatPct(detail.profit_total_pct)} tone={detail.profit_total_pct >= 0 ? 'good' : 'bad'} />
            <MetricCard label="Win rate" value={formatPct(detail.win_rate_pct)} />
            <MetricCard label="Drawdown" value={formatPct(detail.max_drawdown_pct)} tone="warn" />
            <MetricCard label="Trades" value={detail.trades_count} />
            <MetricCard label="Final balance" value={formatNumber(detail.final_balance)} />
            <MetricCard label="Saved" value={formatDate(detail.saved_at)} />
          </section>
          <Tabs
            active={activeTab}
            onChange={setActiveTab}
            tabs={[
              {
                id: 'trades',
                label: 'Trades',
                content: (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Pair</th>
                          <th>Profit</th>
                          <th>Absolute</th>
                          <th>Open</th>
                          <th>Close</th>
                          <th>Exit</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.trades.map((trade, index) => (
                          <tr key={`${trade.pair}-${index}`}>
                            <td>{trade.pair}</td>
                            <td className={trade.profit >= 0 ? 'positive' : 'negative'}>{formatPct(trade.profit)}</td>
                            <td>{formatNumber(trade.profit_abs)}</td>
                            <td>{formatDate(trade.open_date)}</td>
                            <td>{formatDate(trade.close_date)}</td>
                            <td>{trade.exit_reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )
              },
              {
                id: 'chart',
                label: 'Chart',
                content: <EquitySparkline points={equityPoints} />
              },
              {
                id: 'diagnosis',
                label: 'Diagnosis',
                content: <pre className="json-block">{JSON.stringify(diagnosis, null, 2)}</pre>
              },
              {
                id: 'params',
                label: 'Params',
                content: <pre className="json-block">{JSON.stringify(detail.params, null, 2)}</pre>
              },
              {
                id: 'diff',
                label: 'Diff',
                content: <pre className="json-block">{JSON.stringify(diff, null, 2)}</pre>
              }
            ]}
          />
        </>
      ) : (
        <div className="empty-state">No run selected.</div>
      )}
    </div>
  );
}

function EquitySparkline({ points }: { points: { index: number; balance: number }[] }) {
  if (!points.length) return <div className="empty-state">No trade series available.</div>;
  const min = Math.min(...points.map((point) => point.balance));
  const max = Math.max(...points.map((point) => point.balance));
  const range = max - min || 1;
  const path = points
    .map((point, index) => {
      const x = (index / Math.max(points.length - 1, 1)) * 1000;
      const y = 260 - ((point.balance - min) / range) * 220;
      return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(' ');
  return (
    <svg className="equity-chart" viewBox="0 0 1000 300" role="img" aria-label="Equity curve">
      <path d={path} />
    </svg>
  );
}
