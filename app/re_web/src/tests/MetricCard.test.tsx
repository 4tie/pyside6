// Feature: web-ui-redesign, Property 3: MetricCard Tone Rendering Invariant
import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { render } from '@testing-library/react';
import { MetricCard } from '../components/MetricCard';

const TONE_COLORS: Record<string, string> = {
  good:    'var(--green)',
  bad:     'var(--red)',
  warn:    'var(--amber)',
  neutral: 'var(--accent)',
};

/**
 * Validates: Requirements 4.1, 4.3
 *
 * Property 3: MetricCard Tone Rendering Invariant
 * For any tone in {good, bad, warn, neutral}, MetricCard renders a
 * .metric-card-bar with a non-empty background style and a .metric-value element.
 */
describe('Property 3: MetricCard Tone Rendering Invariant', () => {
  it('renders .metric-card-bar with non-empty background and .metric-value for every tone', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('good', 'bad', 'warn', 'neutral'),
        (tone) => {
          const { container } = render(
            <MetricCard label="Test" value="42" tone={tone as 'good' | 'bad' | 'warn' | 'neutral'} />
          );

          const bar = container.querySelector('.metric-card-bar') as HTMLElement | null;
          expect(bar).not.toBeNull();
          expect(bar!.style.background).toBeTruthy();
          expect(bar!.style.background).toBe(TONE_COLORS[tone]);

          const valueEl = container.querySelector('.metric-value');
          expect(valueEl).not.toBeNull();
        }
      ),
      { numRuns: 100 }
    );
  });
});

describe('MetricCard unit tests', () => {
  it.each([
    ['good',    'var(--green)'],
    ['bad',     'var(--red)'],
    ['warn',    'var(--amber)'],
    ['neutral', 'var(--accent)'],
  ] as const)('tone "%s" renders bar with background "%s"', (tone, expectedColor) => {
    const { container } = render(
      <MetricCard label="Label" value="0" tone={tone} />
    );

    const bar = container.querySelector('.metric-card-bar') as HTMLElement;
    expect(bar).not.toBeNull();
    expect(bar.style.background).toBe(expectedColor);

    expect(container.querySelector('.metric-value')).not.toBeNull();
  });

  it('defaults to neutral tone when no tone prop is provided', () => {
    const { container } = render(<MetricCard label="Label" value="0" />);
    const bar = container.querySelector('.metric-card-bar') as HTMLElement;
    expect(bar.style.background).toBe('var(--accent)');
  });
});
