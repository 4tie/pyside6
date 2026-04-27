import { Save, ShieldCheck } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useAutosave } from '../hooks/useAutosave';
import type { SettingsResponse } from '../types/api';

type PathSettings = Pick<
  SettingsResponse,
  'user_data_path' | 'venv_path' | 'python_executable' | 'freqtrade_executable' | 'use_module_execution'
>;

const emptyPaths: PathSettings = {
  user_data_path: '',
  venv_path: '',
  python_executable: '',
  freqtrade_executable: '',
  use_module_execution: true,
};

export function SettingsPage() {
  const [paths, setPaths] = useState<PathSettings>(emptyPaths);
  const [ready, setReady] = useState(false);
  const [message, setMessage] = useState('');
  const [validating, setValidating] = useState(false);
  const [validation, setValidation] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    void api
      .settings()
      .then((response) => {
        setPaths({
          user_data_path: response.user_data_path,
          venv_path: response.venv_path,
          python_executable: response.python_executable,
          freqtrade_executable: response.freqtrade_executable,
          use_module_execution: response.use_module_execution,
        });
        setReady(true);
      })
      .catch((err) => setMessage(err instanceof Error ? err.message : String(err)));
  }, []);

  // Auto-save paths section with 600ms debounce
  const saveState = useAutosave(paths, api.updateSettings, { enabled: ready, delay: 600 });

  async function saveNow() {
    try {
      await api.updateSettings(paths);
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

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Settings</h1>
          <p>Paths and executables persist to settings.json automatically.</p>
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
            value={paths.user_data_path}
            onChange={(e) => setPaths({ ...paths, user_data_path: e.target.value })}
            placeholder="/path/to/user_data"
          />
        </label>
        <label>
          Virtual environment
          <input
            value={paths.venv_path}
            onChange={(e) => setPaths({ ...paths, venv_path: e.target.value })}
            placeholder="/path/to/.venv"
          />
        </label>
        <label>
          Python executable
          <input
            value={paths.python_executable}
            onChange={(e) => setPaths({ ...paths, python_executable: e.target.value })}
            placeholder="/path/to/.venv/bin/python"
          />
        </label>
        <label>
          Freqtrade executable
          <input
            value={paths.freqtrade_executable}
            onChange={(e) => setPaths({ ...paths, freqtrade_executable: e.target.value })}
            placeholder="/path/to/.venv/bin/freqtrade"
          />
        </label>
        <label className="check-row" style={{ gridColumn: '1 / -1' }}>
          <input
            type="checkbox"
            checked={paths.use_module_execution}
            onChange={(e) => setPaths({ ...paths, use_module_execution: e.target.checked })}
          />
          Use <code>python -m freqtrade</code> (recommended)
        </label>
      </section>
    </div>
  );
}
