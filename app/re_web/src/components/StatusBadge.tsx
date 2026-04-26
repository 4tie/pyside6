interface StatusBadgeProps {
  status: string;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const normalized = status.toLowerCase();
  const tone =
    normalized.includes('run') || normalized.includes('start')
      ? 'warn'
      : normalized.includes('complete') || normalized.includes('success')
        ? 'good'
        : normalized.includes('fail') || normalized.includes('error')
          ? 'bad'
          : 'neutral';

  return <span className={`status-badge tone-${tone}`}>{status || 'unknown'}</span>;
}
