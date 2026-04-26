import { ChevronDown, TrendingDown, TrendingUp } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api/client';
import { MetricCard } from '../components/MetricCard';
import { Tabs } from '../components/Tabs';
import type { RunDetailResponse, RunResponse } from '../types/api';
import { formatDate, formatNumber, formatPct } from '../utils/format';

interface RunDetailPageProps {
  runId?: string;
  onOpenRun: (run: RunResponse) => void;
}

// ─── helpers ────────────────────────────────────────────────────────────────

function severityClass(s: string) {
  if (s === 'error' || s === 'critical') return 'diag-badge diag-error';
  if (s === 'warning' || s === 'warn')   return 'diag-badge diag-warn';
  return 'diag-badge diag-info';
}

function severityIcon(s: string) {
  if (s === 'error' || s === 'critical') return '✕';
  if (s === 'warning' || s === 'warn')   return '⚠';
  return 'ℹ';
}

// ─── Equity chart ────────────────────────────────────────────────────────────

interface EquityPoint { index: number; balance: number }

function EquityChart({ points, startBalance }: { points: EquityPoint[]; startBalance: number }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<{ x: number; y: number; balance: number; idx: number } | null>(null);

  if (!points.length) {
    return <div className="empty-state chart-empty">No trade data available.</div>;
  }

  const W = 1000;
  const H = 300;
  const PAD = { top: 20, right: 20, bottom: 32, left: 64 };
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;

  const balances = points.map((p) => p.balance);
  const rawMin = Math.min(...balances, startBalance);
  const rawMax = Math.max(...balances, startBalance);
  const span   = rawMax - rawMin || 1;
  const minY   = rawMin - span * 0.08;
  const maxY   = rawMax + span * 0.08;
  const range  = maxY - minY;

  const toX = (i: number) => PAD.left + (i / Math.max(points.length - 1, 1)) * innerW;
  const toY = (v: number) => PAD.top + (1 - (v - minY) / range) * innerH;

  const linePts = points.map((p, i) => `${toX(i).toFixed(1)},${toY(p.balance).toFixed(1)}`).join(' ');
  const zeroY   = toY(startBalance);
  const isProfit = points[points.length - 1].balance >= startBalance;
  const lineColor = isProfit ? 'var(--green)' : 'var(--red)';

  // Area path: line + close back along bottom
  const firstX = toX(0).toFixed(1);
  const lastX  = toX(points.length - 1).toFixed(1);
  const areaPath = `M ${firstX},${toY(points[0].balance).toFixed(1)} `
    + points.slice(1).map((p, i) => `L ${toX(i + 1).toFixed(1)},${toY(p.balance).toFixed(1)}`).join(' ')
    + ` L ${lastX},${zeroY.toFixed(1)} L ${firstX},${zeroY.toFixed(1)} Z`;

  // Y-axis ticks (5 evenly spaced)
  const ticks = Array.from({ length: 5 }, (_, i) => {
    const v = minY + (range / 4) * i;
    return { v, y: toY(v) };
  });

  function onMouseMove(e: React.MouseEvent<SVGSVGElement>) {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    const svgX = ((e.clientX - rect.left) / rect.width) * W;
    const relX = svgX - PAD.left;
    const idx  = Math.round((relX / innerW) * (points.length - 1));
    const clamped = Math.max(0, Math.min(points.length - 1, idx));
    const pt = points[clamped];
    setHover({ x: toX(clamped), y: toY(pt.balance), balance: pt.balance, idx: clamped });
  }

  function getTouchX(e: React.TouchEvent<SVGSVGElement>): number {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect || !e.touches.length) return 0;
    return ((e.touches[0].clientX - rect.left) / rect.width) * W;
  }

  return (
    <div className="equity-chart-wrap">
      <svg
        ref={svgRef}
        className="equity-chart-svg"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label="Equity curve"
        onMouseMove={onMouseMove}
        onMouseLeave={() => setHover(null)}
        onTouchMove={(e) => {
          e.preventDefault();
          const svgX = getTouchX(e);
          const relX = svgX - PAD.left;
          const idx = Math.round((relX / innerW) * (points.length - 1));
          const clamped = Math.max(0, Math.min(points.length - 1, idx));
          const pt = points[clamped];
          setHover({ x: toX(clamped), y: toY(pt.balance), balance: pt.balance, idx: clamped });
        }}
        onTouchEnd={() => setHover(null)}
        style={{ touchAction: 'none' }}
      >
        <defs>
          <linearGradient id="eq-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"   stopColor={lineColor} stopOpacity="0.22" />
            <stop offset="100%" stopColor={lineColor} stopOpacity="0.01" />
          </linearGradient>
          <clipPath id="eq-clip">
            <rect x={PAD.left} y={PAD.top} width={innerW} height={innerH} />
          </clipPath>
        </defs>

        {/* Grid lines */}
        {ticks.map(({ v, y }) => (
          <g key={v}>
            <line x1={PAD.left} y1={y} x2={W - PAD.right} y2={y}
              stroke="var(--border)" strokeWidth="1" strokeDasharray="4 4" />
            <text x={PAD.left - 8} y={y + 4} textAnchor="end"
              fontSize="11" fill="var(--muted)">
              {formatNumber(v)}
            </text>
          </g>
        ))}

        {/* Zero / start-balance line */}
        {zeroY >= PAD.top && zeroY <= PAD.top + innerH && (
          <line x1={PAD.left} y1={zeroY} x2={W - PAD.right} y2={zeroY}
            stroke="var(--muted)" strokeWidth="1" strokeDasharray="6 3" opacity="0.6" />
        )}

        {/* Area fill */}
        <path d={areaPath} fill="url(#eq-fill)" clipPath="url(#eq-clip)" />

        {/* Line */}
        <polyline
          points={linePts}
          fill="none"
          stroke={lineColor}
          strokeWidth="2.5"
          strokeLinejoin="round"
          strokeLinecap="round"
          clipPath="url(#eq-clip)"
        />

        {/* Hover crosshair */}
        {hover && (
          <>
            <line x1={hover.x} y1={PAD.top} x2={hover.x} y2={PAD.top + innerH}
              stroke="var(--muted)" strokeWidth="1" strokeDasharray="3 3" opacity="0.7" />
            <circle cx={hover.x} cy={hover.y} r="5"
              fill={lineColor} stroke="var(--surface)" strokeWidth="2" />
            {/* Tooltip */}
            <g transform={`translate(${Math.min(hover.x + 10, W - 130)},${Math.max(hover.y - 36, PAD.top)})`}>
              <rect rx="5" ry="5" width="118" height="38"
                fill="var(--surface-3)" stroke="var(--border)" strokeWidth="1" />
              <text x="9" y="14" fontSize="10" fill="var(--muted)">
                Trade #{hover.idx + 1}
              </text>
              <text x="9" y="29" fontSize="13" fontWeight="600" fill={lineColor}>
                {formatNumber(hover.balance)}
              </text>
            </g>
          </>
        )}

        {/* X-axis label */}
        <text x={PAD.left + innerW / 2} y={H - 4} textAnchor="middle"
          fontSize="11" fill="var(--muted)">
          Trades
        </text>
      </svg>

      {/* Summary strip */}
      <div className="equity-summary">
        <span className="muted" style={{ fontSize: 12 }}>
          Start: <strong>{formatNumber(startBalance)}</strong>
        </span>
        <span className="muted" style={{ fontSize: 12 }}>
          End: <strong style={{ color: lineColor }}>
            {formatNumber(points[points.length - 1]?.balance ?? startBalance)}
          </strong>
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: lineColor }}>
          {isProfit ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
          {formatPct(((points[points.length - 1]?.balance ?? startBalance) / startBalance - 1) * 100)}
        </span>
      </div>
    </div>
  );
}

