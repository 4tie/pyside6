/* Dashboard Page Script */

import { getRuns, getStrategies } from '/static/shared/js/api.js';
import { formatPct } from '/static/shared/js/utils.js';
import { initTheme, toggleTheme } from '/static/shared/js/theme.js';
import { renderRunCard } from '/static/shared/js/components.js';

// Initialize theme
initTheme();

// Theme toggle handler
document.getElementById('theme-toggle').addEventListener('click', toggleTheme);

// Load dashboard data
async function loadDashboard() {
  const runsList = document.getElementById('runs-list');
  
  try {
    // Load runs
    const runs = await getRuns();
    
    // Load strategies
    const strategies = await getStrategies();
    
    // Update metrics
    document.getElementById('total-runs').textContent = runs.length;
    document.getElementById('total-strategies').textContent = strategies.length;
    
    if (runs.length > 0) {
      const avgProfit = runs.reduce((sum, r) => sum + r.profit_total_pct, 0) / runs.length;
      const avgWinrate = runs.reduce((sum, r) => sum + r.win_rate_pct, 0) / runs.length;
      
      document.getElementById('avg-profit').textContent = formatPct(avgProfit / 100);
      document.getElementById('avg-winrate').textContent = formatPct(avgWinrate / 100);
    }
    
    // Render runs grouped by strategy
    if (runs.length === 0) {
      runsList.innerHTML = '<div class="loading">No runs found</div>';
    } else {
      // Group runs by strategy
      const runsByStrategy = runs.reduce((acc, run) => {
        if (!acc[run.strategy]) {
          acc[run.strategy] = [];
        }
        acc[run.strategy].push(run);
        return acc;
      }, {});
      
      // Render strategy sections
      let html = '';
      for (const [strategy, strategyRuns] of Object.entries(runsByStrategy)) {
        html += `
          <div class="strategy-section">
            <div class="strategy-header" data-strategy="${strategy}">
              <div class="strategy-title">
                <button class="toggle-button" data-expanded="true">▼</button>
                <h3>${strategy}</h3>
              </div>
              <span class="run-count">${strategyRuns.length} runs</span>
            </div>
            <div class="strategy-runs">
              ${strategyRuns.map(run => renderRunCard(run)).join('')}
            </div>
          </div>
        `;
      }
      runsList.innerHTML = html;
      
      // Add toggle handlers for strategy sections
      runsList.querySelectorAll('.strategy-header').forEach(header => {
        header.addEventListener('click', () => {
          const toggleButton = header.querySelector('.toggle-button');
          const strategyRuns = header.nextElementSibling;
          const isExpanded = toggleButton.dataset.expanded === 'true';
          
          if (isExpanded) {
            toggleButton.dataset.expanded = 'false';
            toggleButton.textContent = '▶';
            strategyRuns.classList.add('collapsed');
          } else {
            toggleButton.dataset.expanded = 'true';
            toggleButton.textContent = '▼';
            strategyRuns.classList.remove('collapsed');
          }
        });
      });
      
      // Add click handlers for run cards (stop propagation to avoid triggering collapse)
      runsList.querySelectorAll('.run-card').forEach(card => {
        card.addEventListener('click', (e) => {
          e.stopPropagation();
          const runId = card.dataset.runId;
          window.location.href = `/static/pages/run_detail/index.html?run_id=${runId}`;
        });
      });
    }
  } catch (error) {
    console.error('Failed to load dashboard:', error);
    runsList.innerHTML = '<div class="error">Failed to load data. Please try again.</div>';
  }
}

// Load dashboard on mount
loadDashboard();
