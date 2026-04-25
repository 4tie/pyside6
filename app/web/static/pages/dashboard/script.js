/* Dashboard Page Script */

import { getRuns, getStrategies, getRun } from '/static/shared/js/api.js';
import { formatPct } from '/static/shared/js/utils.js';
import { initTheme, toggleTheme } from '/static/shared/js/theme.js';
import { renderRunCard, showSuccess, showError } from '/static/shared/js/components.js';

// Initialize theme
initTheme();

// Theme toggle handler
document.getElementById('theme-toggle').addEventListener('click', toggleTheme);

// Refresh button handler
document.getElementById('refresh-btn').addEventListener('click', () => {
  loadDashboard();
  showSuccess('Dashboard refreshed');
});

// Chart instances
let equityChart = null;
let profitChart = null;

// Render equity chart
function renderEquityChart(trades) {
  const ctx = document.getElementById('equity-chart');
  if (!ctx || !trades || trades.length === 0) return;
  
  // Calculate equity curve
  let balance = 100;
  const equityData = [balance];
  const labels = ['Start'];
  
  trades.forEach((trade, index) => {
    balance += trade.profit_abs || 0;
    equityData.push(balance);
    labels.push(`Trade ${index + 1}`);
  });
  
  if (equityChart) {
    equityChart.destroy();
  }
  
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const textColor = isDark ? '#e5e7eb' : '#374151';
  const gridColor = isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
  
  equityChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: 'Equity',
        data: equityData,
        borderColor: '#8b5cf6',
        backgroundColor: 'rgba(139, 92, 246, 0.1)',
        fill: true,
        tension: 0.1,
        pointRadius: 2,
        pointHoverRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false
        }
      },
      scales: {
        x: {
          ticks: {
            color: textColor,
            maxTicksLimit: 10
          },
          grid: {
            color: gridColor
          }
        },
        y: {
          ticks: {
            color: textColor
          },
          grid: {
            color: gridColor
          },
          beginAtZero: false
        }
      }
    }
  });
}

// Render profit distribution chart
function renderProfitChart(trades) {
  const ctx = document.getElementById('profit-chart');
  if (!ctx || !trades || trades.length === 0) return;
  
  const profits = trades.map(t => t.profit_abs || 0);
  
  if (profitChart) {
    profitChart.destroy();
  }
  
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const textColor = isDark ? '#e5e7eb' : '#374151';
  const gridColor = isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
  
  profitChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: profits.map((_, i) => `T${i + 1}`),
      datasets: [{
        label: 'Profit',
        data: profits,
        backgroundColor: profits.map(p => p >= 0 ? 'rgba(16, 185, 129, 0.8)' : 'rgba(239, 68, 68, 0.8)'),
        borderColor: profits.map(p => p >= 0 ? '#10b981' : '#ef4444'),
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false
        }
      },
      scales: {
        x: {
          ticks: {
            color: textColor,
            maxTicksLimit: 15
          },
          grid: {
            color: gridColor
          }
        },
        y: {
          ticks: {
            color: textColor
          },
          grid: {
            color: gridColor
          }
        }
      }
    }
  });
}

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
      // Calculate best metrics (matching PySide6)
      const profits = runs.map(r => r.profit_total_pct);
      const winRates = runs.map(r => r.win_rate_pct);
      const drawdowns = runs.map(r => r.max_drawdown_pct);
      
      const bestProfit = Math.max(...profits);
      const bestWinRate = Math.max(...winRates);
      const minDrawdown = Math.min(...drawdowns);
      
      const bestProfitEl = document.getElementById('best-profit');
      bestProfitEl.textContent = formatPct(bestProfit / 100);
      bestProfitEl.className = `metric-value ${bestProfit >= 0 ? 'positive' : 'negative'}`;
      
      document.getElementById('best-winrate').textContent = formatPct(bestWinRate / 100);
      document.getElementById('min-drawdown').textContent = formatPct(minDrawdown / 100);
      
      // Latest run date
      const latestRun = runs.sort((a, b) => new Date(b.saved_at) - new Date(a.saved_at))[0];
      document.getElementById('latest-run').textContent = latestRun.saved_at ? latestRun.saved_at.split('T')[0] : '-';
      
      // Load latest run details for charts
      try {
        const latestRunDetails = await getRun(latestRun.run_id);
        if (latestRunDetails.trades && latestRunDetails.trades.length > 0) {
          renderEquityChart(latestRunDetails.trades);
          renderProfitChart(latestRunDetails.trades);
        }
      } catch (e) {
        console.warn('Failed to load latest run details for charts:', e);
      }
    } else {
      // Reset metrics when no runs
      document.getElementById('best-profit').textContent = '0%';
      document.getElementById('best-winrate').textContent = '0%';
      document.getElementById('min-drawdown').textContent = '0%';
      document.getElementById('latest-run').textContent = '-';
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
    showError('Failed to load dashboard data');
    runsList.innerHTML = '<div class="error">Failed to load data. Please try again.</div>';
  }
}

// Load dashboard on mount
loadDashboard();