// ─── Diagnosis panel ─────────────────────────────────────────────────────────

interface DiagIssue { rule_id?: string; message?: string; severity?: string }
interface DiagData  { run_id?: string; issues?: DiagIssue[]; suggestions?: DiagIssue[]; error?: string }

function DiagnosisPanel({ data }: { data: unknown }) {
  const d = data as DiagData | null;

  if (!d || d.error) {
    return (
      <div className="diag-empty">
        <span className="diag-badge diag-info">ℹ</span>
        {d?.error ?? 'No diagnosis data available for this run.'}
      </div>
    );
  }

  const issues      = d.issues      ?? [];
  const suggestions = d.suggestions ?? [];

  if (!issues.length && !suggestions.length) {
    return (
      <div className="diag-empty">
        <span className="diag-badge diag-info" style={{ color: 'var(--green)', borderColor: 'var(--green)' }}>✓</span>
        No issues detected.
      </div>
    );
  }

  return (
    <div className="diag-panel">
      {issues.length > 0 && (
        <section>
          <h3 className="diag-section-title">Issues</h3>
          <div className="diag-list">
            {issues.map((issue, i) => (
              <div key={i} className="diag-row">
                <span className={severityClass(issue.severity ?? '')}>
                  {severityIcon(issue.severity ?? '')}
                </span>
                <div className="diag-body">
                  <strong className="diag-rule">{issue.rule_id ?? 'unknown'}</strong>
                  <span className="diag-message">{issue.message}</span>
                </div>
                <span className="diag-severity">{issue.severity}</span>
              </div>
            ))}
          </div>
        </section>
      )}
      {suggestions.length > 0 && (
        <section>
          <h3 className="diag-section-title">Suggestions</h3>
          <div className="diag-list">
            {suggestions.map((s, i) => (
              <div key={i} className="diag-row">
                <span className={severityClass(s.severity ?? '')}>
                  {severityIcon(s.severity ?? '')}
                </span>
                <div className="diag-body">
                  <strong className="diag-rule">{s.rule_id ?? 'unknown'}</strong>
                  <span className="diag-message">{s.message}</span>
                </div>
                <span className="diag-severity">{s.severity}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

// ─── Params panel ────────────────────────────────────────────────────────────

function ParamsPanel({ params }: { params: Record<string, unknown> }) {
  const entries = Object.entries(params ?? {});
  if (!entries.length) {
    return <div className="diag-empty">No parameters saved for this run.</div>;
  }
  return (
    <div className="params-table-wrap">
      <table className="params-table">
        <thead>
          <tr>
            <th>Parameter</th>
            <th>Value</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([key, val]) => (
            <tr key={key}>
              <td className="param-key">{key}</td>
              <td className="param-val">
                {typeof val === 'object'
                  ? <code>{JSON.stringify(val)}</code>
                  : <code>{String(val)}</code>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Diff panel ──────────────────────────────────────────────────────────────

interface DiffChange { param?: string; key?: string; before?: unknown; after?: unknown; old?: unknown; new?: unknown }
interface DiffData   { parameter_changes?: DiffChange[]; code_changes?: unknown[]; has_code_diff?: boolean; error?: string }

function DiffPanel({ data }: { data: unknown }) {
  const d = data as DiffData | null;

  if (!d || d.error) {
    return (
      <div className="diag-empty">
        <span className="diag-badge diag-info">ℹ</span>
        {d?.error ?? 'No diff available — this may be the first run for this strategy.'}
      </div>
    );
  }

  const changes = d.parameter_changes ?? [];
  if (!changes.length && !d.has_code_diff) {
    return (
      <div className="diag-empty">
        <span className="diag-badge diag-info" style={{ color: 'var(--green)', borderColor: 'var(--green)' }}>✓</span>
        No parameter changes from baseline.
      </div>
    );
  }

  return (
    <div className="diff-panel">
      {changes.length > 0 && (
        <section>
          <h3 className="diag-section-title">Parameter Changes</h3>
          <div className="diff-table-wrap">
            <table className="params-table">
              <thead>
                <tr>
                  <th>Parameter</th>
                  <th>Before</th>
                  <th>After</th>
                </tr>
              </thead>
              <tbody>
                {changes.map((c, i) => {
                  const name   = c.param ?? c.key ?? `change_${i}`;
                  const before = c.before ?? c.old;
                  const after  = c.after  ?? c.new;
                  const improved = typeof after === 'number' && typeof before === 'number'
                    ? after > before : null;
                  return (
                    <tr key={i}>
                      <td className="param-key">{name}</td>
                      <td className="param-val diff-before">
                        <code>{String(before ?? '—')}</code>
                      </td>
                      <td className="param-val" style={{
                        color: improved === true ? 'var(--green)' : improved === false ? 'var(--red)' : undefined
                      }}>
                        <code>{String(after ?? '—')}</code>
                        {improved === true  && ' ↑'}
                        {improved === false && ' ↓'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {d.has_code_diff && (
        <div className="diag-row" style={{ marginTop: 12 }}>
          <span className="diag-badge diag-info">ℹ</span>
          <span style={{ fontSize: 13 }}>Strategy code was also modified in this run.</span>
        </div>
      )}
    </div>
  );
}

// ─── Main page ───────────────────────────────────────────────────────────────

export function RunDetailPage({ runId, onOpenRun }: RunDetailPageProps) {
  const [runs, setRuns]         = useState<RunResponse[]>([]);
  const [detail, setDetail]     = useState<RunDetailResponse | null>(null);
  const [diagnosis, setDiagnosis] = useState<unknown>(null);
  const [diff, setDiff]         = useState<unknown>(null);
  const [activeTab, setActiveTab] = useState('trades');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');

  useEffect(() => {
    void api.runs()
      .then(setRuns)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  useEffect(() => {
    const selected = runId || runs[0]?.run_id;
    if (!selected) return;
    setLoading(true);
    setError('');
    void Promise.all([
      api.run(selected),
      api.diagnosis(selected).catch((err) => ({ error: err instanceof Error ? err.message : String(err) })),
      api.diff(selected).catch((err)       => ({ error: err instanceof Error ? err.message : String(err) })),
    ])
      .then(([runDetail, runDiagnosis, runDiff]) => {
        setDetail(runDetail);
        setDiagnosis(runDiagnosis);
        setDiff(runDiff);
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, [runId, runs]);

  const equityPoints = useMemo(() => {
    let balance = detail?.starting_balance ?? 0;
    return (detail?.trades ?? []).map((trade, index) => {
      balance += trade.profit_abs;
      return { index, balance };
    });
  }, [detail]);

  // Count diagnosis issues for badge
  const diagData = diagnosis as { issues?: unknown[]; suggestions?: unknown[] } | null;
  const issueCount = (diagData?.issues?.length ?? 0) + (diagData?.suggestions?.length ?? 0);

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Run Detail</h1>
          <p className="muted">
            {detail ? `${detail.strategy} · ${detail.timeframe} · ${detail.timerange || 'all time'}` : 'Select a saved run.'}
          </p>
        </div>
        <div className="run-selector-wrap">
          <select
            className="run-selector"
            value={detail?.run_id ?? runId ?? ''}
            onChange={(e) => {
              const next = runs.find((r) => r.run_id === e.target.value);
              if (next) onOpenRun(next);
            }}
          >
            <option value="">Select run…</option>
            {runs.map((run) => (
              <option key={run.run_id} value={run.run_id}>
                {run.strategy} · {run.run_id} · {formatPct(run.profit_total_pct)}
              </option>
            ))}
          </select>
          <ChevronDown size={14} className="run-selector-icon" />
        </div>
      </header>

      {loading && <div className="loading-bar" />}
      {error   && <div className="alert error">{error}</div>}

      {detail ? (
        <>
          {/* Metric strip */}
          <section className="metric-grid">
            <MetricCard
              label="Profit"
              value={formatPct(detail.profit_total_pct)}
              detail={`${formatNumber(detail.profit_total_abs)} USDT`}
              tone={detail.profit_total_pct >= 0 ? 'good' : 'bad'}
            />
            <MetricCard
              label="Win rate"
              value={formatPct(detail.win_rate_pct)}
              detail={`${detail.wins}W / ${detail.losses}L`}
              tone={detail.win_rate_pct >= 50 ? 'good' : 'neutral'}
            />
            <MetricCard
              label="Drawdown"
              value={formatPct(detail.max_drawdown_pct)}
              tone="warn"
            />
            <MetricCard
              label="Trades"
              value={detail.trades_count}
              detail={`${detail.timeframe} · ${detail.pairs?.slice(0, 2).join(', ')}${(detail.pairs?.length ?? 0) > 2 ? '…' : ''}`}
            />
            <MetricCard
              label="Final balance"
              value={formatNumber(detail.final_balance)}
              detail={`Start: ${formatNumber(detail.starting_balance)}`}
              tone={detail.final_balance >= detail.starting_balance ? 'good' : 'bad'}
            />
            <MetricCard
              label="Saved"
              value={formatDate(detail.saved_at)}
              detail={`Sharpe: ${detail.sharpe != null ? detail.sharpe.toFixed(3) : '—'}`}
            />
          </section>

          {/* Tabs */}
          <Tabs
            active={activeTab}
            onChange={setActiveTab}
            tabs={[
              {
                id: 'trades',
                label: `Trades (${detail.trades_count})`,
                content: (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>#</th>
                          <th>Pair</th>
                          <th>Profit %</th>
                          <th>Abs</th>
                          <th>Open</th>
                          <th>Close</th>
                          <th>Exit reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.trades.map((trade, i) => (
                          <tr key={`${trade.pair}-${i}`} className="table-row-hover">
                            <td className="muted" style={{ fontSize: 11 }}>{i + 1}</td>
                            <td><strong>{trade.pair}</strong></td>
                            <td className={trade.profit >= 0 ? 'positive' : 'negative'}>
                              {formatPct(trade.profit)}
                            </td>
                            <td className={trade.profit_abs >= 0 ? 'positive' : 'negative'}>
                              {formatNumber(trade.profit_abs)}
                            </td>
                            <td className="muted" style={{ fontSize: 12 }}>{formatDate(trade.open_date)}</td>
                            <td className="muted" style={{ fontSize: 12 }}>{formatDate(trade.close_date)}</td>
                            <td>
                              <span className="exit-badge">{trade.exit_reason || '—'}</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ),
              },
              {
                id: 'chart',
                label: 'Chart',
                content: (
                  <EquityChart
                    points={equityPoints}
                    startBalance={detail.starting_balance}
                  />
                ),
              },
              {
                id: 'diagnosis',
                label: issueCount > 0 ? `Diagnosis (${issueCount})` : 'Diagnosis',
                content: <DiagnosisPanel data={diagnosis} />,
              },
              {
                id: 'params',
                label: 'Params',
                content: <ParamsPanel params={detail.params} />,
              },
              {
                id: 'diff',
                label: 'Diff',
                content: <DiffPanel data={diff} />,
              },
            ]}
          />
        </>
      ) : (
        !loading && <div className="empty-state">Select a run from the dropdown above.</div>
      )}
    </div>
  );
}
