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
    <div className="table-wrap">
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
  );
}
