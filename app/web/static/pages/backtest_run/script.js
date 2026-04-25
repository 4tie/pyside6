/* Backtest Run Page Script */

import { getStrategies, getPairs, saveFavorites, downloadData, saveBacktestConfig, getBacktestConfig } from '/static/shared/js/api.js';
import { initTheme, toggleTheme } from '/static/shared/js/theme.js';

// Initialize theme
initTheme();

// Theme toggle handler
document.getElementById('theme-toggle').addEventListener('click', toggleTheme);

// Polling for status updates
let pollingInterval = null;
let currentRunId = null;
// Start polling for status updates
function startPolling() {
  if (pollingInterval) return;
  
  addLog('info', 'Starting polling fallback for status updates...');
  
  pollingInterval = setInterval(async () => {
    try {
      const response = await fetch('/api/backtest/status');
      if (response.ok) {
        const data = await response.json();
        if (data.status === 'complete' && data.run_id) {
          addLog('success', 'Task completed successfully (via polling)');
          resetBacktestButton();
          clearInterval(pollingInterval);
          pollingInterval = null;
          currentRunId = data.run_id;
          setTimeout(() => {
            window.location.href = `/static/pages/run_detail/index.html?run_id=${data.run_id}`;
          }, 1000);
        } else if (data.status === 'error') {
          addLog('error', `Task failed: ${data.message}`);
          resetBacktestButton();
          clearInterval(pollingInterval);
          pollingInterval = null;
        }
      }
    } catch (e) {
      // Silent fail on polling errors
    }
  }, 2000); // Poll every 2 seconds
}

// Reset backtest button state
function resetBacktestButton() {
  const btn = document.getElementById('run-backtest-btn');
  if (btn) {
    btn.disabled = false;
    btn.textContent = 'Run Backtest';
  }
}



// State
let allPairs = [];
let favorites = [];
let selectedPairs = new Set();

// Load page data
async function loadPageData() {
  try {
    // Load strategies
    const strategies = await getStrategies();
    const strategySelect = document.getElementById('strategy');
    strategySelect.innerHTML = strategies.map(s => `<option value="${s.name}">${s.name}</option>`).join('');
    
    // Load pairs and favorites
    const pairsData = await getPairs();
    allPairs = pairsData.pairs;
    favorites = pairsData.favorites;
    
    // Load saved config
    const config = await getBacktestConfig();
    if (config.strategy) document.getElementById('strategy').value = config.strategy;
    if (config.timeframe) document.getElementById('timeframe').value = config.timeframe;
    if (config.timerange) document.getElementById('timerange').value = config.timerange;
    if (config.max_open_trades) document.getElementById('max_open_trades').value = config.max_open_trades;
    if (config.dry_run_wallet) document.getElementById('dry_run_wallet').value = config.dry_run_wallet;
    if (config.pairs) selectedPairs = new Set(config.pairs);
    
    renderPairs();
    updatePairsCount();
  } catch (error) {
    console.error('Failed to load page data:', error);
    addLog('error', 'Failed to load page data');
  }
}

// Render pairs
function renderPairs() {
  const container = document.getElementById('pairs-container');
  const searchTerm = document.getElementById('pairs-search').value.toLowerCase();
  
  // Sort: favorites first, then alphabetically
  const sortedPairs = [...allPairs].sort((a, b) => {
    const aFav = favorites.includes(a);
    const bFav = favorites.includes(b);
    if (aFav && !bFav) return -1;
    if (!aFav && bFav) return 1;
    return a.localeCompare(b);
  });
  
  const filteredPairs = sortedPairs.filter(pair => pair.toLowerCase().includes(searchTerm));
  
  container.innerHTML = filteredPairs.map(pair => `
    <div class="pair-item ${favorites.includes(pair) ? 'favorite' : ''}" data-pair="${pair}">
      <input type="checkbox" class="pair-checkbox" 
             value="${pair}" 
             ${selectedPairs.has(pair) ? 'checked' : ''}>
      <span class="pair-name">${pair}</span>
      <span class="favorite-icon ${favorites.includes(pair) ? 'active' : ''}" data-pair="${pair}">♥</span>
    </div>
  `).join('');
  
  // Add event listeners
  container.querySelectorAll('.pair-checkbox').forEach(checkbox => {
    checkbox.addEventListener('change', (e) => {
      const pair = e.target.value;
      if (e.target.checked) {
        selectedPairs.add(pair);
      } else {
        selectedPairs.delete(pair);
      }
      updatePairsCount();
      saveConfig();
    });
  });
  
  container.querySelectorAll('.favorite-icon').forEach(icon => {
    icon.addEventListener('click', (e) => {
      e.stopPropagation();
      const pair = e.target.dataset.pair;
      toggleFavorite(pair);
    });
  });
}

// Toggle favorite
async function toggleFavorite(pair) {
  if (favorites.includes(pair)) {
    favorites = favorites.filter(p => p !== pair);
  } else {
    favorites.push(pair);
  }
  
  await saveFavorites(favorites);
  renderPairs();
}

// Update pairs count
function updatePairsCount() {
  document.querySelector('.pairs-count').textContent = `Selected: ${selectedPairs.size}`;
}

