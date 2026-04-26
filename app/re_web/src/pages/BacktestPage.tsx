import { Download, Play, Square } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import { useAutosave } from '../hooks/useAutosave';
import type { BacktestStatus, PreferenceSection, StrategyResponse } from '../types/api';
import { csvToList } from '../utils/format';

const timeframes = ['1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d'];

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
  const [ready, setReady] = useState(false);
  const [status, setStatus] = useState<BacktestStatus>({ status: 'idle' });
  const [message, setMessage] = useState('');

  useEffect(() => {
    async function load() {
      const [settings, strategyList, pairs] = await Promise.all([api.settings(), api.strategies(), api.pairs()]);
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

  useEffect(() => {
    const interval = window.setInterval(() => {
      void api.backtestStatus().then(setStatus).catch(() => undefined);
    }, 1600);
    return () => window.clearInterval(interval);
  }, []);

  const selectedPairs = useMemo(() => csvToList(prefs.default_pairs), [prefs.default_pairs]);

  async function runBacktest() {
    setMessage('');
    const response = await api.executeBacktest({
      strategy: prefs.last_strategy || strategies[0]?.name || '',
      timeframe: prefs.default_timeframe || '5m',
      timerange: prefs.default_timerange || undefined,
      pairs: selectedPairs,
      dry_run_wallet: Number(prefs.dry_run_wallet ?? 80),
      max_open_trades: Number(prefs.max_open_trades ?? 2)
    });
    setStatus({ status: response.status, run_id: response.run_id, message: response.message });
  }

  async function downloadData() {
    const response = await api.downloadData({
      timeframe: prefs.default_timeframe || '5m',
      timerange: prefs.default_timerange || undefined,
      pairs: selectedPairs
    });
    setMessage(response.message);
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
        <form className="panel form-grid" onSubmit={(event) => event.preventDefault()}>
          <label>
            Strategy
            <select
              value={prefs.last_strategy ?? ''}
              onChange={(event) => setPrefs({ ...prefs, last_strategy: event.target.value })}
            >
              <option value="">Select strategy</option>
              {strategies.map((strategy) => (
                <option key={strategy.name} value={strategy.name}>
                  {strategy.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Timeframe
            <select
              value={prefs.default_timeframe ?? '5m'}
              onChange={(event) => setPrefs({ ...prefs, default_timeframe: event.target.value })}
            >
              {timeframes.map((timeframe) => (
                <option key={timeframe} value={timeframe}>
                  {timeframe}
                </option>
              ))}
            </select>
          </label>
          <label>
            Timerange
            <input
              value={prefs.default_timerange ?? ''}
              onChange={(event) => setPrefs({ ...prefs, default_timerange: event.target.value })}
              placeholder="20240101-20241231"
            />
          </label>
          <label>
            Pairs
            <textarea
              value={prefs.default_pairs ?? ''}
              onChange={(event) => setPrefs({ ...prefs, default_pairs: event.target.value })}
              placeholder="BTC/USDT, ETH/USDT"
            />
          </label>
          <label>
            Wallet
            <input
              type="number"
              min="0"
              value={prefs.dry_run_wallet ?? 80}
              onChange={(event) => setPrefs({ ...prefs, dry_run_wallet: Number(event.target.value) })}
            />
          </label>
          <label>
            Max trades
            <input
              type="number"
              min="1"
              value={prefs.max_open_trades ?? 2}
              onChange={(event) => setPrefs({ ...prefs, max_open_trades: Number(event.target.value) })}
            />
          </label>
          <div className="button-row">
            <button className="button primary" type="button" onClick={() => void runBacktest()}>
              <Play size={16} />
              Start
            </button>
            <button className="button" type="button" onClick={() => void api.stopBacktest().then(setStatus)}>
              <Square size={16} />
              Stop
            </button>
            <button className="button ghost" type="button" onClick={() => void downloadData()}>
              <Download size={16} />
              Download
            </button>
          </div>
        </form>

        <aside className="panel">
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
                    ? selectedPairs.filter((item) => item !== pair)
                    : [...selectedPairs, pair];
                  setPrefs({ ...prefs, default_pairs: next.join(', ') });
                }}
              >
                {pair}
              </button>
            ))}
          </div>
          <pre className="terminal">{status.message || 'Backtest status will appear here.'}</pre>
        </aside>
      </section>
    </div>
  );
}
