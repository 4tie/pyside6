/* Run Detail Page Script */

import { getRun, getDiagnosis, deleteRun, getRuns, getRunDiff, rollbackRun } from '/static/shared/js/api.js';
import { formatPct, formatDate, formatCurrency } from '/static/shared/js/utils.js';
import { initTheme, toggleTheme } from '/static/shared/js/theme.js';

// Initialize theme
initTheme();

// Theme toggle handler
document.getElementById('theme-toggle').addEventListener('click', toggleTheme);

// Get run_id from URL
const urlParams = new URLSearchParams(window.location.search);
const runId = urlParams.get('run_id');

if (!runId) {
  // Redirect to dashboard if no run_id provided
  window.location.href = '/static/pages/dashboard/index.html';
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
    
    // Update trades summary
    const totalTrades = run.trades.length;
    const wins = run.trades.filter(t => t.profit >= 0).length;
    const losses = run.trades.filter(t => t.profit < 0).length;
    const winRate = totalTrades > 0 ? ((wins / totalTrades) * 100).toFixed(1) : 0;
    
    document.getElementById('total-trades').textContent = totalTrades;
    document.getElementById('total-wins').textContent = wins;
    document.getElementById('total-losses').textContent = losses;
    document.getElementById('trades-winrate').textContent = `${winRate}%`;
    
    // Load diagnosis
    loadDiagnosis(runId);
    
    // Render parameters
    renderParams(run.params);
    
    // Load baseline runs for diff
    loadBaselineRuns(run.strategy, runId);
    
    // Render charts
    renderCharts(run);
    
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
    const errorMsg = error?.message || error?.toString() || 'Unknown error';
    diagnosisContent.innerHTML = `<p class="error">Failed to load diagnosis: ${errorMsg}</p>`;
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

function renderCharts(run) {
  // Render equity chart
  renderEquityChart(run);
  
  // Render drawdown chart
  renderDrawdownChart(run);
  
  // Render profit distribution chart
  renderProfitChart(run);
}

function renderEquityChart(run) {
  const ctx = document.getElementById('equity-chart');
  if (!ctx) return;
  
  // Generate equity curve data from trades
  let balance = run.starting_balance || 100;
  const equityData = [balance];
  const labels = ['Start'];
  
  run.trades.forEach(trade => {
    balance += trade.profit_abs || 0;
    equityData.push(balance);
    labels.push(formatDate(trade.close_date));
  });
  
  new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: 'Equity',
        data: equityData,
        borderColor: 'rgb(75, 192, 192)',
        backgroundColor: 'rgba(75, 192, 192, 0.1)',
        fill: true,
        tension: 0.1
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: {
          display: true
        }
      },
      scales: {
        y: {
          beginAtZero: false
        }
      }
    }
  });
}

function renderDrawdownChart(run) {
  const ctx = document.getElementById('drawdown-chart');
  if (!ctx) return;
  
  // Generate drawdown data
  let balance = run.starting_balance || 100;
  let peak = balance;
  const drawdownData = [0];
  const labels = ['Start'];
  
  run.trades.forEach(trade => {
    balance += trade.profit_abs || 0;
    if (balance > peak) peak = balance;
    const drawdown = ((peak - balance) / peak) * 100;
    drawdownData.push(drawdown);
    labels.push(formatDate(trade.close_date));
  });
  
  new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: 'Drawdown %',
        data: drawdownData,
        borderColor: 'rgb(255, 99, 132)',
        backgroundColor: 'rgba(255, 99, 132, 0.1)',
        fill: true,
        tension: 0.1
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: {
          display: true
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          max: Math.max(...drawdownData) * 1.1
        }
      }
    }
  });
}

function renderProfitChart(run) {
  const ctx = document.getElementById('profit-chart');
  if (!ctx) return;
  
  // Calculate profit distribution
  const profits = run.trades.map(t => t.profit_abs || 0);
  const winningTrades = profits.filter(p => p > 0);
  const losingTrades = profits.filter(p => p < 0);
  
  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: ['Winning Trades', 'Losing Trades'],
      datasets: [{
        label: 'Total Profit',
        data: [
          winningTrades.reduce((a, b) => a + b, 0),
          losingTrades.reduce((a, b) => a + b, 0)
        ],
        backgroundColor: [
          'rgba(75, 192, 192, 0.8)',
          'rgba(255, 99, 132, 0.8)'
        ]
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: {
          display: true
        }
      },
      scales: {
        y: {
          beginAtZero: true
        }
      }
    }
  });
}

