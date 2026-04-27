import { ChevronDown, Download, Play, Square, TrendingDown, TrendingUp } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api/client';
import { MetricCard } from '../components/MetricCard';
import { StatusBadge } from '../components/StatusBadge';
import { Tabs } from '../components/Tabs';
import { TimerangePicker } from '../components/TimerangePicker';
import { useAutosave } from '../hooks/useAutosave';
import { useSSE } from '../hooks/useSSE';
import type { BacktestStatus, RunDetailResponse, RunResponse, SharedInputsConfig, StrategyResponse } from '../types/api';
import { csvToList, formatDate, formatNumber, formatPct } from '../utils/format';

const TIMEFRAMES = ['1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d'];
const PRESETS: Record<string, number> = { '7d': 7, '14d': 14, '30d': 30, '90d': 90, '180d': 180, '360d': 360 };

function buildTimerange(days: number): string {
  const end = new Date();
  const start = new Date(end.getTime() - days * 86_400_000);
  const fmt = (d: Date) =>
    `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
  return `${fmt(start)}-${fmt(end)}`;
}

// ─── Equity chart ─────────────────────────────────────────────────────────────

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

  const firstX = toX(0).toFixed(1);
  const lastX  = toX(points.length - 1).toFixed(1);
  const areaPath = `M ${firstX},${toY(points[0].balance).toFixed(1)} `
    + points.slice(1).map((p, i) => `L ${toX(i + 1).toFixed(1)},${toY(p.balance).toFixed(1)}`).join(' ')
    + ` L ${lastX},${zeroY.toFixed(1)} L ${firstX},${zeroY.toFixed(1)} Z`;

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
          <linearGradient id="bt-eq-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"   stopColor={lineColor} stopOpacity="0.22" />
            <stop offset="100%" stopColor={lineColor} stopOpacity="0.01" />
          </linearGradient>
          <clipPath id="bt-eq-clip">
            <rect x={PAD.left} y={PAD.top} width={innerW} height={innerH} />
          </clipPath>
        </defs>
        {ticks.map(({ v, y }) => (
          <g key={v}>
            <line x1={PAD.left} y1={y} x2={W - PAD.right} y2={y}
              stroke="var(--border)" strokeWidth="1" strokeDasharray="4 4" />
            <text x={PAD.left - 8} y={y + 4} textAnchor="end" fontSize="11" fill="var(--muted)">
              {formatNumber(v)}
            </text>
          </g>
        ))}
        {zeroY >= PAD.top && zeroY <= PAD.top + innerH && (
          <line x1={PAD.left} y1={zeroY} x2={W - PAD.right} y2={zeroY}
            stroke="var(--muted)" strokeWidth="1" strokeDasharray="6 3" opacity="0.6" />
        )}
        <path d={areaPath} fill="url(#bt-eq-fill)" clipPath="url(#bt-eq-clip)" />
        <polyline points={linePts} fill="none" stroke={lineColor} strokeWidth="2.5"
          strokeLinejoin="round" strokeLinecap="round" clipPath="url(#bt-eq-clip)" />
        {hover && (
          <>
            <line x1={hover.x} y1={PAD.top} x2={hover.x} y2={PAD.top + innerH}
              stroke="var(--muted)" strokeWidth="1" strokeDasharray="3 3" opacity="0.7" />
            <circle cx={hover.x} cy={hover.y} r="5"
              fill={lineColor} stroke="var(--surface)" strokeWidth="2" />
            <g transform={`translate(${Math.min(hover.x + 10, W - 130)},${Math.max(hover.y - 36, PAD.top)})`}>
              <rect rx="5" ry="5" width="118" height="38"
                fill="var(--surface-3)" stroke="var(--border)" strokeWidth="1" />
              <text x="9" y="14" fontSize="10" fill="var(--muted)">Trade #{hover.idx + 1}</text>
              <text x="9" y="29" fontSize="13" fontWeight="600" fill={lineColor}>
                {formatNumber(hover.balance)}
              </text>
            </g>
          </>
        )}
        <text x={PAD.left + innerW / 2} y={H - 4} textAnchor="middle" fontSize="11" fill="var(--muted)">
          Trades
        </text>
      </svg>
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

// ─── Diagnosis panel ──────────────────────────────────────────────────────────

interface DiagIssue { rule_id?: string; message?: string; severity?: string }
interface DiagData  { issues?: DiagIssue[]; suggestions?: DiagIssue[]; error?: string }

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

function DiagnosisPanel({ data }: { data: unknown }) {
  const d = data as DiagData | null;
  if (!d || d.error) {
    return (
      <div className="diag-empty">
        <span className="diag-badge diag-info">ℹ</span>
        {(d as DiagData | null)?.error ?? 'No diagnosis data available for this run.'}
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
                <span className={severityClass(issue.severity ?? '')}>{severityIcon(issue.severity ?? '')}</span>
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
                <span className={severityClass(s.severity ?? '')}>{severityIcon(s.severity ?? '')}</span>
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

// ─── Params panel ─────────────────────────────────────────────────────────────

function ParamsPanel({ params }: { params: Record<string, unknown> }) {
  const entries = Object.entries(params ?? {});
  if (!entries.length) return <div className="diag-empty">No parameters saved for this run.</div>;
  return (
    <div className="params-table-wrap">
      <table className="params-table">
        <thead><tr><th>Parameter</th><th>Value</th></tr></thead>
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

// ─── Diff panel ───────────────────────────────────────────────────────────────

interface DiffChange { param?: string; key?: string; before?: unknown; after?: unknown; old?: unknown; new?: unknown }
interface DiffData   { parameter_changes?: DiffChange[]; has_code_diff?: boolean; error?: string }

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
              <thead><tr><th>Parameter</th><th>Before</th><th>After</th></tr></thead>
              <tbody>
                {changes.map((c, i) => {
                  const name   = c.param ?? c.key ?? `change_${i}`;
                  const before = c.before ?? c.old;
                  const after  = c.after  ?? c.new;
                  const improved = typeof after === 'number' && typeof before === 'number' ? after > before : null;
                  return (
                    <tr key={i}>
                      <td className="param-key">{name}</td>
                      <td className="param-val diff-before"><code>{String(before ?? '—')}</code></td>
                      <td className="param-val" style={{ color: improved === true ? 'var(--green)' : improved === false ? 'var(--red)' : undefined }}>
                        <code>{String(after ?? '—')}</code>
                        {improved === true && ' ↑'}{improved === false && ' ↓'}
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

// ─── RunResultDetail — inline run detail shown after backtest completes ────────

interface RunResultDetailProps {
  detail: RunDetailResponse;
  diagnosis: unknown;
  diff: unknown;
}

function RunResultDetail({ detail, diagnosis, diff }: RunResultDetailProps) {
  const [activeTab, setActiveTab] = useState('trades');

  const equityPoints = useMemo(() => {
    let balance = detail.starting_balance;
    return detail.trades.map((trade, index) => {
      balance += trade.profit_abs;
      return { index, balance };
    });
  }, [detail]);

  const diagData = diagnosis as { issues?: unknown[]; suggestions?: unknown[] } | null;
  const issueCount = (diagData?.issues?.length ?? 0) + (diagData?.suggestions?.length ?? 0);

  return (
    <>
      {/* Metric strip */}
      <div className="metric-grid">
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
          detail={detail.pairs?.slice(0, 2).join(', ') + ((detail.pairs?.length ?? 0) > 2 ? '…' : '')}
        />
        <MetricCard
          label="Final balance"
          value={formatNumber(detail.final_balance)}
          detail={`Start: ${formatNumber(detail.starting_balance)}`}
          tone={detail.final_balance >= detail.starting_balance ? 'good' : 'bad'}
        />
        <MetricCard
          label="Sharpe"
          value={detail.sharpe != null ? detail.sharpe.toFixed(3) : '—'}
          detail={`Profit factor: ${detail.profit_factor.toFixed(2)}`}
        />
      </div>

      {/* Tabbed detail */}
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
                      <th>#</th><th>Pair</th><th>Profit %</th><th>Abs</th>
                      <th>Open</th><th>Close</th><th>Exit reason</th>
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
                        <td><span className="exit-badge">{trade.exit_reason || '—'}</span></td>
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
            content: <EquityChart points={equityPoints} startBalance={detail.starting_balance} />,
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
  );
}

// ─── RunDropdown — colour-coded custom run picker ────────────────────────────

interface RunDropdownProps {
  runs: RunResponse[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

function RunDropdown({ runs, selectedId, onSelect }: RunDropdownProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const selected = runs.find((r) => r.run_id === selectedId) ?? null;

  // Close on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div className="run-dropdown" ref={ref}>
      <button
        type="button"
        className="run-dropdown-trigger"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        {selected ? (
          <>
            <span className="run-dropdown-date">{formatDate(selected.saved_at)}</span>
            <span className="run-dropdown-strategy">{selected.strategy}</span>
            <span
              className="run-dropdown-profit"
              style={{ color: selected.profit_total_pct >= 0 ? 'var(--green)' : 'var(--red)' }}
            >
              {formatPct(selected.profit_total_pct)}
            </span>
          </>
        ) : (
          <span className="run-dropdown-placeholder">Browse saved runs…</span>
        )}
        <ChevronDown size={14} className="run-dropdown-chevron" />
      </button>

      {open && (
        <ul className="run-dropdown-list" role="listbox">
          {runs.map((run) => {
            const profit = run.profit_total_pct;
            const isPos = profit >= 0;
            const isSelected = run.run_id === selectedId;
            return (
              <li
                key={run.run_id}
                role="option"
                aria-selected={isSelected}
                className={`run-dropdown-item${isSelected ? ' selected' : ''}`}
                onClick={() => { onSelect(run.run_id); setOpen(false); }}
              >
                <span className="run-dropdown-date">{formatDate(run.saved_at)}</span>
                <span className="run-dropdown-strategy">{run.strategy}</span>
                <span
                  className="run-dropdown-profit"
                  style={{ color: isPos ? 'var(--green)' : 'var(--red)' }}
                >
                  {formatPct(profit)}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

// ─── BacktestPage ─────────────────────────────────────────────────────────────

export function BacktestPage() {
  const [strategies, setStrategies] = useState<StrategyResponse[]>([]);
  const [availablePairs, setAvailablePairs] = useState<string[]>([]);
  const [runs, setRuns] = useState<RunResponse[]>([]);
  const [lastStrategy, setLastStrategy] = useState('');
  const [sharedPrefs, setSharedPrefs] = useState<SharedInputsConfig>({
    default_timeframe: '5m',
    default_timerange: '',
    last_timerange_preset: '30d',
    default_pairs: 'BTC/USDT',
    dry_run_wallet: 80,
    max_open_trades: 2
  });
  const [preset, setPreset] = useState('30d');
  const [ready, setReady] = useState(false);
  const [status, setStatus] = useState<BacktestStatus>({ status: 'idle' });
  const [log, setLog] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [runDetail, setRunDetail] = useState<RunDetailResponse | null>(null);
  const [diagnosis, setDiagnosis] = useState<unknown>(null);
  const [diff, setDiff] = useState<unknown>(null);
  const [loadingResult, setLoadingResult] = useState(false);
  const logRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    async function load() {
      const [settings, strategyList, pairs, runList] = await Promise.all([
        api.settings(),
        api.strategies(),
        api.pairs(),
        api.runs().catch(() => [] as RunResponse[]),
      ]);
      setSharedPrefs((current) => ({ ...current, ...settings.shared_inputs }));
      setLastStrategy(settings.backtest_preferences.last_strategy ?? '');
      setStrategies(strategyList);
      setAvailablePairs(pairs.pairs);
      setRuns(runList);
      setReady(true);
    }
    void load().catch(() => undefined);
  }, []);

  const saveState = useAutosave(
    sharedPrefs,
    (value) => api.updateSharedInputs(value),
    { enabled: ready, delay: 500 }
  );
  useAutosave(
    lastStrategy,
    (value) => api.updateSettings({ backtest_preferences: { last_strategy: value } }),
    { enabled: ready, delay: 500 }
  );

  function fetchRunDetail(runId: string) {
    setLoadingResult(true);
    void Promise.all([
      api.run(runId),
      api.diagnosis(runId).catch((e) => ({ error: e instanceof Error ? e.message : String(e) })),
      api.diff(runId).catch((e) => ({ error: e instanceof Error ? e.message : String(e) })),
    ])
      .then(([rd, diag, df]) => {
        setRunDetail(rd);
        setDiagnosis(diag);
        setDiff(df);
        // refresh run list so the selector stays current
        void api.runs().then(setRuns).catch(() => undefined);
      })
      .catch(() => undefined)
      .finally(() => setLoadingResult(false));
  }

  // SSE live output
  useSSE({
    url: streaming ? '/api/process/stream' : null,
    onMessage(data, event) {
      if (event === 'output') {
        setLog((prev) => prev + data + '\n');
      } else if (event === 'complete') {
        try {
          const payload = JSON.parse(data) as { exit_code: number; run_id?: string };
          const ok = payload.exit_code === 0;
          setStatus({ status: ok ? 'complete' : 'error', message: ok ? 'Backtest completed.' : `Exit ${payload.exit_code}`, run_id: payload.run_id });
          setLog((prev) => prev + (ok ? '\n✓ Completed.\n' : `\n✗ Failed (exit ${payload.exit_code}).\n`));
          if (ok && payload.run_id) fetchRunDetail(payload.run_id);
        } catch { /* ignore */ }
        setStreaming(false);
      }
    },
    onError() { setStreaming(false); }
  });

  // Poll status as fallback when not streaming
  useEffect(() => {
    if (streaming) return;
    const interval = window.setInterval(() => {
      void api.backtestStatus().then((s) => {
        setStatus(s);
        if (s.status === 'complete' && s.run_id && !runDetail && !loadingResult) {
          fetchRunDetail(s.run_id);
        }
      }).catch(() => undefined);
    }, 2000);
    return () => window.clearInterval(interval);
  }, [streaming, runDetail, loadingResult]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [log]);

  const selectedPairs = useMemo(() => csvToList(sharedPrefs.default_pairs), [sharedPrefs.default_pairs]);

  const hasStrategy = Boolean(lastStrategy);
  const hasPairs = selectedPairs.length > 0;
  const isRunning = status.status === 'running';

  const step1Active = !hasStrategy;
  const step2Active = hasStrategy && !hasPairs;
  const step3Active = (hasStrategy && hasPairs) || isRunning;

  function applyPreset(p: string) {
    setPreset(p);
    if (p !== 'Custom' && PRESETS[p]) {
      setSharedPrefs((prev) => ({ ...prev, default_timerange: buildTimerange(PRESETS[p]) }));
    }
  }

  async function runBacktest() {
    setLog('');
    setStatus({ status: 'running' });
    setStreaming(true);
    setRunDetail(null);
    setDiagnosis(null);
    setDiff(null);
    try {
      const response = await api.executeBacktest({
        strategy: lastStrategy || strategies[0]?.name || '',
        timeframe: sharedPrefs.default_timeframe || '5m',
        timerange: sharedPrefs.default_timerange || undefined,
        pairs: selectedPairs,
        dry_run_wallet: Number(sharedPrefs.dry_run_wallet ?? 80),
        max_open_trades: Number(sharedPrefs.max_open_trades ?? 2)
      });
      setLog(`$ freqtrade backtesting ...\n\n`);
      if (response.status !== 'started') {
        setStatus({ status: 'error', message: response.message });
        setStreaming(false);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatus({ status: 'error', message: msg });
      setStreaming(false);
    }
  }

  async function stopBacktest() {
    setStreaming(false);
    try {
      const response = await api.stopBacktest();
      setStatus(response as BacktestStatus);
      setLog((prev) => prev + '\n■ Stopped by user.\n');
    } catch (err) {
      setStatus({ status: 'error', message: err instanceof Error ? err.message : String(err) });
    }
  }

  async function downloadData() {
    try {
      await api.downloadData({
        timeframe: sharedPrefs.default_timeframe || '5m',
        timerange: sharedPrefs.default_timerange || undefined,
        pairs: selectedPairs
      });
    } catch { /* errors surfaced via status */ }
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Backtest</h1>
          <p>
            {runDetail
              ? `${runDetail.strategy} · ${runDetail.timeframe} · ${runDetail.timerange || 'all time'}`
              : 'Every edit is persisted to settings automatically.'}
          </p>
        </div>
        {/* Run history selector */}
        {runs.length > 0 && (
          <RunDropdown
            runs={[...runs].sort((a, b) => new Date(b.saved_at).getTime() - new Date(a.saved_at).getTime())}
            selectedId={runDetail?.run_id ?? null}
            onSelect={fetchRunDetail}
          />
        )}
      </header>

      {(status.status === 'complete' || status.status === 'error') && (
        <div className={`alert ${status.status === 'error' ? 'error' : 'success'}`}>
          {status.message ?? (status.status === 'complete' ? 'Backtest completed.' : 'An error occurred.')}
        </div>
      )}

      {/* Step 1 — Configure */}
      <section className={`workflow-step${step1Active ? ' active' : ''}`}>
        <div className="workflow-step-header">
          <span className="step-badge">1</span>
          <h2>Configure</h2>
        </div>
        <form className="panel form-grid" onSubmit={(e) => e.preventDefault()}>
          <label>
            Strategy
            <select
              value={lastStrategy}
              onChange={(e) => setLastStrategy(e.target.value)}
            >
              <option value="">Select strategy</option>
              {strategies.map((s) => (
                <option key={s.name} value={s.name}>{s.name}</option>
              ))}
            </select>
          </label>
          <label>
            Timeframe
            <select
              value={sharedPrefs.default_timeframe ?? '5m'}
              onChange={(e) => setSharedPrefs({ ...sharedPrefs, default_timeframe: e.target.value })}
            >
              {TIMEFRAMES.map((tf) => <option key={tf} value={tf}>{tf}</option>)}
            </select>
          </label>
          <label>
            Preset
            <select value={preset} onChange={(e) => applyPreset(e.target.value)}>
              {[...Object.keys(PRESETS), 'Custom'].map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </label>
          <label>
            Timerange
            <TimerangePicker
              value={sharedPrefs.default_timerange ?? ''}
              onChange={(value) => { setPreset('Custom'); setSharedPrefs({ ...sharedPrefs, default_timerange: value }); }}
              placeholder="20240101-20241231"
            />
          </label>
          <label>
            Wallet
            <input
              type="number" min="0"
              value={sharedPrefs.dry_run_wallet ?? 80}
              onChange={(e) => setSharedPrefs({ ...sharedPrefs, dry_run_wallet: Number(e.target.value) })}
            />
          </label>
          <label>
            Max trades
            <input
              type="number" min="1"
              value={sharedPrefs.max_open_trades ?? 2}
              onChange={(e) => setSharedPrefs({ ...sharedPrefs, max_open_trades: Number(e.target.value) })}
            />
          </label>
        </form>
      </section>

      {/* Step 2 — Pairs */}
      <section className={`workflow-step${step2Active ? ' active' : ''}`}>
        <div className="workflow-step-header">
          <span className="step-badge">2</span>
          <h2>Pairs</h2>
        </div>
        <div className="panel">
          <div className="chip-grid">
            {availablePairs.map((pair) => (
              <button
                key={pair}
                className={selectedPairs.includes(pair) ? 'chip active' : 'chip'}
                type="button"
                onClick={() => {
                  const next = selectedPairs.includes(pair)
                    ? selectedPairs.filter((p) => p !== pair)
                    : [...selectedPairs, pair];
                  setSharedPrefs({ ...sharedPrefs, default_pairs: next.join(', ') });
                }}
              >
                {pair}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Step 3 — Run & Monitor */}
      <section className={`workflow-step${step3Active ? ' active' : ''}`}>
        <div className="workflow-step-header">
          <span className="step-badge">3</span>
          <h2>Run &amp; Monitor</h2>
          <StatusBadge status={status.status} />
          <span className={`save-state state-${saveState}`}>{saveState}</span>
        </div>
        <div className="button-row">
          <button
            className="button primary"
            type="button"
            onClick={() => void runBacktest()}
            disabled={isRunning}
          >
            <Play size={16} />
            Start
          </button>
          <button className="button" type="button" onClick={() => void stopBacktest()}>
            <Square size={16} />
            Stop
          </button>
          <button className="button ghost" type="button" onClick={() => void downloadData()}>
            <Download size={16} />
            Download
          </button>
        </div>

        {isRunning && <div className="loading-bar" />}

        {/* Terminal — always visible while running or when there's output */}
        {(log || isRunning) && (
          <div className="panel">
            <pre ref={logRef} className="terminal" style={{ minHeight: 200 }}>
              {log || 'Backtest output will appear here.'}
            </pre>
          </div>
        )}

        {/* Inline run detail — shown after completion or when browsing saved runs */}
        {loadingResult && <div className="loading-bar" />}
        {runDetail && !loadingResult && (
          <RunResultDetail detail={runDetail} diagnosis={diagnosis} diff={diff} />
        )}

        {/* Idle placeholder */}
        {!isRunning && !log && !runDetail && !loadingResult && (
          <div className="panel">
            <pre className="terminal" style={{ minHeight: 200 }}>
              {status.message ?? 'Backtest output will appear here.'}
            </pre>
          </div>
        )}
      </section>
    </div>
  );
}
