import { Download, Play, Square } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api/client';
import { MetricCard } from '../components/MetricCard';
import { StatusBadge } from '../components/StatusBadge';
import { useAutosave } from '../hooks/useAutosave';
import { useSSE } from '../hooks/useSSE';
import type { BacktestStatus, PreferenceSection, RunDetailResponse, StrategyResponse } from '../types/api';
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

export function BacktestPage() {
  const [strategies, setStrategies] = useState<StrategyResponse[]>([]);
  const [availablePairs, setAvailablePairs] = useState<string[]>([]);
  const [prefs, setPrefs] = useState<PreferenceSection>({
    last_strategy: '',
    default_timeframe: '5m',
    default_timerange: '',
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
  const [loadingResult, setLoadingResult] = useState(false);
  const logRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    async function load() {
      const [settings, strategyList, pairs] = await Promise.all([
        api.settings(),
        api.strategies(),
        api.pairs()
      ]);
      setPrefs((current) => ({ ...current, ...settings.backtest_preferences }));
      setStrategies(strategyList);
      setAvailablePairs(pairs.pairs);
      setReady(true);
    }
    void load().catch(() => undefined);
  }, []);

  const saveState = useAutosave(
    prefs,
    (value) => api.updateSettings({ backtest_preferences: value }),
    { enabled: ready, delay: 500 }
  );

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
          if (ok && payload.run_id) {
            setLoadingResult(true);
            void api.run(payload.run_id)
              .then(setRunDetail)
              .catch(() => undefined)
              .finally(() => setLoadingResult(false));
          }
        } catch {
          // ignore parse errors
        }
        setStreaming(false);
      }
    },
    onError() {
      setStreaming(false);
    }
  });

  // Poll status as fallback when not streaming
  useEffect(() => {
    if (streaming) return;
    const interval = window.setInterval(() => {
      void api.backtestStatus().then((s) => {
        setStatus(s);
        if (s.status === 'complete' && s.run_id && !runDetail && !loadingResult) {
          setLoadingResult(true);
          void api.run(s.run_id)
            .then(setRunDetail)
            .catch(() => undefined)
            .finally(() => setLoadingResult(false));
        }
      }).catch(() => undefined);
    }, 2000);
    return () => window.clearInterval(interval);
  }, [streaming, runDetail, loadingResult]);

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [log]);

  const selectedPairs = useMemo(() => csvToList(prefs.default_pairs), [prefs.default_pairs]);

  // Compute active step
  const hasStrategy = Boolean(prefs.last_strategy);
  const hasPairs = selectedPairs.length > 0;
  const isRunning = status.status === 'running';

  const step1Active = !hasStrategy;
  const step2Active = hasStrategy && !hasPairs;
  const step3Active = (hasStrategy && hasPairs) || isRunning;

  function applyPreset(p: string) {
    setPreset(p);
    if (p !== 'Custom' && PRESETS[p]) {
      setPrefs((prev) => ({ ...prev, default_timerange: buildTimerange(PRESETS[p]) }));
    }
  }

  async function runBacktest() {
    setLog('');
    setStatus({ status: 'running' });
    setStreaming(true);
    setRunDetail(null);
    try {
      const response = await api.executeBacktest({
        strategy: prefs.last_strategy || strategies[0]?.name || '',
        timeframe: prefs.default_timeframe || '5m',
        timerange: prefs.default_timerange || undefined,
        pairs: selectedPairs,
        dry_run_wallet: Number(prefs.dry_run_wallet ?? 80),
        max_open_trades: Number(prefs.max_open_trades ?? 2)
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
        timeframe: prefs.default_timeframe || '5m',
        timerange: prefs.default_timerange || undefined,
        pairs: selectedPairs
      });
    } catch {
      // errors surfaced via status
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Backtest</h1>
          <p>Every edit is persisted to settings automatically.</p>
        </div>
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
              value={prefs.last_strategy ?? ''}
              onChange={(e) => setPrefs({ ...prefs, last_strategy: e.target.value })}
            >
              <option value="">Select strategy</option>
              {strategies.map((s) => (
                <option key={s.name} value={s.name}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Timeframe
            <select
              value={prefs.default_timeframe ?? '5m'}
              onChange={(e) => setPrefs({ ...prefs, default_timeframe: e.target.value })}
            >
              {TIMEFRAMES.map((tf) => (
                <option key={tf} value={tf}>
                  {tf}
                </option>
              ))}
            </select>
          </label>
          <label>
            Preset
            <select value={preset} onChange={(e) => applyPreset(e.target.value)}>
              {[...Object.keys(PRESETS), 'Custom'].map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
          <label>
            Timerange
            <input
              value={prefs.default_timerange ?? ''}
              onChange={(e) => {
                setPreset('Custom');
                setPrefs({ ...prefs, default_timerange: e.target.value });
              }}
              placeholder="20240101-20241231"
            />
          </label>
          <label>
            Wallet
            <input
              type="number"
              min="0"
              value={prefs.dry_run_wallet ?? 80}
              onChange={(e) => setPrefs({ ...prefs, dry_run_wallet: Number(e.target.value) })}
            />
          </label>
          <label>
            Max trades
            <input
              type="number"
              min="1"
              value={prefs.max_open_trades ?? 2}
              onChange={(e) => setPrefs({ ...prefs, max_open_trades: Number(e.target.value) })}
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
                  setPrefs({ ...prefs, default_pairs: next.join(', ') });
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
            disabled={status.status === 'running'}
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
        {status.status === 'running' && <div className="loading-bar" />}
        <div className="panel">
          <pre ref={logRef} className="terminal" style={{ minHeight: 200 }}>
            {log || (status.message ?? 'Backtest output will appear here.')}
          </pre>
        </div>

        {/* Results panels — shown after successful completion */}
        {loadingResult && <div className="loading-bar" />}
        {runDetail && (
          <>
            {/* Panel 1 — Key metrics */}
            <div className="panel">
              <div className="panel-header">
                <strong>Results — {runDetail.strategy}</strong>
                <span className="muted" style={{ fontSize: 12, marginLeft: 8 }}>
                  {runDetail.timeframe} · {runDetail.timerange || 'all time'}
                </span>
              </div>
              <div className="metric-grid" style={{ marginTop: 'var(--space-3)' }}>
                <MetricCard
                  label="Profit"
                  value={formatPct(runDetail.profit_total_pct)}
                  detail={`${formatNumber(runDetail.profit_total_abs)} USDT`}
                  tone={runDetail.profit_total_pct >= 0 ? 'good' : 'bad'}
                />
                <MetricCard
                  label="Win rate"
                  value={formatPct(runDetail.win_rate_pct)}
                  detail={`${runDetail.wins}W / ${runDetail.losses}L`}
                  tone={runDetail.win_rate_pct >= 50 ? 'good' : 'neutral'}
                />
                <MetricCard
                  label="Drawdown"
                  value={formatPct(runDetail.max_drawdown_pct)}
                  tone="warn"
                />
                <MetricCard
                  label="Trades"
                  value={runDetail.trades_count}
                  detail={runDetail.pairs?.slice(0, 2).join(', ') + ((runDetail.pairs?.length ?? 0) > 2 ? '…' : '')}
                />
                <MetricCard
                  label="Final balance"
                  value={formatNumber(runDetail.final_balance)}
                  detail={`Start: ${formatNumber(runDetail.starting_balance)}`}
                  tone={runDetail.final_balance >= runDetail.starting_balance ? 'good' : 'bad'}
                />
                <MetricCard
                  label="Sharpe"
                  value={runDetail.sharpe != null ? runDetail.sharpe.toFixed(3) : '—'}
                  detail={`Profit factor: ${runDetail.profit_factor.toFixed(2)}`}
                />
              </div>
            </div>

            {/* Panel 2 — Trades table */}
            <div className="panel">
              <div className="panel-header">
                <strong>Trades ({runDetail.trades_count})</strong>
              </div>
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
                    {runDetail.trades.map((trade, i) => (
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
            </div>
          </>
        )}
      </section>
    </div>
  );
}
