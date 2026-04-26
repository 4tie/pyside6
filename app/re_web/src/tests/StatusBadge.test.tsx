// Feature: web-ui-redesign, Property 6: StatusBadge Tone Mapping
import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { render } from '@testing-library/react';
import { StatusBadge } from '../components/StatusBadge';

const EXPECTED_TONES: Record<string, string> = {
  idle:     'neutral',
  running:  'warn',
  complete: 'good',
  error:    'bad',
};

/**
 * Validates: Requirements 9.2
 *
 * Property 6: StatusBadge Tone Mapping
 * For any status in {idle, running, complete, error}, StatusBadge renders
 * tone-{expected} where expected is neutral, warn, good, bad respectively.
 * The mapping must be injective — no two canonical statuses share a tone.
 */
describe('Property 6: StatusBadge Tone Mapping', () => {
  it('renders the correct tone class for each canonical status', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('idle', 'running', 'complete', 'error'),
        (status) => {
          const { container } = render(<StatusBadge status={status} />);
          const span = container.querySelector('span');
          const expectedTone = EXPECTED_TONES[status];
          expect(span).not.toBeNull();
          expect(span!.className).toContain(`tone-${expectedTone}`);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('tone mapping is injective — no two canonical statuses share a tone', () => {
    const tones = Object.values(EXPECTED_TONES);
    const uniqueTones = new Set(tones);
    expect(uniqueTones.size).toBe(tones.length);
  });
});

describe('StatusBadge unit tests', () => {
  it.each([
    ['idle',     'tone-neutral'],
    ['running',  'tone-warn'],
    ['complete', 'tone-good'],
    ['error',    'tone-bad'],
  ])('status "%s" renders class "%s"', (status, expectedClass) => {
    const { container } = render(<StatusBadge status={status} />);
    expect(container.querySelector('span')!.className).toContain(expectedClass);
  });
});
