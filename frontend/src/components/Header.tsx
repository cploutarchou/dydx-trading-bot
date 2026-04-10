import {
  ChevronRight,
  Command,
  Menu,
  Search,
  ShieldCheck,
  Wifi,
  WifiOff,
} from 'lucide-react';
import React, { useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { getWorkspaceBreadcrumbs, workspaceNavItems } from '../navigation/workspaceNav';
import { useAuthStore } from '../store/auth';

interface HeaderProps {
  onMenuToggle: () => void;
  onOpenCommandPalette: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onMenuToggle, onOpenCommandPalette }) => {
  const location = useLocation();
  const user = useAuthStore((state) => state.user);
  const environmentLabel = import.meta.env.DEV ? 'Development' : 'Production';
  const environmentTone = import.meta.env.DEV ? 'text-amber-300' : 'text-emerald-300';
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
  const routeMeta = useMemo(
    () =>
      workspaceNavItems.find((item) =>
        item.exact ? item.path === location.pathname : location.pathname.startsWith(item.path)
      ),
    [location.pathname]
  );

  return (
    <header className="premium-topbar sticky top-0 z-40">
      <div className="flex min-h-24 items-center justify-between gap-4 px-4 py-3 lg:px-6">
        <div className="flex min-w-0 items-center gap-4">
          <button
            type="button"
            onClick={onMenuToggle}
            className="rounded-2xl border border-slate-700/80 bg-slate-900/70 p-2.5 text-slate-400 transition-colors hover:bg-slate-800 hover:text-white lg:hidden"
            aria-label="Toggle navigation"
          >
            <Menu className="h-6 w-6" />
          </button>

          <div className="min-w-0">
            <nav className="hidden items-center gap-2 text-sm md:flex">
              {breadcrumbs.map((crumb, index) => (
                <React.Fragment key={`${crumb.path}-${index}`}>
                  {index > 0 && <ChevronRight className="h-4 w-4 text-slate-600" />}
                  {index === breadcrumbs.length - 1 ? (
                    <span className="font-medium text-white">{crumb.label}</span>
                  ) : (
                    <Link
                      to={crumb.path}
                      className="text-slate-400 transition hover:text-slate-200"
                    >
                      {crumb.label}
                    </Link>
                  )}
                </React.Fragment>
              ))}
            </nav>

            <div className="mt-0 md:mt-2">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-lg font-semibold text-white sm:text-xl">{pageTitle}</h1>
                <span className="workspace-chip border-cyan-500/20 text-cyan-200">
                  <ShieldCheck className="h-3.5 w-3.5" />
                  Operator surface
                </span>
              </div>
              <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-500 sm:text-sm">
                {routeMeta?.description ||
                  'Navigate across live workflows with grouped actions, stable status chips, and faster route switching.'}
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onOpenCommandPalette}
            className="inline-flex items-center gap-3 rounded-2xl border border-slate-700/70 bg-slate-900/65 px-3 py-2.5 text-sm text-slate-300 transition hover:border-slate-600 hover:text-white sm:px-4"
          >
            <Search className="h-4 w-4 text-slate-500" />
            <span className="hidden lg:inline">Jump anywhere</span>
            <span className="inline-flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-950 px-2 py-1 text-[10px] uppercase tracking-[0.16em] text-slate-500">
              <Command className="h-3 w-3" />
              K
            </span>
          </button>

          <div className="hidden items-center gap-2 xl:flex">
            <div className="workspace-card px-4 py-3">
              <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Environment</p>
              <p className={`mt-1 text-sm font-medium ${environmentTone}`}>{environmentLabel}</p>
            </div>
            <div className="workspace-card px-4 py-3">
              <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Network</p>
              <p
                className={`mt-1 inline-flex items-center gap-1 text-sm font-medium ${
                  isOnline ? 'text-cyan-300' : 'text-amber-300'
                }`}
              >
                {isOnline ? <Wifi className="h-4 w-4" /> : <WifiOff className="h-4 w-4" />}
                {isOnline ? 'Online' : 'Offline'}
              </p>
            </div>
            <div className="workspace-card px-4 py-3">
              <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Local time</p>
              <p className="mt-1 text-sm font-medium text-cyan-300">
                {now.toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit',
                })}
              </p>
            </div>
            <div className="workspace-card px-4 py-3">
              <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Operator</p>
              <p className="mt-1 text-sm font-medium text-white">
                {user?.full_name || user?.username || 'Trader'}
              </p>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
