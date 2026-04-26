import { GitCompare, RefreshCcw } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { MetricCard } from '../components/MetricCard';
import { RunTable } from '../components/RunTable';
import type { ComparisonResponse, RunResponse } from '../types/api';
import { formatPct } from '../utils/format';

interface ComparisonPageProps {
  onOpenRun: (run: RunResponse) => void;
}

export function ComparisonPage({ onOpenRun }: ComparisonPageProps) {
  const [runs, setRuns] = useState<RunResponse[]>([]);
  const [runA, setRunA] = useState('');
  const [runB, setRunB] = useState('');
  const [comparison, setComparison] = useState<ComparisonResponse | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    void loadRuns();
  }, []);

  async function loadRuns() {
    const nextRuns = await api.runs();
    setRuns(nextRuns);
    setRunA((current) => current || nextRuns[0]?.run_id || '');
    setRunB((current) => current || nextRuns[1]?.run_id || nextRuns[0]?.run_id || '');
  }

  async function compare() {
    setError('');
    if (!runA || !runB || runA === runB) {
      setError('Select two different runs.');
      return;
    }
    setComparison(await api.compare(runA, runB, true));
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Comparison</h1>
          <p>Compare saved runs through the backend comparison service.</p>
        </div>
        <button className="button" type="button" onClick={() => void loadRuns()}>
          <RefreshCcw size={16} />
          Refresh
        </button>
      </header>

      <section className="panel comparison-controls">
        <label>
          Baseline
          <select value={runA} onChange={(event) => setRunA(event.target.value)}>
            <option value="">Select run</option>
            {runs.map((run) => (
              <option key={run.run_id} value={run.run_id}>
                {run.strategy} · {run.run_id}
              </option>
            ))}
          </select>
        </label>
        <label>
          Candidate
          <select value={runB} onChange={(event) => setRunB(event.target.value)}>
            <option value="">Select run</option>
            {runs.map((run) => (
              <option key={run.run_id} value={run.run_id}>
                {run.strategy} · {run.run_id}
              </option>
            ))}
          </select>
        </label>
        <button className="button primary" type="button" onClick={() => void compare()}>
          <GitCompare size={16} />
          Compare
        </button>
      </section>

      {error ? <div className="alert error">{error}</div> : null}

      {comparison ? (
        <>
          <section className="metric-grid">
            <MetricCard label="Verdict" value={comparison.verdict} />
            <MetricCard label="Profit diff" value={formatPct(comparison.profit_diff)} tone={comparison.profit_diff >= 0 ? 'good' : 'bad'} />
            <MetricCard label="Win-rate diff" value={formatPct(comparison.winrate_diff)} />
            <MetricCard label="Drawdown diff" value={formatPct(comparison.drawdown_diff)} tone="warn" />
            <MetricCard label="Score diff" value={comparison.score_diff.toFixed(3)} />
            <MetricCard label="Confidence" value={formatPct(comparison.confidence_score * 100)} />
          </section>
          <section className="panel">
            <div className="panel-header">
              <h2>Recommendations</h2>
            </div>
            <ul className="recommendations">
              {comparison.recommendations.length ? (
                comparison.recommendations.map((item) => <li key={item}>{item}</li>)
              ) : (
                <li>No backend recommendations for this pair.</li>
              )}
            </ul>
          </section>
        </>
      ) : null}

      <section className="panel">
        <div className="panel-header">
          <h2>Runs</h2>
          <span className="muted">{runs.length} available</span>
        </div>
        <RunTable runs={runs} onOpen={onOpenRun} />
      </section>
    </div>
  );
}
