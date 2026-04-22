/* Utility Functions */

export function formatPct(v) {
  return `${(v * 100).toFixed(2)}%`;
}

export function formatNumber(v, decimals = 2) {
  return v.toLocaleString(undefined, { 
    minimumFractionDigits: decimals, 
    maximumFractionDigits: decimals 
  });
}

export function formatDate(dateStr) {
  return new Date(dateStr).toLocaleString();
}

export function formatCurrency(v) {
  return v.toLocaleString(undefined, {
    style: "currency",
    currency: "USD"
  });
}

export function truncate(str, maxLength = 50) {
  if (str.length <= maxLength) return str;
  return str.substring(0, maxLength) + "...";
}
