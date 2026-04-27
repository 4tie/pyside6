/* Reusable UI Components */

import { formatPct, formatDate } from "./utils.js";

export function renderRunCard(run) {
  return `
    <div class="run-card" data-run-id="${run.run_id}">
      <div class="run-header">
        <span class="run-strategy">${run.strategy}</span>
        <span class="run-date">${formatDate(run.saved_at)}</span>
      </div>
      <div class="run-metrics">
        <div class="metric">
          <span class="metric-label">Profit</span>
          <span class="metric-value ${run.profit_total_pct >= 0 ? 'positive' : 'negative'}">
            ${formatPct(run.profit_total_pct / 100)}
          </span>
        </div>
        <div class="metric">
          <span class="metric-label">Win Rate</span>
          <span class="metric-value">${formatPct(run.win_rate_pct / 100)}</span>
        </div>
        <div class="metric">
          <span class="metric-label">Drawdown</span>
          <span class="metric-value">${formatPct(run.max_drawdown_pct / 100)}</span>
        </div>
      </div>
    </div>
  `;
}

export function renderProgressBar(progress) {
  return `
    <div class="progress">
      <div class="bar" style="width:${progress.progress_pct}%"></div>
      <span class="progress-text">${progress.progress_pct.toFixed(1)}%</span>
    </div>
  `;
}

export function renderMetricCard(label, value, unit = "") {
  return `
    <div class="metric-card">
      <span class="metric-label">${label}</span>
      <span class="metric-value">${value}${unit}</span>
    </div>
  `;
}

export function renderButton(text, onClick, variant = "primary") {
  const className = variant === "primary" ? "button" : "button button-secondary";
  return `<button class="${className}" onclick="${onClick}">${text}</button>`;
}

// Toast notification system
let toastContainer = null;

function getToastContainer() {
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.id = 'toast-container';
    toastContainer.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      z-index: 10000;
      display: flex;
      flex-direction: column;
      gap: 10px;
      max-width: 400px;
    `;
    document.body.appendChild(toastContainer);
  }
  return toastContainer;
}

export function showToast(message, type = 'info', duration = 5000) {
  const container = getToastContainer();
  
  const toast = document.createElement('div');
  toast.style.cssText = `
    padding: 12px 20px;
    border-radius: 8px;
    color: white;
    font-size: 14px;
    font-weight: 500;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    display: flex;
    align-items: center;
    gap: 10px;
    animation: slideIn 0.3s ease;
    cursor: pointer;
  `;
  
  // Color based on type
  const colors = {
    success: '#10b981',
    error: '#ef4444',
    warning: '#f59e0b',
    info: '#3b82f6'
  };
  
  toast.style.backgroundColor = colors[type] || colors.info;
  
  // Icon based on type
  const icons = {
    success: '✓',
    error: '✗',
    warning: '⚠',
    info: 'ℹ'
  };
  
  toast.innerHTML = `
    <span style="font-size: 18px;">${icons[type] || icons.info}</span>
    <span>${message}</span>
  `;
  
  // Click to dismiss
  toast.addEventListener('click', () => {
    toast.style.animation = 'slideOut 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  });
  
  container.appendChild(toast);
  
  // Auto dismiss
  if (duration > 0) {
    setTimeout(() => {
      if (toast.parentElement) {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => toast.remove(), 300);
      }
    }, duration);
  }
  
  return toast;
}

export function showSuccess(message, duration) {
  return showToast(message, 'success', duration);
}

export function showError(message, duration) {
  return showToast(message, 'error', duration);
}

export function showWarning(message, duration) {
  return showToast(message, 'warning', duration);
}

export function showInfo(message, duration) {
  return showToast(message, 'info', duration);
}

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
  @keyframes slideIn {
    from {
      transform: translateX(100%);
      opacity: 0;
    }
    to {
      transform: translateX(0);
      opacity: 1;
    }
  }
  
  @keyframes slideOut {
    from {
      transform: translateX(0);
      opacity: 1;
    }
    to {
      transform: translateX(100%);
      opacity: 0;
    }
  }
`;
document.head.appendChild(style);
