import { Download, Plus, Square, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import { TimerangePicker } from '../components/TimerangePicker';
import { useAutosave } from '../hooks/useAutosave';
import type { SharedInputsConfig } from '../types/api';

const TIMEFRAMES = ['1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d'];
const COMMON_PAIRS = [
  'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'ADA/USDT', 'XRP/USDT',
  'SOL/USDT', 'DOGE/USDT', 'DOT/USDT', 'MATIC/USDT', 'AVAX/USDT',
  'LINK/USDT', 'UNI/USDT', 'LTC/USDT', 'ATOM/USDT', 'NEAR/USDT',
];

export function DownloadPage() {
  const [sharedPrefs, setSharedPrefs] = useState<SharedInputsConfig>({
    default_timeframe: '5m',
    default_timerange: '',
    last_timerange_preset: '30d',
    default_pairs: '',
    dry_run_wallet: 80,
    max_open_trades: 2,
  });
  const [downloadPrefs, setDownloadPrefs] = useState({ prepend: false, erase: false });
  const [pairs, setPairs] = useState<string[]>([]);
  const [pairInput, setPairInput] = useState('');
  const [ready, setReady] = useState(false);
  const [status, setStatus] = useState<{ status: string; message?: string }>({ status: 'idle' });
  const [log, setLog] = useState('');
  const logRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    void api.settings().then((s) => {
      const si = s.shared_inputs;
      const dp = s.download_preferences;
      setSharedPrefs({
        default_timeframe: si.default_timeframe,
        default_timerange: si.default_timerange,
        last_timerange_preset: si.last_timerange_preset,
        default_pairs: si.default_pairs,
        dry_run_wallet: si.dry_run_wallet,
        max_open_trades: si.max_open_trades,
      });
      setDownloadPrefs({ prepend: dp.prepend ?? false, erase: dp.erase ?? false });
      const savedPairs = (si.default_pairs ?? '')
        .split(',')
        .map((p) => p.trim())
        .filter(Boolean);
      setPairs(savedPairs);
      setReady(true);
    });
  }, []);

  // Sync pairs list back into sharedPrefs for autosave
  const sharedPrefsWithPairs: SharedInputsConfig = { ...sharedPrefs, default_pairs: pairs.join(', ') };

  const saveStateShared = useAutosave(
    sharedPrefsWithPairs,
    (value) => api.updateSharedInputs(value),
    { enabled: ready, delay: 500 }
  );

  const saveStateDownload = useAutosave(
    downloadPrefs,
    (value) => api.updateSettings({ download_preferences: value }),
    { enabled: ready, delay: 500 }
  );

  const saveState = saveStateShared === 'saving' || saveStateDownload === 'saving' ? 'saving' : saveStateShared;

  function addPair() {
    const p = pairInput.trim().toUpperCase();
    if (p && !pairs.includes(p)) {
      setPairs([...pairs, p]);
    }
    setPairInput('');
  }

  function removePair(pair: string) {
    setPairs(pairs.filter((p) => p !== pair));
  }

  function quickAdd(pair: string) {
    if (!pairs.includes(pair)) setPairs([...pairs, pair]);
  }

  async function startDownload() {
    if (!pairs.length) {
      setLog('⚠ No pairs selected.\n');
      return;
    }
    setLog('Starting download…\n');
    setStatus({ status: 'running' });
    try {
      const response = await api.downloadData({
        timeframe: sharedPrefs.default_timeframe ?? '5m',
        timerange: sharedPrefs.default_timerange || undefined,
        pairs,
      });
      setLog((prev) => prev + (response.message ?? '') + '\n');
      setStatus({ status: response.success ? 'complete' : 'error', message: response.message });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setLog((prev) => prev + `✗ ${msg}\n`);
      setStatus({ status: 'error', message: msg });
    }
  }

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [log]);

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Download Data</h1>
          <p>Download OHLCV candle data for backtesting.</p>
        </div>
        <div className="toolbar">
          <StatusBadge status={status.status} />
          <span className={`save-state state-${saveState}`}>{saveState}</span>
          <button
            className="button primary"
            type="button"
            onClick={() => void startDownload()}
            disabled={status.status === 'running'}
          >
            <Download size={16} />
            Download
          </button>
          <button
            className="button ghost"
            type="button"
            onClick={() => setStatus({ status: 'idle' })}
          >
            <Square size={16} />
            Reset
          </button>
        </div>
      </header>

      <section className="split-layout">
        <div className="panel form-grid">
          <div className="panel-header" style={{ gridColumn: '1 / -1' }}>
            <h2>Configuration</h2>
          </div>
          <label>
            Timeframe
            <select
              value={sharedPrefs.default_timeframe ?? '5m'}
              onChange={(e) => setSharedPrefs({ ...sharedPrefs, default_timeframe: e.target.value })}
            >
              {TIMEFRAMES.map((tf) => (
                <option key={tf} value={tf}>
                  {tf}
                </option>
              ))}
            </select>
          </label>
          <label>
            Timerange
            <TimerangePicker
              value={sharedPrefs.default_timerange ?? ''}
              onChange={(value) => setSharedPrefs({ ...sharedPrefs, default_timerange: value })}
              placeholder="20240101-20241231"
            />
          </label>
          <label className="check-row" style={{ gridColumn: '1 / -1' }}>
            <input
              type="checkbox"
              checked={downloadPrefs.prepend ?? false}
              onChange={(e) => setDownloadPrefs({ ...downloadPrefs, prepend: e.target.checked })}
            />
            Prepend data (fill gaps at start)
          </label>
          <label className="check-row" style={{ gridColumn: '1 / -1' }}>
            <input
              type="checkbox"
              checked={downloadPrefs.erase ?? false}
              onChange={(e) => setDownloadPrefs({ ...downloadPrefs, erase: e.target.checked })}
            />
            Erase existing data before download
          </label>

          <div style={{ gridColumn: '1 / -1' }}>
            <div className="panel-header" style={{ marginBottom: 8 }}>
              <h2>Pairs</h2>
              <span className="muted">{pairs.length} selected</span>
            </div>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <input
                value={pairInput}
                onChange={(e) => setPairInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addPair()}
                placeholder="BTC/USDT"
                style={{ flex: 1 }}
              />
              <button className="button" type="button" onClick={addPair}>
                <Plus size={16} />
              </button>
            </div>
            <div className="chip-grid" style={{ marginBottom: 10 }}>
              {pairs.map((pair) => (
                <span key={pair} className="chip active" style={{ gap: 6 }}>
                  {pair}
                  <button
                    type="button"
                    onClick={() => removePair(pair)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: 'inherit' }}
                  >
                    <X size={12} />
                  </button>
                </span>
              ))}
            </div>
            <div style={{ marginBottom: 4 }}>
              <span className="muted" style={{ fontSize: 12 }}>Quick add:</span>
            </div>
            <div className="chip-grid">
              {COMMON_PAIRS.map((pair) => (
                <button
                  key={pair}
                  className={pairs.includes(pair) ? 'chip active' : 'chip'}
                  type="button"
                  onClick={() => quickAdd(pair)}
                >
                  {pair}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="panel" style={{ display: 'grid', gap: 8 }}>
          <div className="panel-header">
            <h2>Output</h2>
            <button className="button ghost" type="button" onClick={() => setLog('')} style={{ fontSize: 12 }}>
              Clear
            </button>
          </div>
          <pre ref={logRef} className="terminal" style={{ minHeight: 320 }}>
            {log || 'Download output will appear here.'}
          </pre>
        </div>
      </section>
    </div>
  );
}
