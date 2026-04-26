import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { AppShell } from '../components/AppShell';

// MobileNav uses lucide-react icons and internal state — mock it to keep tests focused on AppShell sidebar
vi.mock('../components/MobileNav', () => ({
  MobileNav: () => null,
}));

describe('AppShell unit tests', () => {
  it('active link has aria-current="page" and no other <a> does', () => {
    const activePath = '/app/backtest';
    const { container } = render(
      <AppShell
        currentPath={activePath}
        theme="dark"
        onNavigate={vi.fn()}
        onToggleTheme={vi.fn()}
      >
        <div />
      </AppShell>
    );

    const links = Array.from(container.querySelectorAll('nav.nav-list a'));
    expect(links.length).toBeGreaterThan(0);

    const activeLinks = links.filter((a) => a.getAttribute('aria-current') === 'page');
    const inactiveLinks = links.filter((a) => a.getAttribute('aria-current') !== 'page');

    // Exactly one active link
    expect(activeLinks).toHaveLength(1);
    expect(activeLinks[0].getAttribute('href')).toBe(activePath);

    // All other links must NOT have aria-current
    inactiveLinks.forEach((a) => {
      expect(a.getAttribute('aria-current')).toBeNull();
    });
  });

  it('root path /app is active when currentPath is /app', () => {
    const { container } = render(
      <AppShell
        currentPath="/app"
        theme="light"
        onNavigate={vi.fn()}
        onToggleTheme={vi.fn()}
      >
        <div />
      </AppShell>
    );

    const links = Array.from(container.querySelectorAll('nav.nav-list a'));
    const activeLinks = links.filter((a) => a.getAttribute('aria-current') === 'page');
    expect(activeLinks).toHaveLength(1);
    expect(activeLinks[0].getAttribute('href')).toBe('/app');
  });
});
