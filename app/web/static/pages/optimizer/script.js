/**
 * Strategy Optimizer Page Script
 * 
 * Handles session management, trial execution, composite scoring display,
 * and real-time updates via Server-Sent Events.
 */

import { api } from '/static/shared/js/api.js';
import { state } from '/static/shared/js/state.js';

// Global state
let currentSessionId = null;
let eventSource = null;
let sessionStartTime = null;
let elapsedTimer = null;
let strategies = [];
let paramDefs = [];
let trials = [];
let selectedTrial = null;
let compareTrialA = null;
let isRunning = false;

// Score metric options matching PySide6
const SCORE_OPTIONS = [
  { key: 'composite', label: 'Composite Score' },
  { key: 'total_profit_pct', label: 'Total Profit %' },
  { key: 'total_profit_abs', label: 'Total Profit (abs)' },
  { key: 'sharpe_ratio', label: 'Sharpe Ratio' },
  { key: 'profit_factor', label: 'Profit Factor' },
  { key: 'win_rate', label: 'Win Rate' },
];

// DOM Elements
const els = {
  strategySelect: document.getElementById('strategy-select'),
  timeframe: document.getElementById('timeframe'),
  timerange: document.getElementById('timerange'),
  pairs: document.getElementById('pairs'),
  wallet: document.getElementById('wallet'),
  maxTrades: document.getElementById('max-trades'),
  trials: document.getElementById('trials'),
  scoreMetric: document.getElementById('score-metric'),
  targetTrades: document.getElementById('target-trades'),
  targetProfit: document.getElementById('target-profit'),
  maxDrawdown: document.getElementById('max-drawdown'),
  targetRomad: document.getElementById('target-romad'),
  paramTbody: document.getElementById('param-tbody'),
  historyList: document.getElementById('history-list'),
  progressBar: document.getElementById('progress-bar'),
  progressText: document.getElementById('progress-text'),
  elapsed: document.getElementById('elapsed'),
  eta: document.getElementById('eta'),
  startBtn: document.getElementById('start-btn'),
  stopBtn: document.getElementById('stop-btn'),
  logView: document.getElementById('log-view'),
  trialTbody: document.getElementById('trial-tbody'),
  bestMetrics: document.getElementById('best-metrics'),
  selectedMetrics: document.getElementById('selected-metrics'),
  scoreBreakdown: document.getElementById('score-breakdown'),
  diffStatus: document.getElementById('diff-status'),
  paramDiff: document.getElementById('param-diff'),
  strategyDiff: document.getElementById('strategy-diff'),
  compareModal: document.getElementById('compare-modal'),
  compareTable: document.getElementById('compare-table'),
};

// Initialize
async function init() {
  await loadStrategies();
  await loadSessionHistory();
  setupEventListeners();
  setupTheme();
}

// Load strategies
async function loadStrategies() {
  try {
    strategies = await api.get('/optimizer/strategies');
    els.strategySelect.innerHTML = '<option value="">Select a strategy...</option>' +
      strategies.map(s => `<option value="${s}">${s}</option>`).join('');
  } catch (err) {
    console.error('Failed to load strategies:', err);
    showError('Failed to load strategies');
  }
}

// Load strategy parameters
async function loadStrategyParams(strategyName) {
  if (!strategyName) {
    paramDefs = [];
    renderParamTable();
    return;
  }
  
  try {
    const data = await api.get(`/optimizer/strategy-params?strategy=${encodeURIComponent(strategyName)}`);
    paramDefs = data.params || [];
    els.timeframe.value = data.timeframe || '5m';
    renderParamTable();
  } catch (err) {
    console.error('Failed to load strategy params:', err);
    showError('Failed to load strategy parameters');
  }
}

// Render parameter table
function renderParamTable() {
  els.paramTbody.innerHTML = paramDefs.map((p, idx) => `
    <tr data-idx="${idx}">
      <td><input type="checkbox" ${p.enabled !== false ? 'checked' : ''} data-field="enabled"></td>
      <td>${p.name}</td>
      <td>${p.param_type}</td>
      <td>${formatValue(p.default)}</td>
      <td><input type="${p.param_type === 'int' ? 'number' : 'text'}" 
                 value="${p.low ?? ''}" 
                 data-field="low"
                 ${p.param_type === 'categorical' || p.param_type === 'boolean' ? 'disabled' : ''}></td>
      <td><input type="${p.param_type === 'int' ? 'number' : 'text'}" 
                 value="${p.high ?? ''}" 
                 data-field="high"
                 ${p.param_type === 'categorical' || p.param_type === 'boolean' ? 'disabled' : ''}></td>
    </tr>
  `).join('');
  
  // Add event listeners for param edits
  els.paramTbody.querySelectorAll('input').forEach(input => {
    input.addEventListener('change', handleParamChange);
  });
}

