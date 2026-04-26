import { MoreHorizontal } from 'lucide-react';
import { useState } from 'react';
import type { RouteItem } from './AppShell';

interface MobileNavProps {
  routes: RouteItem[];
  currentPath: string;
  onNavigate: (path: string) => void;
}

const PRIMARY_COUNT = 4;

export function MobileNav({ routes, currentPath, onNavigate }: MobileNavProps) {
  const [moreOpen, setMoreOpen] = useState(false);

  const primaryRoutes = routes.slice(0, PRIMARY_COUNT);
  const moreRoutes = routes.slice(PRIMARY_COUNT);
  const moreIsActive = moreRoutes.some(
    (r) => currentPath === r.path || (r.path !== '/app' && currentPath.startsWith(r.path))
  );

  return (
    <>
      {moreOpen && (
        <>
          <div className="mobile-more-backdrop" onClick={() => setMoreOpen(false)} />
          <div className="mobile-more-sheet">
            {moreRoutes.map((route) => {
              const active =
                currentPath === route.path ||
                (route.path !== '/app' && currentPath.startsWith(route.path));
              return (
                <button
                  key={route.path}
                  type="button"
                  className={active ? 'mobile-nav-item active' : 'mobile-nav-item'}
                  onClick={() => {
                    onNavigate(route.path);
                    setMoreOpen(false);
                  }}
                  aria-label={route.label}
                  aria-current={active ? 'page' : undefined}
                >
                  {route.icon}
                  <span>{route.label}</span>
                </button>
              );
            })}
          </div>
        </>
      )}
      <nav className="mobile-nav" aria-label="Mobile navigation">
        {primaryRoutes.map((route) => {
          const active =
            currentPath === route.path ||
            (route.path !== '/app' && currentPath.startsWith(route.path));
          return (
            <button
              key={route.path}
              type="button"
              className={active ? 'mobile-nav-item active' : 'mobile-nav-item'}
              onClick={() => onNavigate(route.path)}
              aria-label={route.label}
              aria-current={active ? 'page' : undefined}
            >
              {route.icon}
              <span>{route.label}</span>
            </button>
          );
        })}
        <button
          type="button"
          className={moreIsActive ? 'mobile-nav-item active' : 'mobile-nav-item'}
          onClick={() => setMoreOpen((o) => !o)}
          aria-label="More"
        >
          <MoreHorizontal size={20} />
          <span>More</span>
        </button>
      </nav>
    </>
  );
}
