export function formatPct(value?: number | null): string {
  const next = Number(value ?? 0);
  return `${next.toFixed(2)}%`;
}

export function formatNumber(value?: number | null): string {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 4 }).format(Number(value ?? 0));
}

export function formatDate(value?: string | null): string {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
}

export function csvToList(value?: string): string[] {
  return (value ?? '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

export function listToCsv(value?: string[]): string {
  return (value ?? []).join(', ');
}