// Handle parameter change
function handleParamChange(e) {
  const row = e.target.closest('tr');
  const idx = parseInt(row.dataset.idx);
  const field = e.target.dataset.field;
  let value = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
  
  if (field !== 'enabled') {
    value = value === '' ? null : parseFloat(value);
    // Validate range
    const low = field === 'high' ? parseFloat(row.querySelector('[data-field="low"]').value) : null;
    const high = field === 'low' ? parseFloat(row.querySelector('[data-field="high"]').value) : null;
    
    if (low !== null && high !== null && low >= high) {
      e.target.classList.add('invalid');
      return;
    } else {
      e.target.classList.remove('invalid');
    }
  }
  
  paramDefs[idx] = { ...paramDefs[idx], [field]: value };
}

// Sync from backtest preferences
async function syncFromBacktest() {
  try {
    const settings = await api.get('/settings');
    const prefs = settings.backtest_preferences || {};
    const optPrefs = settings.optimizer_preferences || {};
    
    els.timeframe.value = prefs.default_timeframe || '5m';
    els.timerange.value = prefs.default_timerange || '';
    els.pairs.value = prefs.default_pairs || '';
    els.wallet.value = prefs.dry_run_wallet || 80;
    els.maxTrades.value = prefs.max_open_trades || 2;
    
    els.trials.value = optPrefs.total_trials || 50;
    els.scoreMetric.value = optPrefs.score_metric || 'composite';
    els.targetTrades.value = optPrefs.target_min_trades || 100;
    els.targetProfit.value = optPrefs.target_profit_pct || 50.0;
    els.maxDrawdown.value = optPrefs.max_drawdown_limit || 25.0;
    els.targetRomad.value = optPrefs.target_romad || 2.0;
    
    if (prefs.last_strategy) {
      els.strategySelect.value = prefs.last_strategy;
      await loadStrategyParams(prefs.last_strategy);
    }
  } catch (err) {
    console.error('Failed to sync from backtest:', err);
    showError('Failed to sync from backtest preferences');
  }
}

// Load session history
async function loadSessionHistory() {
  try {
    const sessions = await api.get('/optimizer/sessions');
    renderHistoryList(sessions);
  } catch (err) {
    console.error('Failed to load session history:', err);
    els.historyList.innerHTML = '<div class="loading">Failed to load history</div>';
  }
}

// Render history list
function renderHistoryList(sessions) {
  if (!sessions || sessions.length === 0) {
    els.historyList.innerHTML = '<div class="empty-state">No sessions yet</div>';
    return;
  }
  
  els.historyList.innerHTML = sessions.map(s => `
    <div class="history-item" data-session-id="${s.session_id}">
      <div>
        <div class="strategy-name">${s.strategy_name}</div>
        <div class="session-info">${s.trials_completed} trials • ${s.status}</div>
      </div>
    </div>
  `).join('');
  
  els.historyList.querySelectorAll('.history-item').forEach(item => {
    item.addEventListener('click', () => loadSession(item.dataset.sessionId));
  });
}

// Load a session
async function loadSession(sessionId) {
  try {
    const session = await api.get(`/optimizer/sessions/${sessionId}`);
    currentSessionId = sessionId;
    
    // Update UI with session config
    const config = session.config;
    els.strategySelect.value = config.strategy_name;
    els.timeframe.value = config.timeframe;
    els.timerange.value = config.timerange || '';
    els.pairs.value = config.pairs?.join(', ') || '';
    els.wallet.value = config.dry_run_wallet;
    els.maxTrades.value = config.max_open_trades;
    els.trials.value = config.total_trials;
    els.scoreMetric.value = config.score_metric;
    els.targetTrades.value = config.target_min_trades;
    els.targetProfit.value = config.target_profit_pct;
    els.maxDrawdown.value = config.max_drawdown_limit;
    els.targetRomad.value = config.target_romad;
    
    // Load params
    await loadStrategyParams(config.strategy_name);
    
    // Load trials
    await loadTrials(sessionId);
    
    // Highlight in history
    els.historyList.querySelectorAll('.history-item').forEach(item => {
      item.classList.toggle('selected', item.dataset.sessionId === sessionId);
    });
    
    // If running, connect to stream
    if (session.status === 'running') {
      isRunning = true;
      connectEventStream(sessionId);
      updateUIState();
    }
  } catch (err) {
    console.error('Failed to load session:', err);
    showError('Failed to load session');
  }
}

