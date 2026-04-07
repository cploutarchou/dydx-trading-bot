/**
 * Header Component
 * Top navigation bar with breadcrumbs, title, and mobile menu toggle
 */

import { ChevronRight, Menu } from 'lucide-react';
import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/auth';

interface HeaderProps {
  onMenuToggle: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onMenuToggle }) => {
  const location = useLocation();
  const user = useAuthStore((state) => state.user);
  const environmentLabel = import.meta.env.DEV ? '🟡 Development' : '🟢 Production';
  const environmentColor = import.meta.env.DEV ? 'text-yellow-400' : 'text-green-400';

  // Map routes to breadcrumb labels
  const getBreadcrumbs = () => {
    const paths = location.pathname.split('/').filter(Boolean);
    const breadcrumbs = [{ label: 'Home', path: '/dashboard' }];

    if (paths.includes('settings')) {
      breadcrumbs.push({ label: 'Settings', path: '/settings' });
    } else if (paths.includes('backtests') || paths.includes('backtest')) {
      const backtestIndex = paths.findIndex(
        (segment) => segment === 'backtests' || segment === 'backtest'
      );
      const runId = backtestIndex >= 0 ? paths[backtestIndex + 1] : undefined;

      breadcrumbs.push({ label: 'Backtests', path: '/backtests' });

      if (runId && runId !== 'compare') {
        breadcrumbs.push({ label: `Run ${runId}`, path: `/backtest/${runId}` });
      } else if (runId === 'compare') {
        breadcrumbs.push({ label: 'Compare Backtests', path: '/backtests/compare' });
      }
    } else if (paths.includes('strategies')) {
      breadcrumbs.push({ label: 'Strategies', path: '/strategies' });
      if (paths.includes('new')) {
        breadcrumbs.push({ label: 'New Strategy', path: '/strategies/new' });
      } else if (paths.includes('edit')) {
        const strategyId = paths[paths.indexOf('edit') - 1];
        breadcrumbs.push({
          label: `Edit Strategy ${strategyId}`,
          path: `/strategies/${strategyId}/edit`,
        });
      }
    }

    return breadcrumbs;
  };

  const breadcrumbs = getBreadcrumbs();
  const pageTitle = breadcrumbs[breadcrumbs.length - 1]?.label || 'Dashboard';

  return (
    <header className="premium-topbar sticky top-0 z-40">
      <div className="flex min-h-20 items-center justify-between gap-4 px-4 lg:px-6">
        {/* Left: Menu Toggle + Breadcrumbs */}
        <div className="flex items-center gap-4">
          <button
            onClick={onMenuToggle}
            className="lg:hidden rounded-2xl border border-slate-700/80 bg-slate-900/70 p-2.5 text-gray-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <Menu className="w-6 h-6" />
          </button>

          {/* Breadcrumbs */}
          <nav className="hidden md:flex items-center gap-2 text-sm">
            {breadcrumbs.map((crumb, index) => (
              <React.Fragment key={`breadcrumb-${index}-${crumb.path}`}>
                {index > 0 && <ChevronRight className="w-4 h-4 text-gray-500" />}
                {index === breadcrumbs.length - 1 ? (
                  <span className="text-white font-medium">{crumb.label}</span>
                ) : (
                  <Link
                    to={crumb.path}
                    className="text-gray-400 hover:text-gray-300 transition-colors"
                  >
                    {crumb.label}
                  </Link>
                )}
              </React.Fragment>
            ))}
          </nav>
        </div>

        {/* Right: Page Title (mobile) */}
        <div className="md:hidden text-white font-semibold text-sm">{pageTitle}</div>

        {/* Right: Status/Info Area (can be extended) */}
        <div className="flex items-center gap-4">
          <div className="hidden lg:flex items-center gap-3">
            <div className="rounded-full border border-slate-700/70 bg-slate-900/65 px-3 py-2 text-right">
              <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Environment</p>
              <p className={`text-sm font-medium ${environmentColor}`}>{environmentLabel}</p>
            </div>
            <div className="rounded-full border border-slate-700/70 bg-slate-900/65 px-4 py-2">
              <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Operator</p>
              <p className="text-sm font-medium text-white">{user?.full_name || user?.username || 'Trader'}</p>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
