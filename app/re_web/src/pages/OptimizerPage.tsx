import { Play, RefreshCcw, SlidersHorizontal, Square } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import { useAutosave } from '../hooks/useAutosave';
import { useSSE } from '../hooks/useSSE';
import type { OptimizerSessionSummary, ParamDef, PreferenceSection, TrialRecord } from '../types/api';
import { csvToList, formatDate, formatNumber } from '../utils/format';

export function OptimizerPage() {
  const [strategies, setStrategies] = useState<string[]>([]);
  const [prefs, setPrefs] = useState<PreferenceSection>({
    last_strategy: '',
    default_timeframe: '5m',
    default_timerange: '',
    default_pairs: 'BTC/USDT',
    dry_run_wallet: 80,
    max_open_trades: 2,
    total_trials: 50,
    score_mode: 'composite',
    target_min_trades: 100,
    target_profit_pct: 50,
    max_drawdown_limit: 25,
    target_romad: 2
  });
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

  const saveState = useAutosave(
    prefs,
    (value) => api.updateSettings({ optimizer_preferences: value }),
    { enabled: ready, delay: 500 }
  );

  const pairs = useMemo(() => csvToList(prefs.default_pairs), [prefs.default_pairs]);

  // SSE stream for selected session
  const sseUrl = streaming && selectedSession
    ? `/api/optimizer/sessions/${encodeURIComponent(selectedSession)}/stream`
    : null;

  useSSE({
    url: sseUrl,
    onMessage(data) {
      try {
        const event = JSON.parse(data) as { type: string; trial?: TrialRecord; line?: string; session?: unknown };
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
    }
  });

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [liveLog]);

  async function loadAll() {
    const [settings, strategyList, sessionList] = await Promise.all([
      api.settings(),
      api.optimizerStrategies(),
      api.sessions()
    ]);
    setPrefs((current) => ({ ...current, ...settings.optimizer_preferences }));
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

  async function loadParams(strategy = prefs.last_strategy) {
    if (!strategy) return;
    try {
      const response = await api.strategyParams(strategy);
      setParams(response.params);
      setPrefs((prev) => ({ ...prev, default_timeframe: response.timeframe || prev.default_timeframe }));
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    }
  }

  async function createAndStart() {
    const strategy = prefs.last_strategy || strategies[0];
    if (!strategy) return;
    setMessage('');
    setLiveLog('');
    setTrials([]);
    try {
      const paramSource = params.length ? params : (await api.strategyParams(strategy)).params;
      const response = await api.createSession({
        strategy_name: strategy,
        strategy_class: strategy,
        pairs,
        timeframe: prefs.default_timeframe || '5m',
        timerange: prefs.default_timerange || undefined,
        dry_run_wallet: Number(prefs.dry_run_wallet ?? 80),
        max_open_trades: Number(prefs.max_open_trades ?? 2),
        total_trials: Number(prefs.total_trials ?? 50),
        score_mode: prefs.score_mode ?? 'composite',
        score_metric: prefs.score_metric ?? 'composite',
        target_min_trades: Number(prefs.target_min_trades ?? 100),
        target_profit_pct: Number(prefs.target_profit_pct ?? 50),
        max_drawdown_limit: Number(prefs.max_drawdown_limit ?? 25),
        target_romad: Number(prefs.target_romad ?? 2),
        param_defs: paramSource
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
      const trialList = await api.sessionTrials(sessionId).catch(() => ({ trials: [], total: 0 }));
      setTrials(trialList.trials);
    }
  }

  const activeSession = sessions.find((s) => s.session_id === selectedSession);

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Optimizer</h1>
          <p>Optimizer preferences save automatically. Sessions run on the Python backend.</p>
        </div>
        <div className="toolbar">
          {activeSession && <StatusBadge status={activeSession.status} />}
          <span className={`save-state state-${saveState}`}>{saveState}</span>
          <button className="button" type="button" onClick={() => void refreshSessions()}>
            <RefreshCcw size={16} />
            Refresh
          </button>
        </div>
      </header>

      {message ? <div className="alert">{message}</div> : null}

      <section className="split-layout optimizer-layout">
        <form className="panel form-grid" onSubmit={(e) => e.preventDefault()}>
          <label>
            Strategy
            <select
              value={prefs.last_strategy ?? ''}
              onChange={(e) => setPrefs({ ...prefs, last_strategy: e.target.value })}
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
              value={prefs.default_timeframe ?? '5m'}
              onChange={(e) => setPrefs({ ...prefs, default_timeframe: e.target.value })}
            />
          </label>
          <label style={{ gridColumn: '1 / -1' }}>
            Pairs
            <textarea
              value={prefs.default_pairs ?? ''}
              onChange={(e) => setPrefs({ ...prefs, default_pairs: e.target.value })}
            />
          </label>
          <label>
            Timerange
            <input
              value={prefs.default_timerange ?? ''}
              onChange={(e) => setPrefs({ ...prefs, default_timerange: e.target.value })}
              placeholder="20240101-20241231"
            />
          </label>
          <label>
            Trials
            <input
              type="number"
              min="1"
              value={prefs.total_trials ?? 50}
              onChange={(e) => setPrefs({ ...prefs, total_trials: Number(e.target.value) })}
            />
          </label>
          <label>
            Min trades
            <input
              type="number"
              min="0"
              value={prefs.target_min_trades ?? 100}
              onChange={(e) => setPrefs({ ...prefs, target_min_trades: Number(e.target.value) })}
            />
          </label>
          <label>
            Target profit %
            <input
              type="number"
              value={prefs.target_profit_pct ?? 50}
              onChange={(e) => setPrefs({ ...prefs, target_profit_pct: Number(e.target.value) })}
            />
          </label>
          <label>
            Drawdown cap %
            <input
              type="number"
              value={prefs.max_drawdown_limit ?? 25}
              onChange={(e) => setPrefs({ ...prefs, max_drawdown_limit: Number(e.target.value) })}
            />
          </label>
          <div className="button-row" style={{ gridColumn: '1 / -1' }}>
            <button className="button" type="button" onClick={() => void loadParams()}>
              <SlidersHorizontal size={16} />
              Load Params
            </button>
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
        </form>

        <aside className="panel" style={{ display: 'grid', gap: 10 }}>
          <div className="panel-header">
            <h2>Parameter Space</h2>
            <span className="muted">{params.length} params</span>
          </div>
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
        </aside>
      </section>

      <section className="panel">
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
                  style={{ cursor: 'pointer', background: s.session_id === selectedSession ? 'var(--surface-2)' : undefined }}
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
      </section>

      {selectedSession && (
        <section className="panel">
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
            {!trials.length && (
              <div className="empty-state" style={{ fontSize: 12 }}>
                No trials yet. Start a session to see results.
              </div>
            )}
          </div>
        </section>
      )}

      {(liveLog || streaming) && (
        <section className="panel">
          <div className="panel-header">
            <h2>Live Log</h2>
            <button className="button ghost" type="button" onClick={() => setLiveLog('')} style={{ fontSize: 12 }}>
              Clear
            </button>
          </div>
          <pre ref={logRef} className="terminal" style={{ minHeight: 200 }}>
            {liveLog || 'Waiting for output…'}
          </pre>
        </section>
      )}
    </div>
  );
}