// Load trials for a session
async function loadTrials(sessionId) {
  try {
    const data = await api.get(`/optimizer/sessions/${sessionId}/trials`);
    trials = data.trials || [];
    renderTrialTable();
    updateBestTrial();
  } catch (err) {
    console.error('Failed to load trials:', err);
  }
}

// Render trial table
function renderTrialTable() {
  if (trials.length === 0) {
    els.trialTbody.innerHTML = '<tr><td colspan="6" class="empty-state">No trials yet</td></tr>';
    return;
  }
  
  // Calculate star ratings
  const scores = trials
    .filter(t => t.status === 'success' && t.score != null)
    .map(t => t.score);
  const minScore = Math.min(...scores);
  const maxScore = Math.max(...scores);
  
  els.trialTbody.innerHTML = trials.map(t => {
    const isBest = t.is_best;
    const isSelected = selectedTrial?.trial_number === t.trial_number;
    const statusClass = t.status === 'failed' ? 'failed' : 
                       t.status === 'running' ? 'running' : '';
    const rowClass = `${isBest ? 'best' : ''} ${isSelected ? 'selected' : ''} ${statusClass}`;
    
    let starRating = 0;
    if (t.status === 'success' && t.score != null && scores.length > 0) {
      if (isBest) {
        starRating = 7;
      } else if (maxScore !== minScore) {
        starRating = 1 + Math.round(((t.score - minScore) / (maxScore - minScore)) * 6);
        starRating = Math.max(1, Math.min(7, starRating));
      }
    }
    
    const stars = starRating > 0 ? '★'.repeat(starRating) : '';
    
    return `
      <tr class="${rowClass}" data-trial-num="${t.trial_number}">
        <td>${t.trial_number}</td>
        <td>${formatParams(t.candidate_params)}</td>
        <td>${t.metrics ? t.metrics.total_profit_pct?.toFixed(2) + '%' : '—'}</td>
        <td>${t.metrics ? t.metrics.max_drawdown_pct?.toFixed(1) + '%' : '—'}</td>
        <td>${t.score?.toFixed(4) || '—'}</td>
        <td class="star-${starRating}">${stars}</td>
      </tr>
    `;
  }).join('');
  
  els.trialTbody.querySelectorAll('tr').forEach(row => {
    row.addEventListener('click', () => selectTrial(parseInt(row.dataset.trialNum)));
  });
}

// Format parameters for display
function formatParams(params) {
  if (!params) return '—';
  const entries = Object.entries(params).slice(0, 3);
  const formatted = entries.map(([k, v]) => {
    const val = typeof v === 'number' ? v.toFixed(4) : v;
    return `${k}=${val}`;
  });
  const suffix = Object.keys(params).length > 3 ? ', …' : '';
  return formatted.join(', ') + suffix;
}

// Format value
function formatValue(v) {
  if (v === null || v === undefined) return '';
  if (typeof v === 'number') return Number.isInteger(v) ? v.toString() : v.toFixed(4);
  return String(v);
}

// Select a trial
async function selectTrial(trialNumber) {
  selectedTrial = trials.find(t => t.trial_number === trialNumber);
  if (!selectedTrial) return;
  
  renderTrialTable();
  updateSelectedMetrics();
  updateScoreBreakdown();
  
  // Load diff if successful
  if (selectedTrial.status === 'success') {
    await loadTrialDiff();
  } else {
    els.diffStatus.textContent = 'Only successful trials can be previewed or applied.';
    els.paramDiff.innerHTML = '';
    els.strategyDiff.textContent = '';
  }
}

