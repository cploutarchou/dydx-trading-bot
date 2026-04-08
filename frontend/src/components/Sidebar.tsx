/**
 * Sidebar Navigation Component
 * Persistent left sidebar with grouped navigation, quick actions, and operator controls
 */

import { Command, LogOut, X } from 'lucide-react';
import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
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

  const handleLogout = () => {
    logout();
    onClose?.();
    navigate('/login');
  };

  return (
    <>
      {/* Mobile Overlay */}
      {isOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 lg:hidden z-40" onClick={onClose} />
      )}

      {/* Sidebar */}
      <aside
        className={`premium-sidebar fixed lg:static w-72 h-screen border-r border-slate-800/80 flex flex-col transition-transform duration-300 z-50 ${
          isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        {/* Close button for mobile */}
        <div className="lg:hidden flex justify-end p-4">
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Logo/Title */}
        <div className="px-6 py-8 border-b border-slate-800/90">
          <div className="mb-4 inline-flex rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-cyan-300">
            Trading OS
          </div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-cyan-500 via-blue-500 to-emerald-400 shadow-lg shadow-cyan-500/20 flex items-center justify-center">
              📊
            </div>
            dYdX Bot
          </h1>
          <p className="text-xs text-slate-400 mt-3 leading-5">
            Trading intelligence, strategy operations, and premium backtest insight in one cockpit.
          </p>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 space-y-5 overflow-y-auto px-4 py-6">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-3">
            <p className="px-1 text-[10px] uppercase tracking-[0.18em] text-slate-500">
              Quick Actions
            </p>
            <div className="mt-3 space-y-2">
              {workspaceQuickActions.slice(0, 3).map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={`quick-${item.path}`}
                    type="button"
                    onClick={() => {
                      navigate(item.path);
                      onClose?.();
                    }}
                    className="flex w-full items-center gap-3 rounded-2xl border border-slate-800 bg-slate-950/80 px-3 py-3 text-left text-sm text-slate-300 transition hover:border-slate-700 hover:bg-slate-900 hover:text-white"
                  >
                    <div className="rounded-xl border border-slate-800 bg-slate-900 p-2 text-cyan-200">
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

          <button
            type="button"
            onClick={() => {
              onOpenCommandPalette?.();
              onClose?.();
            }}
            className="flex w-full items-center gap-3 rounded-2xl border border-slate-800 bg-slate-900/70 px-4 py-3 text-left text-sm text-slate-300 transition hover:border-slate-700 hover:text-white"
          >
            <div className="rounded-xl border border-slate-800 bg-slate-950 p-2 text-cyan-200">
              <Command className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="font-medium text-slate-100">Command Palette</p>
              <p className="truncate text-xs text-slate-500">Jump anywhere with keyboard-first navigation</p>
            </div>
            <span className="rounded-lg border border-slate-800 bg-slate-950 px-2 py-1 text-[10px] uppercase tracking-[0.16em] text-slate-500">
              Ctrl K
            </span>
          </button>

          <div className="space-y-4">
            {workspaceSections.map((section) => {
              const items = workspaceNavItems.filter((item) => item.section === section);
              if (items.length === 0) return null;
              return (
                <div key={section}>
                  <p className="px-3 text-[10px] uppercase tracking-[0.18em] text-slate-500">
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
                          className={`group flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left text-sm font-medium transition-all ${
                            active
                              ? 'bg-gradient-to-r from-cyan-600 to-blue-600 text-white shadow-lg shadow-cyan-500/20'
                              : 'text-slate-400 hover:bg-slate-800/80 hover:text-white'
                          }`}
                        >
                          <span className={active ? 'text-white' : 'text-slate-400 group-hover:text-white'}>
                            <Icon className="h-5 w-5" />
                          </span>
                          <div className="min-w-0 flex-1">
                            <p>{item.label}</p>
                            <p className={`truncate text-xs ${active ? 'text-cyan-100/80' : 'text-slate-500'}`}>
                              {item.description}
                            </p>
                          </div>
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

        {/* User Section */}
        <div className="px-4 py-4 border-t border-slate-800/90">
          {/* User Info */}
          <div className="mb-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
            <p className="text-xs text-gray-400 mb-1">Logged in as</p>
            <p className="text-sm font-semibold text-white truncate">{user?.username}</p>
            <p className="text-xs text-gray-400 truncate">{user?.email}</p>
            {user?.role && (
              <div className="mt-3 inline-flex rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-cyan-300">
                {user.role}
              </div>
            )}
          </div>

          {/* Logout Button */}
          <button
            type="button"
            onClick={handleLogout}
            className="w-full flex items-center gap-2 px-4 py-3 bg-red-600/90 hover:bg-red-600 text-white text-sm font-medium rounded-2xl transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Logout
          </button>
        </div>
      </aside>
    </>
  );
};
