/* API Client - Single source for all API calls */

const API_BASE = "/api";

export async function getRuns(filters = {}) {
  const params = new URLSearchParams(filters);
  return fetch(`${API_BASE}/runs?${params}`).then(r => r.json());
}

export async function getRun(runId) {
  return fetch(`${API_BASE}/runs/${runId}`).then(r => r.json());
}

export async function startRun(payload) {
  return fetch(`${API_BASE}/runs`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  }).then(r => r.json());
}

export async function deleteRun(runId) {
  return fetch(`${API_BASE}/runs/${runId}`, {
    method: "DELETE"
  }).then(r => r.json());
}

export async function getStrategies() {
  return fetch(`${API_BASE}/strategies`).then(r => r.json());
}

export async function getStrategy(strategyName) {
  return fetch(`${API_BASE}/strategies/${strategyName}`).then(r => r.json());
}

export async function getDiagnosis(runId) {
  return fetch(`${API_BASE}/diagnosis/${runId}`).then(r => r.json());
}

export async function compareRuns(runAId, runBId) {
  return fetch(`${API_BASE}/comparison?run_a_id=${runAId}&run_b_id=${runBId}`).then(r => r.json());
}

export async function getSettings() {
  return fetch(`${API_BASE}/settings`).then(r => r.json());
}

export async function updateSettings(settings) {
  const response = await fetch(`${API_BASE}/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  });
  if (!response.ok) throw new Error('Failed to update settings');
  return response.json();
}

export async function getRunDiff(runId, baselineId = null) {
  const params = baselineId ? `?baseline_id=${baselineId}` : '';
  const response = await fetch(`${API_BASE}/runs/${runId}/diff${params}`);
  if (!response.ok) throw new Error('Failed to get run diff');
  return response.json();
}

export async function rollbackRun(runId, baselineRunId) {
  const response = await fetch(`${API_BASE}/runs/${runId}/rollback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ baseline_run_id: baselineRunId }),
  });
  if (!response.ok) throw new Error('Failed to rollback run');
  return response.json();
}

export async function downloadData(config) {
  const response = await fetch(`${API_BASE}/download-data`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  if (!response.ok) throw new Error('Failed to download data');
  return response.json();
}

export async function getPairs() {
  return fetch(`${API_BASE}/pairs`).then(r => r.json());
}

export async function saveFavorites(favorites) {
  const response = await fetch(`${API_BASE}/favorites`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ favorites }),
  });
  if (!response.ok) throw new Error('Failed to save favorites');
  return response.json();
}

export async function saveBacktestConfig(config) {
  const response = await fetch(`${API_BASE}/backtest-config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  if (!response.ok) throw new Error('Failed to save config');
  return response.json();
}

export async function getBacktestConfig() {
  return fetch(`${API_BASE}/backtest-config`).then(r => r.json());
}

export async function getLoopStatus() {
  return fetch(`${API_BASE}/loop/status`).then(r => r.json());
}

export async function startLoop(config) {
  return fetch(`${API_BASE}/loop/start`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(config)
  }).then(r => r.json());
}

export async function stopLoop() {
  return fetch(`${API_BASE}/loop/stop`, {method: "POST"}).then(r => r.json());
}

export async function getLoopIterations() {
  return fetch(`${API_BASE}/loop/iterations`).then(r => r.json());
}