// Update selected metrics display
function updateSelectedMetrics() {
  if (!selectedTrial || !selectedTrial.metrics) {
    els.selectedMetrics.innerHTML = createMetricRows({});
    return;
  }
  
  const m = selectedTrial.metrics;
  els.selectedMetrics.innerHTML = createMetricRows({
    'Profit %': m.total_profit_pct != null ? m.total_profit_pct.toFixed(2) + '%' : '—',
    'Profit abs': m.total_profit_abs != null ? m.total_profit_abs.toFixed(2) : '—',
    'Win rate': m.win_rate != null ? (m.win_rate <= 1 ? (m.win_rate * 100).toFixed(2) : m.win_rate.toFixed(2)) + '%' : '—',
    'Max DD %': m.max_drawdown_pct != null ? m.max_drawdown_pct.toFixed(2) + '%' : '—',
    'Trades': m.total_trades ?? '—',
    'Profit factor': m.profit_factor != null ? m.profit_factor.toFixed(2) : '—',
    'Sharpe': m.sharpe_ratio != null ? m.sharpe_ratio.toFixed(2) : '—',
    'Score': selectedTrial.score != null ? selectedTrial.score.toFixed(4) : '—',
  });
}

// Update score breakdown
function updateScoreBreakdown() {
  if (!selectedTrial || !selectedTrial.score_breakdown) {
    els.scoreBreakdown.innerHTML = `
      <div class="breakdown-row"><span>Trade count</span><span>—</span></div>
      <div class="breakdown-row"><span>Profit</span><span>—</span></div>
      <div class="breakdown-row"><span>Drawdown</span><span>—</span></div>
      <div class="breakdown-row"><span>RoMAD</span><span>—</span></div>
      <div class="breakdown-row"><span>Profit factor</span><span>—</span></div>
      <div class="breakdown-row"><span>Win rate</span><span>—</span></div>
      <div class="breakdown-row"><span>Sharpe</span><span>—</span></div>
      <div class="breakdown-row"><span>Base score</span><span>—</span></div>
      <div class="breakdown-row"><span>Final score</span><span>—</span></div>
    `;
    return;
  }
  
  const b = selectedTrial.score_breakdown;
  els.scoreBreakdown.innerHTML = `
    <div class="breakdown-row"><span>Trade count</span><span>${b.trade_count_score?.toFixed(4) ?? '—'}</span></div>
    <div class="breakdown-row"><span>Profit</span><span>${b.profit_score?.toFixed(4) ?? '—'}</span></div>
    <div class="breakdown-row"><span>Drawdown</span><span>${b.drawdown_score?.toFixed(4) ?? '—'}</span></div>
    <div class="breakdown-row"><span>RoMAD</span><span>${b.romad_score?.toFixed(4) ?? '—'}</span></div>
    <div class="breakdown-row"><span>Profit factor</span><span>${b.profit_factor_score?.toFixed(4) ?? '—'}</span></div>
    <div class="breakdown-row"><span>Win rate</span><span>${b.win_rate_score?.toFixed(4) ?? '—'}</span></div>
    <div class="breakdown-row"><span>Sharpe</span><span>${b.sharpe_score?.toFixed(4) ?? '—'}</span></div>
    <div class="breakdown-row"><span>Base score</span><span>${b.base_score?.toFixed(4) ?? '—'}</span></div>
    <div class="breakdown-row"><span>Final score</span><span>${b.final_score?.toFixed(4) ?? '—'}</span></div>
  `;
}

// Create metric rows HTML
function createMetricRows(metrics) {
  return Object.entries(metrics).map(([label, value]) => `
    <div class="metric-row">
      <span>${label}</span>
      <span class="metric-value">${value}</span>
    </div>
  `).join('');
}

// Update best trial display
function updateBestTrial() {
  const best = trials.find(t => t.is_best);
  if (!best || !best.metrics) {
    els.bestMetrics.innerHTML = createMetricRows({});
    return;
  }
  
  const m = best.metrics;
  els.bestMetrics.innerHTML = createMetricRows({
    'Profit %': m.total_profit_pct != null ? m.total_profit_pct.toFixed(2) + '%' : '—',
    'Profit abs': m.total_profit_abs != null ? m.total_profit_abs.toFixed(2) : '—',
    'Win rate': m.win_rate != null ? (m.win_rate <= 1 ? (m.win_rate * 100).toFixed(2) : m.win_rate.toFixed(2)) + '%' : '—',
    'Max DD %': m.max_drawdown_pct != null ? m.max_drawdown_pct.toFixed(2) + '%' : '—',
    'Trades': m.total_trades ?? '—',
    'Profit factor': m.profit_factor != null ? m.profit_factor.toFixed(2) : '—',
    'Sharpe': m.sharpe_ratio != null ? m.sharpe_ratio.toFixed(2) : '—',
    'Score': best.score != null ? best.score.toFixed(4) : '—',
  });
}

