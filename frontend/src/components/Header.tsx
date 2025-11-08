/**
 * Header Component
 * Top navigation bar with breadcrumbs, title, and mobile menu toggle
 */

import { ChevronRight, Menu } from 'lucide-react';
import React from 'react';
import { useLocation } from 'react-router-dom';

interface HeaderProps {
  onMenuToggle: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onMenuToggle }) => {
  const location = useLocation();

  // Map routes to breadcrumb labels
  const getBreadcrumbs = () => {
    const paths = location.pathname.split('/').filter(Boolean);
    const breadcrumbs = [{ label: 'Home', path: '/dashboard' }];

    if (paths.includes('settings')) {
      breadcrumbs.push({ label: 'Settings', path: '/settings' });
    } else if (paths.includes('backtest')) {
      // Don't add duplicate dashboard - just show the specific backtest
      const runId = paths[paths.indexOf('backtest') + 1];
      if (runId) {
        breadcrumbs.push({ label: 'Backtests', path: '/backtest/' });
        breadcrumbs.push({ label: `Run ${runId}`, path: `/backtest/${runId}` });
      }
    } else if (paths.includes('strategies')) {
      breadcrumbs.push({ label: 'Strategies', path: '/strategies' });
      if (paths.includes('new')) {
        breadcrumbs.push({ label: 'New Strategy', path: '/strategies/new' });
      } else if (paths.includes('edit')) {
        const strategyId = paths[paths.indexOf('edit') - 1];
        breadcrumbs.push({ label: `Edit Strategy ${strategyId}`, path: `/strategies/${strategyId}/edit` });
      }
    }

    return breadcrumbs;
  };

  const breadcrumbs = getBreadcrumbs();
  const pageTitle = breadcrumbs[breadcrumbs.length - 1]?.label || 'Dashboard';

  return (
    <header className="bg-slate-800 border-b border-slate-700 sticky top-0 z-40">
      <div className="flex items-center justify-between h-16 px-4 lg:px-6">
        {/* Left: Menu Toggle + Breadcrumbs */}
        <div className="flex items-center gap-4">
          <button
            onClick={onMenuToggle}
            className="lg:hidden p-2 text-gray-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
          >
            <Menu className="w-6 h-6" />
          </button>

          {/* Breadcrumbs */}
          <nav className="hidden md:flex items-center gap-2 text-sm">
            {breadcrumbs.map((crumb, index) => (
              <React.Fragment key={`breadcrumb-${index}-${crumb.path}`}>
                {index > 0 && <ChevronRight className="w-4 h-4 text-gray-500" />}
                <span
                  className={
                    index === breadcrumbs.length - 1
                      ? 'text-white font-medium'
                      : 'text-gray-400 hover:text-gray-300 cursor-pointer'
                  }
                >
                  {crumb.label}
                </span>
              </React.Fragment>
            ))}
          </nav>
        </div>

        {/* Right: Page Title (mobile) */}
        <div className="md:hidden text-white font-semibold text-sm">{pageTitle}</div>

        {/* Right: Status/Info Area (can be extended) */}
        <div className="flex items-center gap-4">
          <div className="text-right hidden lg:block">
            <p className="text-xs text-gray-400">Environment</p>
            <p className="text-sm font-medium text-green-400">🟢 Production</p>
          </div>
        </div>
      </div>
    </header>
  );
};
