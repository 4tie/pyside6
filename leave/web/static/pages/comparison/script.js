/* Comparison Page Script */

import { getRuns, compareRuns } from '/static/shared/js/api.js';
import { formatPct } from '/static/shared/js/utils.js';
import { initTheme, toggleTheme } from '/static/shared/js/theme.js';

// Initialize theme
initTheme();

// Theme toggle handler
document.getElementById('theme-toggle').addEventListener('click', toggleTheme);

// Load runs into dropdowns
async function loadRuns() {
  try {
    const runs = await getRuns();
    const selectA = document.getElementById('run-a');
    const selectB = document.getElementById('run-b');
    
    runs.forEach(run => {
      const optionA = document.createElement('option');
      optionA.value = run.run_id;
      optionA.textContent = `${run.strategy} - ${run.saved_at}`;
      selectA.appendChild(optionA);
      
      const optionB = document.createElement('option');
      optionB.value = run.run_id;
      optionB.textContent = `${run.strategy} - ${run.saved_at}`;
      selectB.appendChild(optionB);
    });
  } catch (error) {
    console.error('Failed to load runs:', error);
  }
}

// Compare runs
document.getElementById('compare-btn').addEventListener('click', async () => {
  const runAId = document.getElementById('run-a').value;
  const runBId = document.getElementById('run-b').value;
  
  if (!runAId || !runBId) {
    alert('Please select both runs to compare');
    return;
  }
  
  if (runAId === runBId) {
    alert('Please select different runs to compare');
    return;
  }
  
  try {
    const comparison = await compareRuns(runAId, runBId);
    
    document.getElementById('comparison-results').classList.remove('hidden');
    
    // Update verdict
    const verdictEl = document.getElementById('verdict');
    verdictEl.className = 'verdict';
    
    if (comparison.verdict === 'improvement') {
      verdictEl.classList.add('improvement');
      verdictEl.textContent = 'Run B is an IMPROVEMENT over Run A';
    } else if (comparison.verdict === 'degradation') {
      verdictEl.classList.add('degradation');
      verdictEl.textContent = 'Run B is a DEGRADATION compared to Run A';
    } else {
      verdictEl.classList.add('neutral');
      verdictEl.textContent = 'Run B is NEUTRAL compared to Run A';
    }
    
    // Get run details for full comparison
    const runA = await getRun(runAId);
    const runB = await getRun(runBId);
    
    // Render comparison table
    const tbody = document.getElementById('comparison-body');
    tbody.innerHTML = `
      <tr>
        <td>Strategy</td>
        <td>${runA.strategy}</td>
        <td>${runB.strategy}</td>
        <td class="diff-neutral">-</td>
      </tr>
      <tr>
        <td>Timeframe</td>
        <td>${runA.timeframe}</td>
        <td>${runB.timeframe}</td>
        <td class="diff-neutral">-</td>
      </tr>
      <tr>
        <td>Profit</td>
        <td>${formatPct(runA.profit_total_pct / 100)}</td>
        <td>${formatPct(runB.profit_total_pct / 100)}</td>
        <td class="${comparison.profit_diff >= 0 ? 'diff-positive' : 'diff-negative'}">
          ${comparison.profit_diff >= 0 ? '+' : ''}${formatPct(comparison.profit_diff / 100)}
        </td>
      </tr>
      <tr>
        <td>Win Rate</td>
        <td>${formatPct(runA.win_rate_pct / 100)}</td>
        <td>${formatPct(runB.win_rate_pct / 100)}</td>
        <td class="${comparison.winrate_diff >= 0 ? 'diff-positive' : 'diff-negative'}">
          ${comparison.winrate_diff >= 0 ? '+' : ''}${formatPct(comparison.winrate_diff / 100)}
        </td>
      </tr>
      <tr>
        <td>Max Drawdown</td>
        <td>${formatPct(runA.max_drawdown_pct / 100)}</td>
        <td>${formatPct(runB.max_drawdown_pct / 100)}</td>
        <td class="${comparison.drawdown_diff <= 0 ? 'diff-positive' : 'diff-negative'}">
          ${comparison.drawdown_diff >= 0 ? '+' : ''}${formatPct(comparison.drawdown_diff / 100)}
        </td>
      </tr>
      <tr>
        <td>Trades</td>
        <td>${runA.trades_count}</td>
        <td>${runB.trades_count}</td>
        <td class="diff-neutral">${runB.trades_count - runA.trades_count}</td>
      </tr>
    `;
    
  } catch (error) {
    console.error('Failed to compare runs:', error);
    alert('Failed to compare runs. Please try again.');
  }
});

// Load runs on mount
loadRuns();