// Load trial diff
async function loadTrialDiff() {
  if (!currentSessionId || !selectedTrial) return;
  
  try {
    const diff = await api.get(`/optimizer/sessions/${currentSessionId}/trials/${selectedTrial.trial_number}/diff`);
    
    els.diffStatus.textContent = diff.success ? 'Changes preview:' : diff.error_message || 'No changes available';
    
    if (diff.param_changes && diff.param_changes.length > 0) {
      els.paramDiff.innerHTML = diff.param_changes.map(c => `
        <div class="param-diff-row">
          <span class="key">${c.key}</span>
          <span>
            <span class="current">${c.current_value}</span>
            →
            <span class="trial">${c.trial_value}</span>
          </span>
        </div>
      `).join('');
    } else {
      els.paramDiff.innerHTML = '<div class="empty-state">No parameter changes</div>';
    }
    
    els.strategyDiff.textContent = diff.strategy_diff || 'No strategy changes';
  } catch (err) {
    console.error('Failed to load trial diff:', err);
    els.diffStatus.textContent = 'Failed to load diff';
  }
}

// Start optimizer
async function startOptimizer() {
  if (!els.strategySelect.value) {
    showError('Please select a strategy');
    return;
  }
  
  try {
    // Create session
    const config = {
      strategy_name: els.strategySelect.value,
      strategy_class: els.strategySelect.value,
      pairs: els.pairs.value.split(',').map(p => p.trim()).filter(Boolean),
      timeframe: els.timeframe.value,
      timerange: els.timerange.value || null,
      dry_run_wallet: parseFloat(els.wallet.value),
      max_open_trades: parseInt(els.maxTrades.value),
      total_trials: parseInt(els.trials.value),
      score_metric: els.scoreMetric.value,
      score_mode: els.scoreMetric.value === 'composite' ? 'composite' : 'single_metric',
      target_min_trades: parseInt(els.targetTrades.value),
      target_profit_pct: parseFloat(els.targetProfit.value),
      max_drawdown_limit: parseFloat(els.maxDrawdown.value),
      target_romad: parseFloat(els.targetRomad.value),
      param_defs: paramDefs,
    };
    
    const session = await api.post('/optimizer/sessions', config);
    currentSessionId = session.session_id;
    
    // Clear previous state
    trials = [];
    selectedTrial = null;
    renderTrialTable();
    els.logView.innerHTML = '';
    
    // Start session
    await api.post(`/optimizer/sessions/${currentSessionId}/start`);
    
    isRunning = true;
    sessionStartTime = Date.now();
    connectEventStream(currentSessionId);
    startElapsedTimer();
    updateUIState();
    
    // Save preferences
    await saveOptimizerPreferences(config);
    
    // Refresh history
    await loadSessionHistory();
    
  } catch (err) {
    console.error('Failed to start optimizer:', err);
    showError(err.message || 'Failed to start optimizer');
  }
}

// Stop optimizer
async function stopOptimizer() {
  if (!currentSessionId) return;
  
  try {
    await api.post(`/optimizer/sessions/${currentSessionId}/stop`);
    isRunning = false;
    stopElapsedTimer();
    updateUIState();
    
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
  } catch (err) {
    console.error('Failed to stop optimizer:', err);
    showError('Failed to stop optimizer');
  }
}

// Connect to SSE stream
function connectEventStream(sessionId) {
  if (eventSource) {
    eventSource.close();
  }
  
  eventSource = new EventSource(`/api/optimizer/sessions/${sessionId}/stream`);
  
  eventSource.onmessage = (e) => {
    const event = JSON.parse(e.data);
    handleStreamEvent(event);
  };
  
  eventSource.onerror = (err) => {
    console.error('EventSource error:', err);
    if (isRunning) {
      // Try to reconnect after a delay
      setTimeout(() => connectEventStream(sessionId), 2000);
    }
  };
}

