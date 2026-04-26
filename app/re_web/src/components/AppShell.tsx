import {
  Activity,
  BarChart3,
  Download,
  GitCompare,
  LayoutDashboard,
  Moon,
  Settings,
  SlidersHorizontal,
  Sun
} from 'lucide-react';
import type { ReactNode } from 'react';
import type { ThemeMode } from '../types/api';
import { MobileNav } from './MobileNav';

export interface RouteItem {
  path: string;
  label: string;
  icon: ReactNode;
}

const routes: RouteItem[] = [
  { path: '/app', label: 'Dashboard', icon: <LayoutDashboard size={17} /> },
  { path: '/app/backtest', label: 'Backtest', icon: <Activity size={17} /> },
  { path: '/app/optimizer', label: 'Optimizer', icon: <SlidersHorizontal size={17} /> },
  { path: '/app/comparison', label: 'Comparison', icon: <GitCompare size={17} /> },
  { path: '/app/download', label: 'Download', icon: <Download size={17} /> },
  { path: '/app/settings', label: 'Settings', icon: <Settings size={17} /> }
];

interface AppShellProps {
  children: ReactNode;
  currentPath: string;
  theme: ThemeMode;
  onNavigate: (path: string) => void;
  onToggleTheme: () => void;
}

export function AppShell({ children, currentPath, theme, onNavigate, onToggleTheme }: AppShellProps) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <BarChart3 size={22} />
          <div>
            <strong>Freqtrade Control</strong>
            <span>Backtests and optimization</span>
          </div>
        </div>
        <nav className="nav-list" aria-label="Main navigation">
          {routes.map((route) => {
            const active = currentPath === route.path || (route.path !== '/app' && currentPath.startsWith(route.path));
            return (
              <a
                key={route.path}
                className={active ? 'nav-link active' : 'nav-link'}
                href={route.path}
                aria-current={active ? 'page' : undefined}
                onClick={(event) => {
                  event.preventDefault();
                  onNavigate(route.path);
                }}
              >
                {route.icon}
                <span>{route.label}</span>
              </a>
            );
          })}
        </nav>
        <button className="icon-button theme-button" type="button" onClick={onToggleTheme} aria-label="Toggle theme">
          {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
        </button>
      </aside>
      <main className="content">{children}</main>
      <MobileNav routes={routes} currentPath={currentPath} onNavigate={onNavigate} />
    </div>
  );
}
