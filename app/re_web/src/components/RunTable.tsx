import type { RunResponse } from '../types/api';
import { formatDate, formatNumber, formatPct } from '../utils/format';
import { StatusBadge } from './StatusBadge';

interface RunTableProps {
  runs: RunResponse[];
  onOpen: (run: RunResponse) => void;
}

export function RunTable({ runs, onOpen }: RunTableProps) {
  if (!runs.length) {
    return <div className="empty-state">No runs found.</div>;
  }

  return (
    <>
      <div className="table-wrap run-table-desktop">
        <table>
          <thead>
            <tr>
              <th>Strategy</th>
              <th>Timeframe</th>
              <th>Profit</th>
              <th>Win rate</th>
              <th>Drawdown</th>
              <th>Trades</th>
              <th>Saved</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.run_id}>
                <td>
                  <strong>{run.strategy}</strong>
                  <span className="muted block">{run.run_id}</span>
                </td>
                <td>
                  <StatusBadge status={run.timeframe || '-'} />
                </td>
                <td className={run.profit_total_pct >= 0 ? 'positive' : 'negative'}>
                  {formatPct(run.profit_total_pct)}
                  <span className="muted block">{formatNumber(run.profit_total_abs)}</span>
                </td>
                <td>{formatPct(run.win_rate_pct)}</td>
                <td className="negative">{formatPct(run.max_drawdown_pct)}</td>
                <td>{run.trades_count}</td>
                <td>{formatDate(run.saved_at)}</td>
                <td>
                  <button className="button ghost" type="button" onClick={() => onOpen(run)}>
                    Open
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="run-card-list">
        {runs.map((run) => (
          <div key={run.run_id} className="run-card">
            <div className="run-card-main">
              <strong>{run.strategy}</strong>
              <span className="muted">{run.run_id}</span>
            </div>
            <div className="run-card-stats">
              <span className={run.profit_total_pct >= 0 ? 'positive' : 'negative'}>
                {formatPct(run.profit_total_pct)}
              </span>
              <span className="muted">WR {formatPct(run.win_rate_pct)}</span>
              <span className="muted">DD {formatPct(run.max_drawdown_pct)}</span>
              <span className="muted">{run.trades_count} trades</span>
            </div>
            <button className="button ghost run-card-open" type="button" onClick={() => onOpen(run)}>
              Open
            </button>
          </div>
        ))}
      </div>
    </>
  );
}
