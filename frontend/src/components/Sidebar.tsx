import { Activity, Command, LogOut, Sparkles, X } from 'lucide-react';
import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { getUserWorkspaceRole } from '../auth/roles';
import {
  filterNavItemsForRole,
  isNavItemActive,
  workspaceNavItems,
  workspaceQuickActions,
  workspaceSections,
} from '../navigation/workspaceNav';
import { useAuthStore } from '../store/auth';

interface SidebarProps {
  isOpen: boolean;
  onClose?: () => void;
  onOpenCommandPalette?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose, onOpenCommandPalette }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const role = getUserWorkspaceRole(user);
  const visibleNavItems = filterNavItemsForRole(workspaceNavItems, role);
  const visibleQuickActions = filterNavItemsForRole(workspaceQuickActions, role);

  const handleLogout = () => {
    logout();
    onClose?.();
    navigate('/login');
  };

  return (
    <>
      {isOpen && (
        <div className="fixed inset-0 z-40 bg-black/55 lg:hidden" onClick={onClose} />
      )}

      <aside
        className={`premium-sidebar fixed z-50 flex h-screen w-[19rem] shrink-0 flex-col border-r border-slate-800/80 transition-transform duration-300 lg:sticky lg:top-0 lg:self-start ${
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

        <div className="border-b border-slate-800/90 px-6 pb-6 pt-4 lg:pt-8">
          <div className="workspace-chip border-cyan-500/20 text-cyan-200">
            <Sparkles className="h-3.5 w-3.5" />
            Trading desk
          </div>

          <div className="mt-4 flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-lg border border-teal-300/30 bg-teal-400/15 text-sm font-semibold text-teal-100">
              dY
            </div>
            <div>
              <h1 className="text-lg font-semibold text-white">dYdX Arbitrage OS</h1>
              <p className="text-xs text-slate-500">Research, backtests, bots, and controls</p>
            </div>
          </div>

          <div className="mt-5 grid gap-3">
            <div className="workspace-card px-4 py-4">
              <div className="flex items-center gap-2 text-emerald-300">
                <Activity className="h-4 w-4" />
                <p className="text-sm font-semibold text-white">Workspace ready</p>
              </div>
              <p className="mt-2 text-xs leading-5 text-slate-400">
                Active routes, quick actions, and command access stay within one scan.
              </p>
            </div>

            <button
              type="button"
              onClick={() => {
                onOpenCommandPalette?.();
                onClose?.();
              }}
              className="workspace-card flex w-full items-center gap-3 px-4 py-4 text-left transition hover:border-cyan-500/20"
            >
              <div className="rounded-lg border border-slate-800 bg-slate-950 p-2 text-cyan-200">
                <Command className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-slate-100">Command palette</p>
                <p className="truncate text-xs text-slate-500">
                  Jump anywhere with keyboard-first navigation
                </p>
              </div>
              <span className="rounded-lg border border-slate-800 bg-slate-950 px-2 py-1 text-[10px] uppercase text-slate-500">
                Ctrl K
              </span>
            </button>
          </div>
        </div>

        <nav className="flex-1 space-y-6 overflow-y-auto px-4 py-6">
          <div className="workspace-card px-3 py-3">
            <p className="px-1 text-[10px] uppercase text-slate-500">
              Quick actions
            </p>
            <div className="mt-3 space-y-2">
              {visibleQuickActions.slice(0, 3).map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={`quick-${item.path}`}
                    type="button"
                    onClick={() => {
                      navigate(item.path);
                      onClose?.();
                    }}
                    className="flex w-full items-center gap-3 rounded-lg border border-slate-800 bg-stone-950/78 px-3 py-3 text-left text-sm text-slate-300 transition hover:border-slate-700 hover:bg-stone-900 hover:text-white"
                  >
                    <div className="rounded-lg border border-slate-800 bg-stone-900 p-2 text-cyan-200">
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <p className="font-medium text-slate-100">{item.label}</p>
                      <p className="truncate text-xs text-slate-500">{item.description}</p>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="space-y-4">
            {workspaceSections.map((section) => {
              const items = visibleNavItems.filter((item) => item.section === section);
              if (items.length === 0) return null;

              return (
                <div key={section}>
                  <p className="px-3 text-[10px] uppercase text-slate-500">
                    {section}
                  </p>
                  <div className="mt-2 space-y-1">
                    {items.map((item) => {
                      const active = isNavItemActive(location.pathname, item);
                      const Icon = item.icon;

                      return (
                        <button
                          key={item.path}
                          type="button"
                          onClick={() => {
                            navigate(item.path);
                            onClose?.();
                          }}
                          className={`group flex w-full items-center gap-3 rounded-lg px-4 py-3 text-left transition-all ${
                            active
                              ? 'border border-teal-400/30 bg-teal-500/16 text-white shadow-lg shadow-teal-500/10'
                              : 'border border-transparent text-slate-400 hover:border-slate-800 hover:bg-stone-900/80 hover:text-white'
                          }`}
                        >
                          <span className={active ? 'text-white' : 'text-slate-400 group-hover:text-white'}>
                            <Icon className="h-5 w-5" />
                          </span>
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium">{item.label}</p>
                            <p className={`truncate text-xs ${active ? 'text-teal-100/80' : 'text-slate-500'}`}>
                              {item.description}
                            </p>
                          </div>
                          {item.shortcut && !active && (
                            <span className="hidden rounded-lg border border-slate-800 bg-slate-950 px-2 py-1 text-[10px] uppercase text-slate-500 2xl:inline-flex">
                              {item.shortcut}
                            </span>
                          )}
                          {active && <div className="ml-auto h-1.5 w-1.5 rounded-full bg-white/70" />}
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </nav>

        <div className="border-t border-slate-800/90 px-4 py-4">
          <div className="workspace-card px-4 py-4">
            <p className="text-[10px] uppercase text-slate-500">Signed in as</p>
            <p className="mt-2 truncate text-sm font-semibold text-white">
              {user?.full_name || user?.username}
            </p>
            <p className="truncate text-xs text-slate-500">{user?.email}</p>
            {user?.role && (
              <div className="mt-3 inline-flex rounded-lg border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-[11px] font-semibold uppercase text-cyan-300">
                {user.role}
              </div>
            )}
          </div>

          <button
            type="button"
            onClick={handleLogout}
            className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-red-600/90 px-4 py-3 text-sm font-medium text-white transition-colors hover:bg-red-600"
          >
            <LogOut className="h-4 w-4" />
            Logout
          </button>
        </div>
      </aside>
    </>
  );
};
