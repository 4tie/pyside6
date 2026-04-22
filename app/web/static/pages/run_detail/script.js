/* Run Detail Page Script */

import { getRun, getDiagnosis, deleteRun } from '../../shared/js/api.js';
import { formatPct, formatDate, formatCurrency } from '../../shared/js/utils.js';
import { initTheme, toggleTheme } from '../../shared/js/theme.js';

// Initialize theme
initTheme();

// Theme toggle handler
document.getElementById('theme-toggle').addEventListener('click', toggleTheme);

// Get run_id from URL
const urlParams = new URLSearchParams(window.location.search);
const runId = urlParams.get('run_id');

if (!runId) {
  document.getElementById('loading').classList.add('hidden');
  document.getElementById('error').textContent = 'No run ID provided';
  document.getElementById('error').classList.remove('hidden');
} else {
  loadRunDetail(runId);
}

// Tab switching
document.querySelectorAll('.tab-button').forEach(button => {
  button.addEventListener('click', () => {
    const tab = button.dataset.tab;
    
    // Update button states
    document.querySelectorAll('.tab-button').forEach(b => b.classList.remove('active'));
    button.classList.add('active');
    
    // Update panel visibility
    document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.remove('active'));
    document.getElementById(`${tab}-panel`).classList.add('active');
  });
});

async function loadRunDetail(runId) {
  try {
    const run = await getRun(runId);
    
    document.getElementById('loading').classList.add('hidden');
    document.getElementById('run-content').classList.remove('hidden');
    
    // Update summary
    document.getElementById('strategy').textContent = run.strategy;
    document.getElementById('timeframe').textContent = run.timeframe;
    document.getElementById('timerange').textContent = run.timerange;
    document.getElementById('pairs').textContent = run.pairs.join(', ');
    
    const profitEl = document.getElementById('profit');
    profitEl.textContent = formatPct(run.profit_total_pct / 100);
    profitEl.className = `value ${run.profit_total_pct >= 0 ? 'text-success' : 'text-error'}`;
    
    document.getElementById('winrate').textContent = formatPct(run.win_rate_pct / 100);
    document.getElementById('drawdown').textContent = formatPct(run.max_drawdown_pct / 100);
    document.getElementById('trades-count').textContent = run.trades_count;
    
    // Render trades table
    const tradesBody = document.getElementById('trades-body');
    tradesBody.innerHTML = run.trades.map(trade => `
      <tr>
        <td>${trade.pair}</td>
        <td>${formatDate(trade.open_date)}</td>
        <td>${formatDate(trade.close_date)}</td>
        <td class="${trade.profit >= 0 ? 'text-success' : 'text-error'}">${formatPct(trade.profit)}</td>
        <td>${trade.exit_reason}</td>
      </tr>
    `).join('');
    
    // Load diagnosis
    loadDiagnosis(runId);
    
    // Render parameters
    renderParams(run.params);
    
  } catch (error) {
    console.error('Failed to load run:', error);
    document.getElementById('loading').classList.add('hidden');
    document.getElementById('error').textContent = 'Failed to load run. Please try again.';
    document.getElementById('error').classList.remove('hidden');
  }
}

async function loadDiagnosis(runId) {
  const diagnosisContent = document.getElementById('diagnosis-content');
  
  try {
    const diagnosis = await getDiagnosis(runId);
    
    if (diagnosis.issues.length === 0) {
      diagnosisContent.innerHTML = '<p>No issues found.</p>';
    } else {
      diagnosisContent.innerHTML = diagnosis.issues.map(issue => `
        <div class="diagnosis-item severity-${issue.severity}">
          <div class="rule-id">${issue.rule_id}</div>
          <div class="message">${issue.message}</div>
        </div>
      `).join('');
    }
  } catch (error) {
    console.error('Failed to load diagnosis:', error);
    diagnosisContent.innerHTML = '<p class="error">Failed to load diagnosis.</p>';
  }
}

function renderParams(params) {
  const paramsContent = document.getElementById('params-content');
  
  if (!params || Object.keys(params).length === 0) {
    paramsContent.innerHTML = '<p>No parameters available.</p>';
    return;
  }
  
  paramsContent.innerHTML = `
    <div class="params-grid">
      ${Object.entries(params).map(([key, value]) => `
        <div class="param-item">
          <span class="key">${key}</span>
          <span class="value">${JSON.stringify(value)}</span>
        </div>
      `).join('')}
    </div>
  `;
}