// Handle stream events
function handleStreamEvent(event) {
  switch (event.type) {
    case 'trial_start':
      appendLog(`\n=== Trial #${event.trial_number}: ${JSON.stringify(event.params)} ===`);
      break;
      
    case 'trial_complete':
      const trial = event.trial;
      trials.push(trial);
      renderTrialTable();
      updateBestTrial();
      updateProgress();
      
      if (trial.status === 'success' && trial.metrics) {
        appendLog(`Trial #${trial.trial_number} done: profit=${trial.metrics.total_profit_pct?.toFixed(2)}% dd=${trial.metrics.max_drawdown_pct?.toFixed(2)}% trades=${trial.metrics.total_trades} score=${trial.score?.toFixed(4)}`);
      } else {
        appendLog(`Trial #${trial.trial_number} failed.`);
      }
      break;
      
    case 'log':
      appendLog(event.line);
      break;
      
    case 'session_complete':
      isRunning = false;
      stopElapsedTimer();
      updateUIState();
      appendLog(`Session ${event.session.status}: ${event.session.trials_completed} trial(s).`);
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
      break;
  }
}

// Append to log
function appendLog(line) {
  const div = document.createElement('div');
  div.textContent = line;
  els.logView.appendChild(div);
  els.logView.scrollTop = els.logView.scrollHeight;
  
  // Limit log size
  while (els.logView.children.length > 5000) {
    els.logView.removeChild(els.logView.firstChild);
  }
}

// Update progress
function updateProgress() {
  const completed = trials.length;
  const total = parseInt(els.trials.value);
  const pct = total > 0 ? (completed / total) * 100 : 0;
  
  els.progressBar.style.width = `${pct}%`;
  els.progressText.textContent = `${completed}/${total} trials`;
}

// Start elapsed timer
function startElapsedTimer() {
  stopElapsedTimer();
  elapsedTimer = setInterval(() => {
    if (!sessionStartTime) return;
    
    const elapsed = Math.floor((Date.now() - sessionStartTime) / 1000);
    const mins = Math.floor(elapsed / 60).toString().padStart(2, '0');
    const secs = (elapsed % 60).toString().padStart(2, '0');
    els.elapsed.textContent = `Elapsed: ${mins}:${secs}`;
    
    // Calculate ETA
    const completed = trials.length;
    const total = parseInt(els.trials.value);
    if (completed > 0 && completed < total) {
      const avgTime = elapsed / completed;
      const remaining = (total - completed) * avgTime;
      const etaMins = Math.floor(remaining / 60).toString().padStart(2, '0');
      const etaSecs = (remaining % 60).toString().padStart(2, '0');
      els.eta.textContent = `ETA: ${etaMins}:${etaSecs}`;
    }
  }, 1000);
}

// Stop elapsed timer
function stopElapsedTimer() {
  if (elapsedTimer) {
    clearInterval(elapsedTimer);
    elapsedTimer = null;
  }
}

// Update UI state
function updateUIState() {
  els.startBtn.disabled = isRunning;
  els.stopBtn.disabled = !isRunning;
}

// Set selected as best
async function setSelectedAsBest() {
  if (!currentSessionId || !selectedTrial) {
    showError('No trial selected');
    return;
  }
  
  if (selectedTrial.status !== 'success') {
    showError('Only successful trials can be set as best');
    return;
  }
  
  try {
    await api.post(`/optimizer/sessions/${currentSessionId}/best`, {
      trial_number: selectedTrial.trial_number,
    });
    
    // Update local state
    trials.forEach(t => t.is_best = false);
    selectedTrial.is_best = true;
    renderTrialTable();
    updateBestTrial();
    
  } catch (err) {
    console.error('Failed to set best:', err);
    showError('Failed to set as best');
  }
}

// Export best
async function exportBest() {
  if (!currentSessionId) {
    showError('No active session');
    return;
  }
  
  try {
    const result = await api.post(`/optimizer/sessions/${currentSessionId}/export`);
    showSuccess(`Exported to ${result.live_json_path}`);
  } catch (err) {
    console.error('Failed to export:', err);
    showError(err.message || 'Failed to export');
  }
}

// Roll back the most recent optimizer export backup.
async function rollbackLatestExport() {
  if (!currentSessionId) {
    showError('No active session');
    return;
  }

  if (!confirm('Rollback the latest exported strategy params backup?')) return;

  try {
    const result = await api.post(`/optimizer/sessions/${currentSessionId}/rollback`);
    showSuccess(`Restored from ${result.restored_from}`);
  } catch (err) {
    console.error('Failed to rollback:', err);
    showError(err.message || 'Failed to rollback');
  }
}

