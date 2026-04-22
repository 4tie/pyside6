/* Dashboard Page Script */

import { getRuns, getStrategies } from '../../shared/js/api.js';
import { formatPct } from '../../shared/js/utils.js';
import { initTheme, toggleTheme } from '../../shared/js/theme.js';
import { renderRunCard } from '../../shared/js/components.js';

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
    
    // Render runs
    if (runs.length === 0) {
      runsList.innerHTML = '<div class="loading">No runs found</div>';
    } else {
      runsList.innerHTML = runs.map(run => renderRunCard(run)).join('');
      
      // Add click handlers
      runsList.querySelectorAll('.run-card').forEach(card => {
        card.addEventListener('click', () => {
          const runId = card.dataset.runId;
          window.location.href = `/pages/run_detail/index.html?run_id=${runId}`;
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
