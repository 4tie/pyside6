interface StatusBadgeProps {
  status: string;
}

const TONE_MAP: Record<string, string> = {
  idle:     'neutral',
  running:  'warn',
  started:  'warn',
  complete: 'good',
  success:  'good',
  error:    'bad',
  failed:   'bad',
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const normalized = status.toLowerCase();
  const tone = TONE_MAP[normalized] ?? (
    normalized.includes('run') || normalized.includes('start') ? 'warn' :
    normalized.includes('complete') || normalized.includes('success') ? 'good' :
    normalized.includes('fail') || normalized.includes('error') ? 'bad' :
    'neutral'
  );

  return <span className={`status-badge tone-${tone}`}>{status || 'unknown'}</span>;
}
