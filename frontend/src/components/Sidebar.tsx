import { Command, LogOut, Search, X } from 'lucide-react';
import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { getUserWorkspaceRole } from '../auth/roles';
import { useI18n } from '../i18n/useI18n';
import {
  filterNavItemsForRole,
  getWorkspaceNavItems,
  getWorkspaceQuickActions,
  isNavItemActive,
  workspaceSections,
} from '../navigation/workspaceNav';
import { getCurrentPortalType, getPortalLabel } from '../app/portal';
import { useAuthStore } from '../store/auth';
import { BrandMark } from './BrandMark';

interface SidebarProps {
  isOpen: boolean;
  onClose?: () => void;
  onOpenCommandPalette?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose, onOpenCommandPalette }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const { t, tr } = useI18n();
  const role = getUserWorkspaceRole(user);
  const portal = getCurrentPortalType();
  const visibleNavItems = filterNavItemsForRole(getWorkspaceNavItems(portal), role);
  const visibleQuickActions = filterNavItemsForRole(getWorkspaceQuickActions(portal), role);
  const sectionLabel = (section: (typeof workspaceSections)[number]) => {
    const labels = {
      Overview: t('Overview', 'Επισκόπηση'),
      'Strategy Lab': t('Strategy Lab', 'Εργαστήριο Στρατηγικής'),
      Backtests: t('Backtests', 'Backtests'),
      'Live Trading': t('Live Trading', 'Ζωντανές Συναλλαγές'),
      Intelligence: t('Intelligence', 'Πληροφόρηση'),
      Administration: t('Administration', 'Διαχείριση'),
      'IB Portal': t('IB Portal', 'Πύλη IB'),
      Account: t('Account', 'Λογαριασμός'),
    };

    return labels[section];
  };

  const handleLogout = () => {
    logout();
    onClose?.();
    navigate('/login');
  };

  return (
    <>
      {/* Backdrop dismiss is a pointer-only convenience; the drawer itself
          exposes a close button and Escape for keyboard operators. */}
      {isOpen && (
        <div
          role="presentation"
          className="fixed inset-0 z-40 bg-black/55 lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={`premium-sidebar app-sidebar fixed z-50 flex h-screen w-76 shrink-0 flex-col border-r border-slate-800/80 transition-transform duration-300 lg:sticky lg:top-0 lg:self-start ${
          isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        <div className="lg:hidden flex justify-end p-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-stone-800 bg-stone-950/80 p-2 text-stone-400 transition hover:text-white"
            aria-label="Close navigation"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="border-b border-slate-800/90 px-5 pb-4 pt-4 lg:pt-6">
          <div className="flex items-center gap-3">
            <BrandMark compact />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <p className="truncate text-lg font-semibold text-white">ExecutionLab</p>
                <span className="rounded-full bg-cyan-400/80 p-1" title={t('Ready', 'Έτοιμο')} />
              </div>
              <p className="truncate text-xs text-slate-500">
                {t(getPortalLabel(portal), getPortalLabel(portal))}
              </p>
            </div>
          </div>

          <div className="mt-4 grid gap-3">
            <button
              type="button"
              onClick={() => {
                onOpenCommandPalette?.();
                onClose?.();
              }}
              className="workspace-card flex w-full items-center gap-3 px-3 py-3 text-left transition hover:border-cyan-500/20"
            >
              <div className="rounded-lg border border-slate-800 bg-slate-950 p-2 text-cyan-200">
                <Search className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-slate-100">
                  {t('Command palette', 'Παλέτα εντολών')}
                </p>
                <p className="truncate text-xs text-slate-500">
                  {t(
                    'Find routes, actions, and recent screens',
                    'Βρείτε διαδρομές, ενέργειες και πρόσφατες οθόνες'
                  )}
                </p>
              </div>
              <span className="rounded-lg border border-slate-800 bg-slate-950 px-2 py-1 text-[10px] uppercase text-slate-500">
                <Command className="inline h-3 w-3" /> K
              </span>
            </button>
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto px-4 py-4">
          <div className="mb-5">
            <p className="px-1 text-[10px] font-semibold uppercase text-slate-500">
              {t('Primary actions', 'Κύριες ενέργειες')}
            </p>
            <div className="mt-3 grid grid-cols-3 gap-2">
              {visibleQuickActions.slice(0, 3).map((item) => {
                const Icon = item.icon;
                return (
                  <Link
                    key={`quick-${item.path}`}
                    to={item.path}
                    onClick={onClose}
                    className="flex min-h-22 flex-col items-start justify-between rounded-lg border border-slate-800 bg-stone-950/78 p-3 text-left text-slate-300 transition hover:border-cyan-500/30 hover:bg-stone-900 hover:text-white"
                    title={tr(item.description)}
                  >
                    <div className="rounded-lg border border-slate-800 bg-stone-900 p-2 text-cyan-200">
                      <Icon className="h-4 w-4" />
                    </div>
                    <p className="mt-2 text-xs font-semibold leading-4 text-slate-100">
                      {tr(item.label)}
                    </p>
                  </Link>
                );
              })}
            </div>
          </div>

          <div className="space-y-5">
            {workspaceSections.map((section) => {
              const items = visibleNavItems.filter((item) => item.section === section);
              if (items.length === 0) return null;

              return (
                <div key={section}>
                  <p className="px-3 text-[10px] font-semibold uppercase text-slate-500">
                    {sectionLabel(section)}
                  </p>
                  <div className="mt-2 space-y-1">
                    {items.map((item) => {
                      const active = isNavItemActive(location.pathname, item);
                      const Icon = item.icon;

                      return (
                        <Link
                          key={item.path}
                          to={item.path}
                          onClick={onClose}
                          title={tr(item.description)}
                          className={`group flex w-full items-center gap-3 rounded-lg px-4 py-3 text-left transition-all ${
                            active
                              ? 'border border-teal-400/30 bg-teal-500/16 text-white shadow-lg shadow-teal-500/10'
                              : 'border border-transparent text-slate-400 hover:border-slate-800 hover:bg-stone-900/80 hover:text-white'
                          }`}
                        >
                          <span
                            className={
                              active ? 'text-white' : 'text-slate-400 group-hover:text-white'
                            }
                          >
                            <Icon className="h-5 w-5" />
                          </span>
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium">{tr(item.label)}</p>
                            <p
                              className={`hidden truncate text-xs xl:block ${active ? 'text-teal-100/80' : 'text-slate-500'}`}
                            >
                              {tr(item.description)}
                            </p>
                          </div>
                          {item.shortcut && !active && (
                            <span className="hidden rounded-lg border border-slate-800 bg-slate-950 px-2 py-1 text-[10px] uppercase text-slate-500 2xl:inline-flex">
                              {item.shortcut}
                            </span>
                          )}
                          {active && (
                            <div className="ml-auto h-1.5 w-1.5 rounded-full bg-white/70" />
                          )}
                        </Link>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </nav>

        <div className="border-t border-slate-800/90 px-4 py-4">
          <div className="flex items-center gap-3 rounded-lg border border-slate-800 bg-stone-950/62 px-3 py-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-cyan-500/20 bg-cyan-500/10 text-xs font-bold text-cyan-200">
              {(user?.full_name || user?.username || 'T').slice(0, 2).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[10px] uppercase text-slate-500">
                {t('Signed in as', 'Συνδεδεμένος ως')}
              </p>
              <p
                className="truncate text-sm font-semibold text-white"
                title={user?.full_name || user?.username || undefined}
              >
                {user?.full_name || user?.username}
              </p>
              <p className="truncate text-xs text-slate-500" title={user?.email || undefined}>
                {user?.email}
              </p>
            </div>
            {user?.role && (
              <span className="rounded-lg border border-cyan-500/20 bg-cyan-500/10 px-2 py-1 text-[10px] font-semibold uppercase text-cyan-300">
                {user.role}
              </span>
            )}
          </div>

          <button
            type="button"
            onClick={handleLogout}
            className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-red-600/90 px-4 py-3 text-sm font-medium text-white transition-colors hover:bg-red-600"
          >
            <LogOut className="h-4 w-4" />
            {t('Logout', 'Αποσύνδεση')}
          </button>
        </div>
      </aside>
    </>
  );
};
