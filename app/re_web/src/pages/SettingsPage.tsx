import { Save, ShieldCheck } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useAutosave } from '../hooks/useAutosave';
import type { PreferenceSection, SettingsResponse } from '../types/api';

const emptySettings: SettingsResponse = {
  user_data_path: '',
  venv_path: '',
  python_executable: '',
  freqtrade_executable: '',
  use_module_execution: true,
  backtest_preferences: {},
  optimize_preferences: {},
  download_preferences: {},
  optimizer_preferences: {}
};

const TIMEFRAMES = ['1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d'];

function PrefField({
  label,
  value,
  onChange,
  type = 'text',
  placeholder
}: {
  label: string;
  value: string | number | undefined;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
}) {
  return (
    <label>
      {label}
      <input
        type={type}
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </label>
  );
}

function PrefsSection({
  title,
  prefs,
  onChange,
  showStrategy = true,
  showTrials = false
}: {
  title: string;
  prefs: PreferenceSection;
  onChange: (p: PreferenceSection) => void;
  showStrategy?: boolean;
  showTrials?: boolean;
}) {
  const set = (key: keyof PreferenceSection, val: unknown) =>
    onChange({ ...prefs, [key]: val });

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>{title}</h2>
      </div>
      <div className="form-grid">
        {showStrategy && (
          <PrefField
            label="Last strategy"
            value={prefs.last_strategy}
            onChange={(v) => set('last_strategy', v)}
          />
        )}
        <label>
          Default timeframe
          <select
            value={prefs.default_timeframe ?? '5m'}
            onChange={(e) => set('default_timeframe', e.target.value)}
          >
            {TIMEFRAMES.map((tf) => (
              <option key={tf} value={tf}>
                {tf}
              </option>
            ))}
          </select>
        </label>
        <PrefField
          label="Default timerange"
          value={prefs.default_timerange}
          onChange={(v) => set('default_timerange', v)}
          placeholder="20240101-20241231"
        />
        <PrefField
          label="Default pairs"
          value={prefs.default_pairs}
          onChange={(v) => set('default_pairs', v)}
          placeholder="BTC/USDT, ETH/USDT"
        />
        <PrefField
          label="Dry-run wallet"
          value={prefs.dry_run_wallet}
          onChange={(v) => set('dry_run_wallet', Number(v))}
          type="number"
        />
        <PrefField
          label="Max open trades"
          value={prefs.max_open_trades}
          onChange={(v) => set('max_open_trades', Number(v))}
          type="number"
        />
        {showTrials && (
          <>
            <PrefField
              label="Total trials"
              value={prefs.total_trials}
              onChange={(v) => set('total_trials', Number(v))}
              type="number"
            />
            <PrefField
              label="Target min trades"
              value={prefs.target_min_trades}
              onChange={(v) => set('target_min_trades', Number(v))}
              type="number"
            />
            <PrefField
              label="Target profit %"
              value={prefs.target_profit_pct}
              onChange={(v) => set('target_profit_pct', Number(v))}
              type="number"
            />
            <PrefField
              label="Max drawdown cap"
              value={prefs.max_drawdown_limit}
              onChange={(v) => set('max_drawdown_limit', Number(v))}
              type="number"
            />
          </>
        )}
      </div>
    </section>
  );
}

export function SettingsPage() {
  const [settings, setSettings] = useState<SettingsResponse>(emptySettings);
  const [ready, setReady] = useState(false);
  const [message, setMessage] = useState('');
  const [validating, setValidating] = useState(false);
  const [validation, setValidation] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    void api
      .settings()
      .then((response) => {
        setSettings(response);
        setReady(true);
      })
      .catch((err) => setMessage(err instanceof Error ? err.message : String(err)));
  }, []);

  // Auto-save paths section with 600ms debounce
  const saveState = useAutosave(settings, api.updateSettings, { enabled: ready, delay: 600 });

  async function saveNow() {
    try {
      const response = await api.updateSettings(settings);
      setSettings(response);
      setMessage('Settings saved.');
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    }
  }

  async function validate() {
    setValidating(true);
    setValidation(null);
    try {
      const response = await fetch('/api/settings/validate', { method: 'POST' });
      const data = (await response.json()) as Record<string, unknown>;
      setValidation(data);
    } catch (err) {
      setValidation({ error: err instanceof Error ? err.message : String(err) });
    } finally {
      setValidating(false);
    }
  }

  const setPrefs = (section: keyof Pick<SettingsResponse, 'backtest_preferences' | 'optimize_preferences' | 'download_preferences' | 'optimizer_preferences'>) =>
    (prefs: PreferenceSection) => setSettings({ ...settings, [section]: prefs });

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Settings</h1>
          <p>Paths and preferences persist to settings.json automatically.</p>
        </div>
        <div className="toolbar">
          <span className={`save-state state-${saveState}`}>{saveState}</span>
          <button className="button" type="button" onClick={() => void validate()} disabled={validating}>
            <ShieldCheck size={16} />
            {validating ? 'Checking…' : 'Validate'}
          </button>
          <button className="button primary" type="button" onClick={() => void saveNow()}>
            <Save size={16} />
            Save
          </button>
        </div>
      </header>

      {message ? <div className="alert">{message}</div> : null}

      {validation ? (
        <div className={`alert ${(validation.valid as boolean) ? '' : 'error'}`}>
          <strong>{(validation.valid as boolean) ? '✓ Valid' : '✗ Invalid'}</strong>
          {' — '}
          {String(validation.message ?? '')}
          {validation.details ? (
            <pre style={{ marginTop: 8, fontSize: 12 }}>{JSON.stringify(validation.details, null, 2)}</pre>
          ) : null}
        </div>
      ) : null}

      <section className="panel form-grid settings-form">
        <div className="panel-header" style={{ gridColumn: '1 / -1' }}>
          <h2>Paths &amp; Executables</h2>
        </div>
        <label>
          User data path
          <input
            value={settings.user_data_path}
            onChange={(e) => setSettings({ ...settings, user_data_path: e.target.value })}
            placeholder="/path/to/user_data"
          />
        </label>
        <label>
          Virtual environment
          <input
            value={settings.venv_path}
            onChange={(e) => setSettings({ ...settings, venv_path: e.target.value })}
            placeholder="/path/to/.venv"
          />
        </label>
        <label>
          Python executable
          <input
            value={settings.python_executable}
            onChange={(e) => setSettings({ ...settings, python_executable: e.target.value })}
            placeholder="/path/to/.venv/bin/python"
          />
        </label>
        <label>
          Freqtrade executable
          <input
            value={settings.freqtrade_executable}
            onChange={(e) => setSettings({ ...settings, freqtrade_executable: e.target.value })}
            placeholder="/path/to/.venv/bin/freqtrade"
          />
        </label>
        <label className="check-row" style={{ gridColumn: '1 / -1' }}>
          <input
            type="checkbox"
            checked={settings.use_module_execution}
            onChange={(e) => setSettings({ ...settings, use_module_execution: e.target.checked })}
          />
          Use <code>python -m freqtrade</code> (recommended)
        </label>
      </section>

      <PrefsSection
        title="Backtest Preferences"
        prefs={settings.backtest_preferences}
        onChange={setPrefs('backtest_preferences')}
      />

      <PrefsSection
        title="Optimizer Preferences"
        prefs={settings.optimizer_preferences}
        onChange={setPrefs('optimizer_preferences')}
        showTrials
      />

      <PrefsSection
        title="Download Preferences"
        prefs={settings.download_preferences}
        onChange={setPrefs('download_preferences')}
        showStrategy={false}
      />
    </div>
  );
}
