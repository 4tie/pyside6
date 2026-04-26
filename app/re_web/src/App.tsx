import { useCallback, useEffect, useMemo, useState } from 'react';
import { AppShell } from './components/AppShell';
import { useTheme } from './hooks/useTheme';
import { BacktestPage } from './pages/BacktestPage';
import { ComparisonPage } from './pages/ComparisonPage';
import { DashboardPage } from './pages/DashboardPage';
import { DownloadPage } from './pages/DownloadPage';
import { OptimizerPage } from './pages/OptimizerPage';
import { RunDetailPage } from './pages/RunDetailPage';
import { SettingsPage } from './pages/SettingsPage';
import type { RunResponse } from './types/api';

function normalizePath(pathname: string): string {
  if (pathname === '/' || pathname === '/app/') return '/app';
  return pathname.replace(/\/$/, '');
}

export function App() {
  const { theme, toggleTheme } = useTheme();
  const [path, setPath] = useState(normalizePath(window.location.pathname));

  useEffect(() => {
    const handler = () => setPath(normalizePath(window.location.pathname));
    window.addEventListener('popstate', handler);
    return () => window.removeEventListener('popstate', handler);
  }, []);

  const navigate = useCallback((nextPath: string) => {
    window.history.pushState({}, '', nextPath);
    setPath(normalizePath(nextPath));
  }, []);

  const onOpenRun = useCallback(
    (run: RunResponse) => {
      navigate(`/app/run/${encodeURIComponent(run.strategy)}/${encodeURIComponent(run.run_id)}`);
    },
    [navigate]
  );

  const content = useMemo(() => {
    if (path === '/app' || path === '/') return <DashboardPage onOpenRun={onOpenRun} />;
    if (path.startsWith('/app/backtest')) return <BacktestPage />;
    if (path.startsWith('/app/optimizer')) return <OptimizerPage />;
    if (path.startsWith('/app/comparison')) return <ComparisonPage onOpenRun={onOpenRun} />;
    if (path.startsWith('/app/download')) return <DownloadPage />;
    if (path.startsWith('/app/settings')) return <SettingsPage />;
    if (path.startsWith('/app/run')) {
      const parts = path.split('/').map(decodeURIComponent);
      const runId = parts[4] || parts[3];
      return <RunDetailPage runId={runId} onOpenRun={onOpenRun} />;
    }
    return <DashboardPage onOpenRun={onOpenRun} />;
  }, [path, onOpenRun]);

  return (
    <AppShell currentPath={path} theme={theme} onNavigate={navigate} onToggleTheme={toggleTheme}>
      {content}
    </AppShell>
  );
}