// Randomize pairs
document.getElementById('randomize-pairs').addEventListener('click', () => {
  const maxOpenTrades = parseInt(document.getElementById('max_open_trades').value) || 3;
  const count = Math.min(maxOpenTrades, allPairs.length);
  
  // Clear current selection
  selectedPairs.clear();
  
  // Select random pairs
  const shuffled = [...allPairs].sort(() => Math.random() - 0.5);
  for (let i = 0; i < count; i++) {
    selectedPairs.add(shuffled[i]);
  }
  
  renderPairs();
  updatePairsCount();
  saveConfig();
});

// Search pairs
document.getElementById('pairs-search').addEventListener('input', () => {
  renderPairs();
});

// Download data button
document.getElementById('download-data-btn').addEventListener('click', async () => {
  const btn = document.getElementById('download-data-btn');
  
  // Prevent double-click
  if (btn.disabled) return;
  
  const timeframe = document.getElementById('timeframe').value;
  const timerange = document.getElementById('timerange').value;
  const pairsArray = Array.from(selectedPairs);
  
  if (!timeframe) {
    addLog('error', 'Please select a timeframe');
    return;
  }
  
  if (pairsArray.length === 0) {
    addLog('error', 'Please select at least one pair');
    return;
  }
  
  // Disable button to prevent double-click
  btn.disabled = true;
  btn.textContent = 'Downloading...';
  
  addLog('info', `Downloading data for ${pairsArray.length} pairs...`);
  addLog('info', `Timeframe: ${timeframe}`);
  addLog('info', `Timerange: ${timerange || 'Not specified'}`);
  
  try {
    const result = await downloadData({
      timeframe,
      timerange,
      pairs: pairsArray,
    });
    
    if (result.success) {
      addLog('success', `Download started: ${result.message}`);
    } else {
      addLog('error', `Download failed: ${result.message}`);
    }
  } catch (error) {
    console.error('Download failed:', error);
    addLog('error', 'Download failed. Please try again.');
  } finally {
    // Re-enable button after request completes
    btn.disabled = false;
    btn.textContent = 'Download Data';
  }
});

// Run backtest button
document.getElementById('run-backtest-btn').addEventListener('click', async () => {
  const btn = document.getElementById('run-backtest-btn');
  
  // Prevent double-click
  if (btn.disabled) return;
  
  const strategy = document.getElementById('strategy').value;
  const timeframe = document.getElementById('timeframe').value;
  const timerange = document.getElementById('timerange').value;
  const pairsArray = Array.from(selectedPairs);
  const maxOpenTrades = document.getElementById('max_open_trades').value;
  const dryRunWallet = document.getElementById('dry_run_wallet').value;
  
  if (!strategy) {
    addLog('error', 'Please select a strategy');
    return;
  }
  
  if (!timeframe) {
    addLog('error', 'Please select a timeframe');
    return;
  }
  
  if (pairsArray.length === 0) {
    addLog('error', 'Please select at least one pair');
    return;
  }
  
  // Disable button to prevent double-click
  btn.disabled = true;
  btn.textContent = 'Running...';
  
  addLog('info', `Starting backtest for ${strategy}...`);
  addLog('info', `Strategy: ${strategy}`);
  addLog('info', `Timeframe: ${timeframe}`);
  addLog('info', `Timerange: ${timerange || 'Not specified'}`);
  addLog('info', `Pairs: ${pairsArray.join(', ')}`);
  addLog('info', `Max Open Trades: ${maxOpenTrades}`);
  addLog('info', `Dry Run Wallet: ${dryRunWallet}`);
  
   try {
     const response = await fetch('/api/backtest/execute', {
       method: 'POST',
       headers: {
         'Content-Type': 'application/json',
       },
       body: JSON.stringify({
         strategy,
         timeframe,
         timerange,
         pairs: pairsArray,
         max_open_trades: parseInt(maxOpenTrades),
         dry_run_wallet: parseFloat(dryRunWallet),
       }),
     });
     
     if (!response.ok) {
       const errorData = await response.json().catch(() => ({}));
       throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
     }
     
     const result = await response.json();
     addLog('info', result.message);
     // Start polling for status updates after successful backtest initiation
     startPolling();
   } catch (error) {
     console.error('Failed to start backtest:', error);
     addLog('error', `Failed to start backtest: ${error.message}`);
     btn.disabled = false;
     btn.textContent = 'Run Backtest';
   }
});

// Clear logs
document.getElementById('clear-logs').addEventListener('click', () => {
  document.getElementById('logs-container').innerHTML = '<div class="log-entry">Logs cleared</div>';
});

// Add log entry
function addLog(level, message) {
  const logsContainer = document.getElementById('logs-container');
  const logEntry = document.createElement('div');
  logEntry.className = `log-entry ${level}`;
  logEntry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
  logsContainer.appendChild(logEntry);
  logsContainer.scrollTop = logsContainer.scrollHeight;
}

// Save config
async function saveConfig() {
  try {
    await saveBacktestConfig({
      strategy: document.getElementById('strategy').value || null,
      timeframe: document.getElementById('timeframe').value || null,
      pairs: Array.from(selectedPairs),
      timerange: document.getElementById('timerange').value || null,
      max_open_trades: parseInt(document.getElementById('max_open_trades').value) || null,
      dry_run_wallet: parseFloat(document.getElementById('dry_run_wallet').value) || null,
    });
  } catch (error) {
    console.error('Failed to save config:', error);
  }
}

// Auto-save on form changes
document.querySelectorAll('input, select').forEach(input => {
  input.addEventListener('change', saveConfig);
});

// Load page data on mount
loadPageData();