// Apply trial
async function applyTrial(asNew = false) {
  if (!currentSessionId || !selectedTrial) {
    showError('No trial selected');
    return;
  }
  
  if (selectedTrial.status !== 'success') {
    showError('Only successful trials can be applied');
    return;
  }
  
  let newName = null;
  if (asNew) {
    newName = prompt('Enter new strategy name:');
    if (!newName) return;
  }
  
  try {
    const result = await api.post(
      `/optimizer/sessions/${currentSessionId}/trials/${selectedTrial.trial_number}/apply`,
      { new_strategy_name: newName }
    );
    
    showSuccess(`Applied to ${result.strategy_py_path}`);
  } catch (err) {
    console.error('Failed to apply trial:', err);
    showError(err.message || 'Failed to apply trial');
  }
}

// Open selected log
async function openSelectedLog() {
  if (!currentSessionId || !selectedTrial) {
    showError('No trial selected');
    return;
  }
  
  const url = `/api/optimizer/sessions/${currentSessionId}/trials/${selectedTrial.trial_number}/log`;
  window.open(url, '_blank');
}

// Open selected result
async function openSelectedResult() {
  if (!currentSessionId || !selectedTrial) {
    showError('No trial selected');
    return;
  }
  
  const url = `/api/optimizer/sessions/${currentSessionId}/trials/${selectedTrial.trial_number}/result`;
  window.open(url, '_blank');
}

// Compare trials
function showCompareModal() {
  if (!selectedTrial) {
    showError('No trial selected');
    return;
  }

  if (!compareTrialA || !selectedTrial) {
    // Set first trial for comparison
    compareTrialA = selectedTrial;
    showInfo('Select another trial to compare');
    return;
  }
  
  if (compareTrialA.trial_number === selectedTrial.trial_number) {
    showError('Cannot compare trial with itself');
    return;
  }
  
  const a = compareTrialA;
  const b = selectedTrial;
  const am = a.metrics || {};
  const bm = b.metrics || {};
  
  const rows = [
    { label: 'Profit %', a: am.total_profit_pct, b: bm.total_profit_pct, higherBetter: true },
    { label: 'Profit abs', a: am.total_profit_abs, b: bm.total_profit_abs, higherBetter: true },
    { label: 'Win Rate', a: am.win_rate, b: bm.win_rate, higherBetter: true },
    { label: 'Max DD %', a: am.max_drawdown_pct, b: bm.max_drawdown_pct, higherBetter: false },
    { label: 'Trades', a: am.total_trades, b: bm.total_trades, higherBetter: null },
    { label: 'Profit Factor', a: am.profit_factor, b: bm.profit_factor, higherBetter: true },
    { label: 'Sharpe', a: am.sharpe_ratio, b: bm.sharpe_ratio, higherBetter: true },
    { label: 'Final Balance', a: am.final_balance, b: bm.final_balance, higherBetter: true },
  ];
  rows.push({ label: 'Score', a: a.score, b: b.score, higherBetter: true });
  
  els.compareTable.querySelector('tbody').innerHTML = rows.map(r => {
    const va = formatMetric(r.a);
    const vb = formatMetric(r.b);
    let delta = '—';
    let deltaClass = '';
    
    if (r.a != null && r.b != null) {
      const diff = r.b - r.a;
      delta = (diff >= 0 ? '+' : '') + diff.toFixed(4);
      
      if (r.higherBetter === true) {
        deltaClass = diff > 0 ? 'positive' : diff < 0 ? 'negative' : '';
      } else if (r.higherBetter === false) {
        deltaClass = diff > 0 ? 'negative' : diff < 0 ? 'positive' : '';
      }
    }
    
    return `
      <tr>
        <td>${r.label}</td>
        <td>${va}</td>
        <td>${vb}</td>
        <td class="${deltaClass}">${delta}</td>
      </tr>
    `;
  }).join('');
  
  els.compareModal.classList.add('active');
  compareTrialA = null;
}

// Format metric for display
function formatMetric(v) {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'number') return Number.isInteger(v) ? v.toString() : v.toFixed(4);
  return String(v);
}

// Delete selected session
async function deleteSelectedSession() {
  const selected = els.historyList.querySelector('.history-item.selected');
  if (!selected) {
    showError('No session selected');
    return;
  }
  
  if (!confirm('Delete this optimizer session?')) return;
  
  const sessionId = selected.dataset.sessionId;
  
  try {
    await api.delete(`/optimizer/sessions/${sessionId}`);
    await loadSessionHistory();
    
    if (currentSessionId === sessionId) {
      currentSessionId = null;
      trials = [];
      renderTrialTable();
    }
  } catch (err) {
    console.error('Failed to delete session:', err);
    showError('Failed to delete session');
  }
}

