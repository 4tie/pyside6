import type { ReactNode } from 'react';

interface MetricCardProps {
  label: string;
  value: ReactNode;
  detail?: ReactNode;
  tone?: 'neutral' | 'good' | 'bad' | 'warn';
}

const TONE_COLOR: Record<string, string> = {
  good:    'var(--green)',
  bad:     'var(--red)',
  warn:    'var(--amber)',
  neutral: 'var(--accent)',
};

export function MetricCard({ label, value, detail, tone = 'neutral' }: MetricCardProps) {
  const bar = TONE_COLOR[tone];
  return (
    <section className={`metric-card tone-${tone}`}>
      <span className="metric-card-bar" style={{ background: bar }} />
      <span className="metric-label">{label}</span>
      <strong className="metric-value">{value}</strong>
      {detail ? <span className="metric-detail">{detail}</span> : null}
    </section>
  );
}
