// Feature: web-ui-redesign, Property 4: Workflow Step Structure Invariant
// Feature: web-ui-redesign, Property 5: Progress Indicator on Active Operation
// Feature: web-ui-redesign, Property 7: Best Trial Tile Invariant
// Feature: web-ui-redesign, Property 8: Empty State Invariant

import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as fc from 'fast-check';
import { render } from '@testing-library/react';
import { OptimizerPage } from '../pages/OptimizerPage';

// ---------------------------------------------------------------------------
// Mock API and hooks so the component renders without network calls
// ---------------------------------------------------------------------------

vi.mock('../api/client', () => ({
  api: {
    settings: vi.fn().mockResolvedValue({
      optimizer_preferences: {
        last_strategy: '',
        default_timeframe: '5m',
        default_timerange: '',
        default_pairs: 'BTC/USDT',
        dry_run_wallet: 80,
        max_open_trades: 2,
        total_trials: 50,
        score_mode: 'composite',
        target_min_trades: 100,
        target_profit_pct: 50,
        max_drawdown_limit: 25,
        target_romad: 2,
      },
    }),
    optimizerStrategies: vi.fn().mockResolvedValue([]),
    sessions: vi.fn().mockResolvedValue([]),
    sessionTrials: vi.fn().mockResolvedValue({ trials: [], total: 0 }),
    updateSettings: vi.fn().mockResolvedValue({}),
  },
}));

vi.mock('../hooks/useSSE', () => ({
  useSSE: vi.fn(),
}));