async function loadBaselineRuns(strategy, currentRunId) {
  const baselineSelect = document.getElementById('baseline-select');
  
  try {
    const runs = await getRuns();
    const strategyRuns = runs.filter(r => r.strategy === strategy && r.run_id !== currentRunId);
    
    if (strategyRuns.length === 0) {
      baselineSelect.innerHTML = '<option value="">No other runs available</option>';
      return;
    }
    
    // Sort by date descending (most recent first)
    strategyRuns.sort((a, b) => new Date(b.saved_at) - new Date(a.saved_at));
    
    baselineSelect.innerHTML = `
      <option value="">Select a baseline run...</option>
      ${strategyRuns.map(run => `
        <option value="${run.run_id}">${run.saved_at} - ${run.run_id}</option>
      `).join('')}
    `;
    
    // Select the most recent run by default
    if (strategyRuns.length > 0) {
      baselineSelect.value = strategyRuns[0].run_id;
    }
  } catch (error) {
    console.error('Failed to load baseline runs:', error);
    baselineSelect.innerHTML = '<option value="">Failed to load runs</option>';
  }
}

// Compare diff button handler
document.getElementById('compare-diff-btn').addEventListener('click', async () => {
  const baselineSelect = document.getElementById('baseline-select');
  const baselineId = baselineSelect.value;
  const diffContent = document.getElementById('diff-content');
  const rollbackSection = document.getElementById('rollback-section');
  
  if (!baselineId) {
    diffContent.innerHTML = '<p class="error">Please select a baseline run to compare.</p>';
    return;
  }
  
  diffContent.innerHTML = '<div class="loading">Loading diff...</div>';
  rollbackSection.classList.add('hidden');
  
  try {
    const diff = await getRunDiff(runId, baselineId);
    
    if (diff.parameter_changes.length === 0 && !diff.has_code_diff) {
      diffContent.innerHTML = '<div class="no-changes">No changes detected between runs.</div>';
      return;
    }
    
    let html = '';
    
    if (diff.parameter_changes.length > 0) {
      html += `
        <div class="diff-section">
          <h4>Parameter Changes (${diff.parameter_changes.length})</h4>
          ${diff.parameter_changes.map(change => `
            <div class="diff-item">
              <div class="diff-item-header">
                <span class="diff-item-parameter">${change.parameter}</span>
              </div>
              <div class="diff-item-values">
                <div class="diff-item-value before">
                  <div class="diff-item-value-label">Before</div>
                  <div class="diff-item-value-content">${JSON.stringify(change.before)}</div>
                </div>
                <div class="diff-item-value after">
                  <div class="diff-item-value-label">After</div>
                  <div class="diff-item-value-content">${JSON.stringify(change.after)}</div>
                </div>
              </div>
            </div>
          `).join('')}
        </div>
      `;
    }
    
    if (diff.has_code_diff) {
      html += `
        <div class="diff-section">
          <h4>Code Changes</h4>
          <p>Code diff comparison would be displayed here.</p>
        </div>
      `;
    }
    
    diffContent.innerHTML = html;
    rollbackSection.classList.remove('hidden');
  } catch (error) {
    console.error('Failed to load diff:', error);
    diffContent.innerHTML = '<p class="error">Failed to load diff. Please try again.</p>';
  }
});

// Rollback button handler
document.getElementById('rollback-btn').addEventListener('click', async () => {
  const baselineSelect = document.getElementById('baseline-select');
  const baselineId = baselineSelect.value;
  
  if (!baselineId) {
    alert('Please select a baseline run to rollback to.');
    return;
  }
  
  if (!confirm(`Are you sure you want to rollback to ${baselineId}? This will modify the strategy file on disk.`)) {
    return;
  }
  
  try {
    const result = await rollbackRun(runId, baselineId);
    
    if (result.success) {
      alert(`Rollback successful: ${result.message}`);
    } else {
      alert(`Rollback failed: ${result.message}`);
    }
  } catch (error) {
    console.error('Failed to rollback:', error);
    alert('Failed to rollback. Please try again.');
  }
});
