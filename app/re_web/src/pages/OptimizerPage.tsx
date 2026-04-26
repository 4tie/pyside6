import { Play, RefreshCcw, SlidersHorizontal, Square } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import { useAutosave } from '../hooks/useAutosave';
import type { OptimizerSessionSummary, ParamDef, PreferenceSection } from '../types/api';
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
  const [trials, setTrials] = useState<unknown[]>([]);
  const [ready, setReady] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    void loadAll();
  }, []);

  const saveState = useAutosave(
    prefs,
    (value) => api.updateSettings({ optimizer_preferences: value }),
    { enabled: ready, delay: 500 }
  );

  const pairs = useMemo(() => csvToList(prefs.default_pairs), [prefs.default_pairs]);

  async function loadAll() {
    const [settings, strategyList, sessionList] = await Promise.all([
      api.settings(),
      api.optimizerStrategies(),
      api.sessions()
    ]);
    setPrefs((current) => ({ ...current, ...settings.optimizer_preferences }));
    setStrategies(strategyList);
    setSessions(sessionList);
    setSelectedSession(sessionList[0]?.session_id ?? '');
    setReady(true);
  }

  async function loadParams(strategy = prefs.last_strategy) {
    if (!strategy) return;
    const response = await api.strategyParams(strategy);
    setParams(response.params);
    setPrefs({ ...prefs, default_timeframe: response.timeframe || prefs.default_timeframe });
  }

  async function createAndStart() {
    const strategy = prefs.last_strategy || strategies[0];
    if (!strategy) return;
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
    setMessage(`Optimizer session ${response.session_id} started.`);
    await refreshSessions(response.session_id);
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

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Optimizer</h1>
          <p>Optimizer preferences save automatically while Python keeps session logic.</p>
        </div>
        <div className="toolbar">
          <span className={`save-state state-${saveState}`}>{saveState}</span>
          <button className="button" type="button" onClick={() => void refreshSessions()}>
            <RefreshCcw size={16} />
            Refresh
          </button>
        </div>
      </header>

      {message ? <div className="alert">{message}</div> : null}

      <section className="split-layout optimizer-layout">
        <form className="panel form-grid" onSubmit={(event) => event.preventDefault()}>
          <label>
            Strategy
            <select
              value={prefs.last_strategy ?? ''}
              onChange={(event) => setPrefs({ ...prefs, last_strategy: event.target.value })}
            >
              <option value="">Select strategy</option>
              {strategies.map((strategy) => (
                <option key={strategy} value={strategy}>
                  {strategy}
                </option>
              ))}
            </select>
          </label>
          <label>
            Pairs
            <textarea
              value={prefs.default_pairs ?? ''}
              onChange={(event) => setPrefs({ ...prefs, default_pairs: event.target.value })}
            />
          </label>
          <label>
            Timeframe
            <input
              value={prefs.default_timeframe ?? '5m'}
              onChange={(event) => setPrefs({ ...prefs, default_timeframe: event.target.value })}
            />
          </label>
          <label>
            Timerange
            <input
              value={prefs.default_timerange ?? ''}
              onChange={(event) => setPrefs({ ...prefs, default_timerange: event.target.value })}
            />
          </label>
          <label>
            Trials
            <input
              type="number"
              min="1"
              value={prefs.total_trials ?? 50}
              onChange={(event) => setPrefs({ ...prefs, total_trials: Number(event.target.value) })}
            />
          </label>
          <label>
            Min trades
            <input
              type="number"
              min="0"
              value={prefs.target_min_trades ?? 100}
              onChange={(event) => setPrefs({ ...prefs, target_min_trades: Number(event.target.value) })}
            />
          </label>
          <label>
            Target profit
            <input
              type="number"
              value={prefs.target_profit_pct ?? 50}
              onChange={(event) => setPrefs({ ...prefs, target_profit_pct: Number(event.target.value) })}
            />
          </label>
          <label>
            Drawdown cap
            <input
              type="number"
              value={prefs.max_drawdown_limit ?? 25}
              onChange={(event) => setPrefs({ ...prefs, max_drawdown_limit: Number(event.target.value) })}
            />
          </label>
          <div className="button-row">
            <button className="button" type="button" onClick={() => void loadParams()}>
              <SlidersHorizontal size={16} />
              Params
            </button>
            <button className="button primary" type="button" onClick={() => void createAndStart()}>
              <Play size={16} />
              Start
            </button>
            <button
              className="button ghost"
              type="button"
              onClick={() => selectedSession && void api.stopSession(selectedSession).then(() => refreshSessions())}
            >
              <Square size={16} />
              Stop
            </button>
          </div>
        </form>

        <aside className="panel">
          <div className="panel-header">
            <h2>Parameter Space</h2>
            <span className="muted">{params.length} params</span>
          </div>
          <div className="param-list">
            {params.slice(0, 48).map((param) => (
              <div className="param-row" key={param.name}>
                <strong>{param.name}</strong>
                <span>{param.space}</span>
                <span>{param.param_type}</span>
                <span>{String(param.default ?? '')}</span>
              </div>
            ))}
          </div>
        </aside>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>Sessions</h2>
          <select value={selectedSession} onChange={(event) => void refreshSessions(event.target.value)}>
            <option value="">Select session</option>
            {sessions.map((session) => (
              <option key={session.session_id} value={session.session_id}>
                {session.strategy_name ?? session.session_id}
              </option>
            ))}
          </select>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Session</th>
                <th>Status</th>
                <th>Trials</th>
                <th>Started</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((session) => (
                <tr key={session.session_id}>
                  <td>{session.session_id}</td>
                  <td>
                    <StatusBadge status={session.status} />
                  </td>
                  <td>{session.trials_completed}</td>
                  <td>{formatDate(session.started_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="trial-grid">
          {trials.slice(0, 24).map((trial) => {
            const item = trial as { trial_number?: number; score?: number; status?: string };
            return (
              <div className="trial-tile" key={item.trial_number}>
                <strong>#{item.trial_number}</strong>
                <span>{item.status}</span>
                <span>{formatNumber(item.score)}</span>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
