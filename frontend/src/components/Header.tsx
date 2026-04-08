/**
 * Header Component
 * Top navigation bar with breadcrumbs, title, and mobile menu toggle
 */

import { ChevronRight, Command, Menu, Search, Wifi, WifiOff } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/auth';
import { getWorkspaceBreadcrumbs } from '../navigation/workspaceNav';

interface HeaderProps {
  onMenuToggle: () => void;
  onOpenCommandPalette: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onMenuToggle, onOpenCommandPalette }) => {
  const location = useLocation();
  const user = useAuthStore((state) => state.user);
  const environmentLabel = import.meta.env.DEV ? 'Development' : 'Production';
  const environmentColor = import.meta.env.DEV ? 'text-yellow-400' : 'text-green-400';
  const [now, setNow] = useState(() => new Date());
  const [isOnline, setIsOnline] = useState(() => window.navigator.onLine);

  useEffect(() => {
    const timerId = window.setInterval(() => setNow(new Date()), 1000);
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.clearInterval(timerId);
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const breadcrumbs = getWorkspaceBreadcrumbs(location.pathname);
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
          <button
            type="button"
            onClick={onOpenCommandPalette}
            className="hidden md:inline-flex items-center gap-3 rounded-2xl border border-slate-700/70 bg-slate-900/65 px-4 py-2 text-sm text-slate-300 transition hover:border-slate-600 hover:text-white"
          >
            <Search className="h-4 w-4 text-slate-500" />
            <span className="hidden lg:inline">Jump anywhere</span>
            <span className="inline-flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-950 px-2 py-1 text-[10px] uppercase tracking-[0.16em] text-slate-500">
              <Command className="h-3 w-3" />
              K
            </span>
          </button>

          <div className="hidden xl:flex items-center gap-3">
            <div className="rounded-full border border-slate-700/70 bg-slate-900/65 px-3 py-2 text-right">
              <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Environment</p>
              <p className={`text-sm font-medium ${environmentColor}`}>{environmentLabel}</p>
            </div>
            <div className="rounded-full border border-slate-700/70 bg-slate-900/65 px-3 py-2 text-right">
              <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Network</p>
              <p className={`inline-flex items-center gap-1 text-sm font-medium ${isOnline ? 'text-cyan-300' : 'text-amber-300'}`}>
                {isOnline ? <Wifi className="h-4 w-4" /> : <WifiOff className="h-4 w-4" />}
                {isOnline ? 'Online' : 'Offline'}
              </p>
            </div>
            <div className="rounded-full border border-slate-700/70 bg-slate-900/65 px-3 py-2 text-right">
              <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Clock</p>
              <p className="text-sm font-medium text-cyan-300">
                {now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </p>
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
