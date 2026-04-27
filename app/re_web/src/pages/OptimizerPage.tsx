import { Play, SlidersHorizontal, Square } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import { useAutosave } from '../hooks/useAutosave';
import { useSSE } from '../hooks/useSSE';
import type {
  OptimizerConfigResponse,
  OptimizerConfigUpdate,
  OptimizerSessionSummary,
  ParamDef,
  TrialRecord,
} from '../types/api';
import { formatDate, formatNumber } from '../utils/format';

const DEFAULT_CONFIG: OptimizerConfigResponse = {
  last_strategy: '',
  default_timeframe: '5m',
  last_timerange_preset: '30d',
  default_timerange: '',
  default_pairs: 'BTC/USDT',
  pairs_list: ['BTC/USDT'],
  dry_run_wallet: 80,
  max_open_trades: 2,
};

export function OptimizerPage() {
  const [strategies, setStrategies] = useState<string[]>([]);
  const [config, setConfig] = useState<OptimizerConfigResponse>(DEFAULT_CONFIG);
  const [params, setParams] = useState<ParamDef[]>([]);
  const [sessions, setSessions] = useState<OptimizerSessionSummary[]>([]);
  const [selectedSession, setSelectedSession] = useState('');
  const [trials, setTrials] = useState<TrialRecord[]>([]);
  const [liveLog, setLiveLog] = useState('');
  const [ready, setReady] = useState(false);
  const [message, setMessage] = useState('');
  const [streaming, setStreaming] = useState(false);
  const logRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    void loadAll();
  }, []);

  // Autosave: on every config change, PUT the seven InputHolder fields to the backend
  const saveState = useAutosave(
    config,
    (value) => {
      const update: OptimizerConfigUpdate = {
        last_strategy: value.last_strategy,
        default_timeframe: value.default_timeframe,
        last_timerange_preset: value.last_timerange_preset,
        default_timerange: value.default_timerange,
        default_pairs: value.default_pairs,
        dry_run_wallet: value.dry_run_wallet,
        max_open_trades: value.max_open_trades,
      };
      return api.updateOptimizerConfig(update).then((updated) => {
        // Sync back the server response (e.g. resolved timerange, deduplicated pairs)
        setConfig(updated);
      });
    },
    { enabled: ready, delay: 500 }
  );

  const pairs = useMemo(() => config.pairs_list, [config.pairs_list]);

  // SSE stream for selected session
  const sseUrl =
    streaming && selectedSession
      ? `/api/optimizer/sessions/${encodeURIComponent(selectedSession)}/stream`
      : null;

  useSSE({
    url: sseUrl,
    onMessage(data) {
      try {
        const event = JSON.parse(data) as {
          type: string;
          trial?: TrialRecord;
          line?: string;
          session?: unknown;
        };
        if (event.type === 'trial_complete' && event.trial) {
          setTrials((prev) => {
            const idx = prev.findIndex((t) => t.trial_number === event.trial!.trial_number);
            if (idx >= 0) {
              const next = [...prev];
              next[idx] = event.trial!;
              return next;
            }
            return [...prev, event.trial!];
          });
        } else if (event.type === 'log' && event.line) {
          setLiveLog((prev) => prev + event.line + '\n');
        } else if (event.type === 'session_complete') {
          setStreaming(false);
          void refreshSessions(selectedSession);
        }
      } catch {
        // ignore parse errors
      }
    },
    onError() {
      setStreaming(false);
    },
  });

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [liveLog]);

  async function loadAll() {
    const [cfg, strategyList, sessionList] = await Promise.all([
      api.getOptimizerConfig(),
      api.optimizerStrategies(),
      api.sessions(),
    ]);
    setConfig(cfg);
    setStrategies(strategyList);
    setSessions(sessionList);
    const firstId = sessionList[0]?.session_id ?? '';
    setSelectedSession(firstId);
    if (firstId) {
      const trialList = await api.sessionTrials(firstId).catch(() => ({ trials: [], total: 0 }));
      setTrials(trialList.trials);
    }
    setReady(true);
  }

  async function loadParams(strategy = config.last_strategy) {
    if (!strategy) return;
    try {
      const response = await api.strategyParams(strategy);
      setParams(response.params);
      // Update timeframe from strategy metadata, persist via autosave
      if (response.timeframe) {
        setConfig((prev) => ({ ...prev, default_timeframe: response.timeframe }));
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    }
  }

  async function createAndStart() {
    const strategy = config.last_strategy || strategies[0];
    if (!strategy) return;
    setMessage('');
    setLiveLog('');
    setTrials([]);
    try {
      const paramSource =
        params.length ? params : (await api.strategyParams(strategy)).params;
      const response = await api.createSession({
        strategy_name: strategy,
        strategy_class: strategy,
        pairs,
        timeframe: config.default_timeframe || '5m',
        timerange: config.default_timerange || undefined,
        dry_run_wallet: config.dry_run_wallet,
        max_open_trades: config.max_open_trades,
        total_trials: 50,
        score_mode: 'composite',
        score_metric: 'composite',
        target_min_trades: 100,
        target_profit_pct: 50,
        max_drawdown_limit: 25,
        target_romad: 2,
        param_defs: paramSource,
      });
      setSelectedSession(response.session_id);
      await api.startSession(response.session_id);
      setStreaming(true);
      setMessage(`Session ${response.session_id} started.`);
      await refreshSessions(response.session_id);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    }
  }

  async function stopSession() {
    if (!selectedSession) return;
    setStreaming(false);
    try {
      await api.stopSession(selectedSession);
      await refreshSessions(selectedSession);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    }
  }

  async function refreshSessions(sessionId = selectedSession) {
    const sessionList = await api.sessions();
    setSessions(sessionList);
    if (sessionId) {
      setSelectedSession(sessionId);
      const trialList = await api
        .sessionTrials(sessionId)
        .catch(() => ({ trials: [], total: 0 }));
      setTrials(trialList.trials);
    }
  }

  const activeSession = sessions.find((s) => s.session_id === selectedSession);

  const hasStrategy = Boolean(config.last_strategy);
  const hasParams = params.length > 0;
  const isRunning = streaming;

  const step1Active = !hasStrategy;
  const step2Active = hasStrategy && !hasParams && !isRunning;
  const step3Active = hasParams || isRunning;

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Optimizer</h1>
          <p>Configure-section fields save automatically to the backend.</p>
        </div>
        <div className="toolbar">
          <span className={`save-state state-${saveState}`}>{saveState}</span>
        </div>
      </header>

      {message ? <div className="alert">{message}</div> : null}

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
              value={config.last_strategy}
              onChange={(e) => setConfig({ ...config, last_strategy: e.target.value })}
            >
              <option value="">Select strategy</option>
              {strategies.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label>
            Timeframe
            <input
              value={config.default_timeframe}
              onChange={(e) => setConfig({ ...config, default_timeframe: e.target.value })}
            />
          </label>
          <label style={{ gridColumn: '1 / -1' }}>
            Pairs
            <textarea
              value={config.default_pairs}
              onChange={(e) => setConfig({ ...config, default_pairs: e.target.value })}
            />
          </label>
          <label>
            Preset
            <select
              value={config.last_timerange_preset}
              onChange={(e) =>
                setConfig({ ...config, last_timerange_preset: e.target.value })
              }
            >
              {['7d', '14d', '30d', '60d', '90d', '180d', '1y'].map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
          <label>
            Timerange
            <input
              value={config.default_timerange}
              onChange={(e) => setConfig({ ...config, default_timerange: e.target.value })}
              placeholder="20240101-20241231"
            />
          </label>
          <label>
            Wallet (USDT)
            <input
              type="number"
              min="0.01"
              step="0.01"
              value={config.dry_run_wallet}
              onChange={(e) =>
                setConfig({ ...config, dry_run_wallet: Number(e.target.value) })
              }
            />
          </label>
          <label>
            Max Trades
            <input
              type="number"
              min="1"
              value={config.max_open_trades}
              onChange={(e) =>
                setConfig({ ...config, max_open_trades: Number(e.target.value) })
              }
            />
          </label>
        </form>
      </section>

      {/* Step 2 — Parameter Space */}
      <section className={`workflow-step${step2Active ? ' active' : ''}`}>
        <div className="workflow-step-header">
          <span className="step-badge">2</span>
          <h2>Parameter Space</h2>
          <button className="button" type="button" onClick={() => void loadParams()}>
            <SlidersHorizontal size={16} />
            Load Params
          </button>
        </div>
        <div className="panel">
          <div className="param-list">
            {params.slice(0, 48).map((p) => (
              <div className="param-row" key={p.name}>
                <strong>{p.name}</strong>
                <span>{p.space}</span>
                <span>{p.param_type}</span>
                <span>{String(p.default ?? '')}</span>
              </div>
            ))}
            {!params.length && (
              <div className="empty-state" style={{ fontSize: 12 }}>
                Click "Load Params" to inspect strategy parameters.
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Step 3 — Run & Monitor */}
      <section className={`workflow-step${step3Active ? ' active' : ''}`}>
        <div className="workflow-step-header">
          <span className="step-badge">3</span>
          <h2>Run &amp; Monitor</h2>
          {activeSession && <StatusBadge status={activeSession.status} />}
          <button
            className="button primary"
            type="button"
            onClick={() => void createAndStart()}
            disabled={streaming}
          >
            <Play size={16} />
            Start
          </button>
          <button className="button ghost" type="button" onClick={() => void stopSession()}>
            <Square size={16} />
            Stop
          </button>
        </div>

        {streaming && <div className="loading-bar" />}

        <div className="panel">
          <div className="panel-header">
            <h2>Sessions</h2>
            <select
              value={selectedSession}
              onChange={(e) => void refreshSessions(e.target.value)}
              style={{ maxWidth: 320 }}
            >
              <option value="">Select session</option>
              {sessions.map((s) => (
                <option key={s.session_id} value={s.session_id}>
                  {s.strategy_name ?? s.session_id} — {s.status} ({s.trials_completed} trials)
                </option>
              ))}
            </select>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Session</th>
                  <th>Strategy</th>
                  <th>Status</th>
                  <th>Trials</th>
                  <th>Started</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((s) => (
                  <tr
                    key={s.session_id}
                    style={{
                      cursor: 'pointer',
                      background:
                        s.session_id === selectedSession ? 'var(--surface-2)' : undefined,
                    }}
                    onClick={() => void refreshSessions(s.session_id)}
                  >
                    <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{s.session_id}</td>
                    <td>{s.strategy_name ?? '—'}</td>
                    <td>
                      <StatusBadge status={s.status} />
                    </td>
                    <td>{s.trials_completed}</td>
                    <td>{formatDate(s.started_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <h2>Trials</h2>
            <span className="muted">{trials.length} recorded</span>
          </div>
          <div className="trial-grid">
            {trials.slice(0, 48).map((t) => (
              <div
                className="trial-tile"
                key={t.trial_number}
                style={{ borderLeft: t.is_best ? '3px solid var(--accent)' : undefined }}
              >
                <strong>#{t.trial_number}</strong>
                <span>{t.status}</span>
                <span>{formatNumber(t.score)}</span>
                <span>{t.is_best ? '★' : ''}</span>
              </div>
            ))}
            {trials.length === 0 && (
              <div className="empty-state" style={{ fontSize: 12 }}>
                No trials yet. Start a session to see results.
              </div>
            )}
          </div>
        </div>

        {(liveLog || streaming) && (
          <div className="panel">
            <div className="panel-header">
              <h2>Live Log</h2>
              <button
                className="button ghost"
                type="button"
                onClick={() => setLiveLog('')}
                style={{ fontSize: 12 }}
              >
                Clear
              </button>
            </div>
            <pre ref={logRef} className="terminal" style={{ minHeight: 200 }}>
              {liveLog || 'Waiting for output…'}
            </pre>
          </div>
        )}
      </section>
    </div>
  );
}