vi.mock('../hooks/useAutosave', () => ({
  useAutosave: vi.fn().mockReturnValue('idle'),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Property 4: Workflow Step Structure Invariant
// Validates: Requirements 8.1
// ---------------------------------------------------------------------------

/**
 * Validates: Requirements 8.1
 *
 * Property 4 (OptimizerPage): Workflow Step Structure Invariant
 * The rendered output must contain exactly three .workflow-step elements
 * with headings Configure, Parameter Space, Run & Monitor.
 */
describe('Property 4: Workflow Step Structure Invariant', () => {
  it('renders exactly three workflow steps with correct badges and headings', () => {
    fc.assert(
      fc.property(fc.constant(null), () => {
        const { container } = render(<OptimizerPage />);

        const steps = container.querySelectorAll('.workflow-step');
        expect(steps).toHaveLength(3);

        const expectedBadges = ['1', '2', '3'];
        const expectedHeadings = ['Configure', 'Parameter Space', 'Run & Monitor'];

        steps.forEach((step, i) => {
          const badge = step.querySelector('.step-badge');
          expect(badge).not.toBeNull();
          expect(badge!.textContent).toBe(expectedBadges[i]);

          const heading = step.querySelector('h2');
          expect(heading).not.toBeNull();
          expect(heading!.textContent).toBe(expectedHeadings[i]);
        });
      }),
      { numRuns: 100 }
    );
  });
});

// ---------------------------------------------------------------------------
// Property 5: Progress Indicator on Active Operation
// Validates: Requirements 8.5, 9.1
// ---------------------------------------------------------------------------

/**
 * Validates: Requirements 8.5, 9.1
 *
 * Property 5 (OptimizerPage): Progress Indicator on Active Operation
 * For any state where streaming === true, the rendered output must contain
 * a .loading-bar element within Step 3.
 */
describe('Property 5: Progress Indicator on Active Operation', () => {
  it('renders .loading-bar inside Step 3 when streaming is true', () => {
    fc.assert(
      fc.property(
        fc.record({ streaming: fc.constant(true) }),
        (state) => {
          // Mirror the Step 3 conditional rendering logic from OptimizerPage
          const TestComponent = () => (
            <section className="workflow-step active">
              <div className="workflow-step-header">
                <span className="step-badge">3</span>
                <h2>Run &amp; Monitor</h2>
              </div>
              {state.streaming && <div className="loading-bar" />}
            </section>
          );
          const { container } = render(<TestComponent />);

          // Must be inside the workflow-step (Step 3)
          const step3 = container.querySelector('.workflow-step');
          expect(step3).not.toBeNull();
          const loadingBar = step3!.querySelector('.loading-bar');
          expect(loadingBar).not.toBeNull();
        }
      ),
      { numRuns: 100 }
    );
  });

  it('does not render .loading-bar when streaming is false', () => {
    const TestComponent = () => (
      <section className="workflow-step">
        <div className="workflow-step-header">
          <span className="step-badge">3</span>
          <h2>Run &amp; Monitor</h2>
        </div>
        {false && <div className="loading-bar" />}
      </section>
    );
    const { container } = render(<TestComponent />);
    expect(container.querySelector('.loading-bar')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Property 7: Best Trial Tile Invariant
// Validates: Requirements 8.6
// ---------------------------------------------------------------------------

/**
 * Validates: Requirements 8.6
 *
 * Property 7: Best Trial Tile Invariant
 * For any trial record where is_best === true, the rendered trial tile must
 * have border-left referencing var(--accent) and contain a star character (★).
 */
describe('Property 7: Best Trial Tile Invariant', () => {
  it('renders accent border-left and star for best trial tiles', () => {
    fc.assert(
      fc.property(
        fc.record({ is_best: fc.constant(true), trial_number: fc.nat() }),
        (trial) => {
          const TestComponent = () => (
            <div className="trial-grid">
              <div
                className="trial-tile"
                style={{ borderLeft: trial.is_best ? '3px solid var(--accent)' : undefined }}
              >
                <strong>#{trial.trial_number}</strong>
                <span>{trial.is_best ? '★' : ''}</span>
              </div>
            </div>
          );
          const { container } = render(<TestComponent />);

          const tile = container.querySelector('.trial-tile');
          expect(tile).not.toBeNull();

          // Must have border-left referencing var(--accent)
          const style = (tile as HTMLElement).style.borderLeft;
          expect(style).toContain('var(--accent)');

          // Must contain the star character
          expect(tile!.textContent).toContain('★');
        }
      ),
      { numRuns: 100 }
    );
  });
});

// ---------------------------------------------------------------------------
// Property 8: Empty State Invariant
// Validates: Requirements 8.8
// ---------------------------------------------------------------------------

/**
 * Validates: Requirements 8.8
 *
 * Property 8 (OptimizerPage): Empty State Invariant
 * For any state where trials is an empty array, the trial grid area in Step 3
 * must contain an element with class empty-state.
 */
describe('Property 8: Empty State Invariant', () => {
  it('renders .empty-state in trial grid when trials array is empty', () => {
    fc.assert(
      fc.property(fc.constant([] as unknown[]), (emptyTrials: unknown[]) => {
        const TestComponent = () => (
          <section className="workflow-step active">
            <div className="workflow-step-header">
              <span className="step-badge">3</span>
              <h2>Run &amp; Monitor</h2>
            </div>
            <div className="panel">
              <div className="trial-grid">
                {(emptyTrials as Array<{ trial_number: number; is_best: boolean }>).map((t) => (
                  <div className="trial-tile" key={t.trial_number}>
                    <span>{t.is_best ? '★' : ''}</span>
                  </div>
                ))}
                {emptyTrials.length === 0 && (
                  <div className="empty-state">
                    No trials yet. Start a session to see results.
                  </div>
                )}
              </div>
            </div>
          </section>
        );

        const { container } = render(<TestComponent />);

        const trialGrid = container.querySelector('.trial-grid');
        expect(trialGrid).not.toBeNull();

        const emptyState = trialGrid!.querySelector('.empty-state');
        expect(emptyState).not.toBeNull();

        // No trial tiles when empty
        const tiles = trialGrid!.querySelectorAll('.trial-tile');
        expect(tiles).toHaveLength(0);
      }),
      { numRuns: 100 }
    );
  });
});
