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
