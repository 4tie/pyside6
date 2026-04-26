import { Save } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useAutosave } from '../hooks/useAutosave';
import type { SettingsResponse } from '../types/api';

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

export function SettingsPage() {
  const [settings, setSettings] = useState<SettingsResponse>(emptySettings);
  const [ready, setReady] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    void api
      .settings()
      .then((response) => {
        setSettings(response);
        setReady(true);
      })
      .catch((err) => setMessage(err instanceof Error ? err.message : String(err)));
  }, []);

  const saveState = useAutosave(settings, api.updateSettings, { enabled: ready, delay: 600 });

  async function saveNow() {
    const response = await api.updateSettings(settings);
    setSettings(response);
    setMessage('Settings saved.');
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Settings</h1>
          <p>Backend paths and execution settings persist to settings.json.</p>
        </div>
        <div className="toolbar">
          <span className={`save-state state-${saveState}`}>{saveState}</span>
          <button className="button primary" type="button" onClick={() => void saveNow()}>
            <Save size={16} />
            Save
          </button>
        </div>
      </header>

      {message ? <div className="alert">{message}</div> : null}

      <section className="panel form-grid settings-form">
        <label>
          User data path
          <input
            value={settings.user_data_path}
            onChange={(event) => setSettings({ ...settings, user_data_path: event.target.value })}
          />
        </label>
        <label>
          Virtual environment
          <input value={settings.venv_path} onChange={(event) => setSettings({ ...settings, venv_path: event.target.value })} />
        </label>
        <label>
          Python executable
          <input
            value={settings.python_executable}
            onChange={(event) => setSettings({ ...settings, python_executable: event.target.value })}
          />
        </label>
        <label>
          Freqtrade executable
          <input
            value={settings.freqtrade_executable}
            onChange={(event) => setSettings({ ...settings, freqtrade_executable: event.target.value })}
          />
        </label>
        <label className="check-row">
          <input
            type="checkbox"
            checked={settings.use_module_execution}
            onChange={(event) => setSettings({ ...settings, use_module_execution: event.target.checked })}
          />
          Use python -m freqtrade
        </label>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>Saved Preferences</h2>
          <span className="muted">Read-only preview</span>
        </div>
        <pre className="json-block">
          {JSON.stringify(
            {
              backtest_preferences: settings.backtest_preferences,
              optimizer_preferences: settings.optimizer_preferences,
              download_preferences: settings.download_preferences
            },
            null,
            2
          )}
        </pre>
      </section>
    </div>
  );
}
