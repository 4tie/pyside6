import { Download, Play, Square } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import { useAutosave } from '../hooks/useAutosave';
import { useSSE } from '../hooks/useSSE';
import type { BacktestStatus, PreferenceSection, StrategyResponse } from '../types/api';
import { csvToList } from '../utils/format';

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
  const [message, setMessage] = useState('');
  const [log, setLog] = useState('');
  const [streaming, setStreaming] = useState(false);
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
    void load().catch((err) => setMessage(err instanceof Error ? err.message : String(err)));
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
          const payload = JSON.parse(data) as { exit_code: number };
          const ok = payload.exit_code === 0;
          setStatus({ status: ok ? 'complete' : 'error', message: ok ? 'Backtest completed.' : `Exit ${payload.exit_code}` });
          setLog((prev) => prev + (ok ? '\n✓ Completed.\n' : `\n✗ Failed (exit ${payload.exit_code}).\n`));
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
      void api.backtestStatus().then(setStatus).catch(() => undefined);
    }, 2000);
    return () => window.clearInterval(interval);
  }, [streaming]);

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [log]);

  const selectedPairs = useMemo(() => csvToList(prefs.default_pairs), [prefs.default_pairs]);

  function applyPreset(p: string) {
    setPreset(p);
    if (p !== 'Custom' && PRESETS[p]) {
      setPrefs((prev) => ({ ...prev, default_timerange: buildTimerange(PRESETS[p]) }));
    }
  }

  async function runBacktest() {
    setMessage('');
    setLog('');
    setStatus({ status: 'running' });
    setStreaming(true);
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
      setMessage(msg);
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
      setMessage(err instanceof Error ? err.message : String(err));
    }
  }

  async function downloadData() {
    setMessage('');
    try {
      const response = await api.downloadData({
        timeframe: prefs.default_timeframe || '5m',
        timerange: prefs.default_timerange || undefined,
        pairs: selectedPairs
      });
      setMessage(response.message);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Backtest</h1>
          <p>Every edit is persisted to settings automatically.</p>
        </div>
        <div className="toolbar">
          <StatusBadge status={status.status} />
          <span className={`save-state state-${saveState}`}>{saveState}</span>
        </div>
      </header>

      {message ? <div className="alert">{message}</div> : null}

      <section className="split-layout">
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
          <label style={{ gridColumn: '1 / -1' }}>
            Pairs
            <textarea
              value={prefs.default_pairs ?? ''}
              onChange={(e) => setPrefs({ ...prefs, default_pairs: e.target.value })}
              placeholder="BTC/USDT, ETH/USDT"
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
          <div className="button-row" style={{ gridColumn: '1 / -1' }}>
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
        </form>

        <aside className="panel" style={{ display: 'grid', gap: 10 }}>
          <div className="panel-header">
            <h2>Pairs</h2>
            <span className="muted">{selectedPairs.length} selected</span>
          </div>
          <div className="chip-grid">
            {availablePairs.slice(0, 16).map((pair) => (
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
          <div className="panel-header" style={{ marginTop: 4 }}>
            <h2>Live Output</h2>
            <button className="button ghost" type="button" onClick={() => setLog('')} style={{ fontSize: 12 }}>
              Clear
            </button>
          </div>
          <pre ref={logRef} className="terminal" style={{ minHeight: 200 }}>
            {log || (status.message ?? 'Backtest output will appear here.')}
          </pre>
        </aside>
      </section>
    </div>
  );
}