// Save optimizer preferences
async function saveOptimizerPreferences(config) {
  try {
    const settings = await api.get('/settings');
    const prefs = settings.optimizer_preferences || {};
    
    prefs.last_strategy = config.strategy_name;
    prefs.total_trials = config.total_trials;
    prefs.score_metric = config.score_metric;
    prefs.score_mode = config.score_mode;
    prefs.target_min_trades = config.target_min_trades;
    prefs.target_profit_pct = config.target_profit_pct;
    prefs.max_drawdown_limit = config.max_drawdown_limit;
    prefs.target_romad = config.target_romad;
    
    await api.put('/settings', { optimizer_preferences: prefs });
  } catch (err) {
    console.error('Failed to save preferences:', err);
  }
}

// Setup event listeners
function setupEventListeners() {
  // Strategy selection
  els.strategySelect.addEventListener('change', (e) => {
    loadStrategyParams(e.target.value);
  });
  
  // Sync button
  document.getElementById('sync-from-backtest').addEventListener('click', syncFromBacktest);
  
  // Start/Stop
  els.startBtn.addEventListener('click', startOptimizer);
  els.stopBtn.addEventListener('click', stopOptimizer);
  
  // Clear log
  document.getElementById('clear-log').addEventListener('click', () => {
    els.logView.innerHTML = '';
  });
  
  // Sort buttons
  document.getElementById('sort-trial-num').addEventListener('click', () => sortTrials('number'));
  document.getElementById('sort-profit').addEventListener('click', () => sortTrials('profit'));
  document.getElementById('sort-dd').addEventListener('click', () => sortTrials('dd'));
  document.getElementById('sort-score').addEventListener('click', () => sortTrials('score'));
  
  // Best actions
  document.getElementById('export-best').addEventListener('click', exportBest);
  document.getElementById('rollback-best').addEventListener('click', rollbackLatestExport);
  
  // Selected actions
  document.getElementById('set-best').addEventListener('click', setSelectedAsBest);
  document.getElementById('open-log').addEventListener('click', openSelectedLog);
  document.getElementById('open-result').addEventListener('click', openSelectedResult);
  document.getElementById('compare-trial').addEventListener('click', showCompareModal);
  document.getElementById('apply-existing').addEventListener('click', (e) => {
    e.preventDefault();
    applyTrial(false);
  });
  document.getElementById('apply-new').addEventListener('click', (e) => {
    e.preventDefault();
    applyTrial(true);
  });
  
  // Delete session
  document.getElementById('delete-session').addEventListener('click', deleteSelectedSession);
  
  // Modal close
  els.compareModal.querySelector('.modal-close').addEventListener('click', () => {
    els.compareModal.classList.remove('active');
  });
  
  els.compareModal.addEventListener('click', (e) => {
    if (e.target === els.compareModal) {
      els.compareModal.classList.remove('active');
    }
  });
  
  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      els.compareModal.classList.remove('active');
    }
  });
}

// Sort trials
function sortTrials(by) {
  document.querySelectorAll('.trial-filters button').forEach(btn => btn.classList.remove('active'));
  const activeButtonId = by === 'number' ? 'sort-trial-num' : `sort-${by}`;
  document.getElementById(activeButtonId)?.classList.add('active');
  
  trials.sort((a, b) => {
    switch (by) {
      case 'number':
        return a.trial_number - b.trial_number;
      case 'profit':
        return (b.metrics?.total_profit_pct ?? 0) - (a.metrics?.total_profit_pct ?? 0);
      case 'dd':
        return (a.metrics?.max_drawdown_pct ?? 0) - (b.metrics?.max_drawdown_pct ?? 0);
      case 'score':
        return (b.score ?? 0) - (a.score ?? 0);
    }
  });
  
  renderTrialTable();
}

// Theme setup
function setupTheme() {
  const themeToggle = document.getElementById('theme-toggle');
  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const root = document.documentElement;
      const current = root.dataset.theme || 'dark';
      const next = current === 'dark' ? 'light' : 'dark';
      root.dataset.theme = next;
      localStorage.setItem('theme', next);
    });
  }
}

// Notification helpers
function showError(message) {
  // Simple alert for now - could be replaced with toast
  alert('Error: ' + message);
}

function showSuccess(message) {
  alert('Success: ' + message);
}

function showInfo(message) {
  alert(message);
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
