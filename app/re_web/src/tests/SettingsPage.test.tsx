// Feature: shared-inputs
// Validates: Requirements 8.1, 8.2

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { SettingsPage } from '../pages/SettingsPage';

vi.mock('../api/client', () => ({
  api: {
    settings: vi.fn().mockResolvedValue({
      user_data_path: '/data',
      venv_path: '/venv',
      python_executable: '/venv/bin/python',
      freqtrade_executable: '/venv/bin/freqtrade',
      use_module_execution: true,
      backtest_preferences: {},
      optimize_preferences: {},
      download_preferences: {},
      optimizer_preferences: {},
      shared_inputs: {
        default_timeframe: '5m',
        default_timerange: '',
        last_timerange_preset: '30d',
        default_pairs: '',
        dry_run_wallet: 80,
        max_open_trades: 2,
      },
    }),
    updateSettings: vi.fn().mockResolvedValue({}),
  },
}));

vi.mock('../hooks/useAutosave', () => ({
  useAutosave: vi.fn().mockReturnValue('idle'),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Requirement 8.1: SettingsPage must NOT render PrefsSection for the three
// removed preference sections.
// Requirement 8.2: SettingsPage must still render the Paths & Executables section.
// ---------------------------------------------------------------------------

describe('SettingsPage cleanup (Requirements 8.1, 8.2)', () => {
  it('does not render PrefsSection for backtest_preferences', () => {
    const { queryByText } = render(<SettingsPage />);
    expect(queryByText('Backtest Preferences')).toBeNull();
  });

  it('does not render PrefsSection for optimizer_preferences', () => {
    const { queryByText } = render(<SettingsPage />);
    expect(queryByText('Optimizer Preferences')).toBeNull();
  });

  it('does not render PrefsSection for download_preferences', () => {
    const { queryByText } = render(<SettingsPage />);
    expect(queryByText('Download Preferences')).toBeNull();
  });

  it('still renders the Paths & Executables section', () => {
    const { getByText } = render(<SettingsPage />);
    expect(getByText('Paths & Executables')).toBeTruthy();
  });
});
