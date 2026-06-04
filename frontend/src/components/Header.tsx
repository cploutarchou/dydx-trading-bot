import {
    ChevronRight,
    Command,
    Languages,
    Menu,
    Search,
    ShieldCheck,
    Wifi,
    WifiOff,
} from 'lucide-react';
import React, { useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { getCurrentPortalType } from '../app/portal';
import { clientPortalHref } from '../app/portalLinks';
import { BACKOFFICE_ROLES, getUserWorkspaceRole, roleMatches } from '../auth/roles';
import { useI18n } from '../i18n/useI18n';
import { getWorkspaceBreadcrumbs, getWorkspaceNavItems } from '../navigation/workspaceNav';
import { useAuthStore } from '../store/auth';
import { useUIPreferencesStore } from '../store/uiPreferences';
import { ThemeToggle } from './ThemeToggle';

interface HeaderProps {
  onMenuToggle: () => void;
  onOpenCommandPalette: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onMenuToggle, onOpenCommandPalette }) => {
  const location = useLocation();
  const user = useAuthStore((state) => state.user);
  const { language, locale, t, tr } = useI18n();
  const setLanguage = useUIPreferencesStore((state) => state.setLanguage);
  const controlCls =
    'border-slate-700/70 bg-slate-950/70 text-slate-300 hover:border-cyan-500/30 hover:text-white';
  const environmentLabel = import.meta.env.DEV
    ? t('Development', 'Ανάπτυξη')
    : t('Production', 'Παραγωγή');
  const environmentTone = import.meta.env.DEV ? 'text-amber-300' : 'text-emerald-300';
  const [now, setNow] = useState(() => new Date());
  const [isOnline, setIsOnline] = useState(() => window.navigator.onLine);
  const portal = getCurrentPortalType();
  const workspaceRole = getUserWorkspaceRole(user);
  const canOpenBackoffice = roleMatches(workspaceRole, BACKOFFICE_ROLES);
  const portalSwitch =
    canOpenBackoffice && portal === 'backoffice'
      ? {
          label: t('Client area', 'Περιοχή πελάτη'),
          href: clientPortalHref('/dashboard'),
        }
      : canOpenBackoffice
        ? {
            label: t('Admin', 'Διαχείριση'),
            href: '/admin',
          }
        : null;

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

  const breadcrumbs = getWorkspaceBreadcrumbs(location.pathname, portal);
  const pageTitle = tr(breadcrumbs[breadcrumbs.length - 1]?.label || 'Dashboard');
  const routeMeta = useMemo(
    () =>
      getWorkspaceNavItems(portal).find((item) =>
        item.exact ? item.path === location.pathname : location.pathname.startsWith(item.path)
      ),
    [location.pathname, portal]
  );

  return (
    <header className="premium-topbar sticky top-0 z-40">
      <div className="flex min-h-20 items-center justify-between gap-4 px-4 py-3 lg:px-6">
        <div className="flex min-w-0 items-center gap-4">
          <button
            type="button"
            onClick={onMenuToggle}
            className="rounded-lg border border-stone-700/80 bg-stone-950/70 p-2.5 text-stone-400 transition-colors hover:bg-stone-900 hover:text-white lg:hidden"
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
                    <span className="font-medium text-white">{tr(crumb.label)}</span>
                  ) : (
                    <Link
                      to={crumb.path}
                      className="text-slate-400 transition hover:text-slate-200"
                    >
                      {tr(crumb.label)}
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
                  {t('Execution desk', 'Πίνακας εκτέλεσης')}
                </span>
              </div>
              <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-500 sm:text-sm">
                {routeMeta?.description
                  ? tr(routeMeta.description)
                  : t(
                      'Move across execution workflows with route context, command access, and operational state in view.',
                      'Μετακινηθείτε σε ζωντανές ροές με ορατό context διαδρομής, πρόσβαση εντολών και λειτουργική κατάσταση.'
                    )}
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {portalSwitch && (
            <a
              href={portalSwitch.href}
              className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-semibold transition ${controlCls}`}
            >
              <ShieldCheck className="h-4 w-4" />
              <span className="hidden sm:inline">{portalSwitch.label}</span>
            </a>
          )}

          <button
            type="button"
            onClick={onOpenCommandPalette}
            className={`inline-flex items-center gap-3 rounded-lg border px-3 py-2.5 text-sm transition sm:px-4 ${controlCls}`}
          >
            <Search className="h-4 w-4 opacity-60" />
            <span className="hidden lg:inline">{t('Jump anywhere', 'Μεταπήδηση παντού')}</span>
            <span className="inline-flex items-center gap-1 rounded-lg border border-stone-700 bg-stone-950 px-2 py-1 text-[10px] uppercase text-stone-500">
              <Command className="h-3 w-3" />K
            </span>
          </button>

          <div className="hidden items-center gap-2 lg:flex">
            <ThemeToggle />
            <label
              className={`inline-flex items-center gap-2 rounded-lg border px-2 py-2 text-xs ${controlCls}`}
            >
              <Languages className="h-4 w-4" />
              <select
                value={language}
                onChange={(event) => setLanguage(event.target.value === 'el' ? 'el' : 'en')}
                className="bg-transparent text-xs text-stone-200 outline-none"
                aria-label="Language"
              >
                <option value="en" className="bg-slate-900 text-slate-100">
                  EN
                </option>
                <option value="el" className="bg-slate-900 text-slate-100">
                  EL
                </option>
              </select>
            </label>
          </div>

          <div className="hidden min-w-0 items-center gap-1.5 xl:flex">
            <div className="workspace-card px-3 py-2.5">
              <p className="text-[10px] uppercase text-slate-500">
                {t('Environment', 'Περιβάλλον')}
              </p>
              <p className={`mt-1 text-sm font-medium ${environmentTone}`}>{environmentLabel}</p>
            </div>
            <div className="workspace-card px-3 py-2.5">
              <p className="text-[10px] uppercase text-slate-500">{t('Network', 'Δίκτυο')}</p>
              <p
                className={`mt-1 inline-flex items-center gap-1 text-sm font-medium ${
                  isOnline ? 'text-cyan-300' : 'text-amber-300'
                }`}
              >
                {isOnline ? <Wifi className="h-4 w-4" /> : <WifiOff className="h-4 w-4" />}
                {isOnline ? t('Online', 'Συνδεδεμένο') : t('Offline', 'Εκτός σύνδεσης')}
              </p>
            </div>
            <div className="workspace-card px-3 py-2.5">
              <p className="text-[10px] uppercase text-slate-500">
                {t('Local time', 'Τοπική ώρα')}
              </p>
              <p className="mt-1 text-sm font-medium text-cyan-300">
                {now.toLocaleTimeString(locale, {
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit',
                })}
              </p>
            </div>
            <div className="workspace-card min-w-0 px-3 py-2.5">
              <p className="text-[10px] uppercase text-slate-500">{t('Operator', 'Χειριστής')}</p>
              <p className="mt-1 max-w-28 truncate text-sm font-medium text-white">
                {user?.full_name || user?.username || t('Trader', 'Trader')}
              </p>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
