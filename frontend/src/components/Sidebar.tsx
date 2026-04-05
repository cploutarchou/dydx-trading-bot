/**
 * Sidebar Navigation Component
 * Persistent left sidebar with navigation links, user info, and logout
 */

import { BarChart3, Bot, Home, Library, LogOut, PlayCircle, Settings, Sparkles, Target, X } from 'lucide-react';
import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/auth';

interface SidebarProps {
  isOpen: boolean;
  onClose?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();

  const handleLogout = () => {
    logout();
    onClose?.();
    navigate('/login');
  };

  const navItems = [
    {
      label: 'Dashboard',
      path: '/dashboard',
      icon: <Home className="w-5 h-5" />,
      exact: true,
    },
    {
      label: 'Strategies',
      path: '/strategies',
      icon: <Library className="w-5 h-5" />,
      exact: true,
    },
    {
      label: 'Strategy Runtime',
      path: '/strategies/manage',
      icon: <PlayCircle className="w-5 h-5" />,
      exact: false,
    },
    {
      label: 'Bot Manager',
      path: '/bots',
      icon: <Bot className="w-5 h-5" />,
      exact: false,
    },
    {
      label: 'Backtests',
      path: '/backtests',
      icon: <Target className="w-5 h-5" />,
      exact: true,
    },
    {
      label: 'Codex',
      path: '/codex',
      icon: <Sparkles className="w-5 h-5" />,
      exact: true,
    },
    {
      label: 'Compare Backtests',
      path: '/backtests/compare',
      icon: <BarChart3 className="w-5 h-5" />,
      exact: false,
    },
    {
      label: 'Settings',
      path: '/settings',
      icon: <Settings className="w-5 h-5" />,
      exact: false,
    },
  ];

  const isActive = (path: string, exact = true) =>
    exact ? location.pathname === path : location.pathname.startsWith(path);

  return (
    <>
      {/* Mobile Overlay */}
      {isOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 lg:hidden z-40" onClick={onClose} />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed lg:static w-64 h-screen bg-slate-900 border-r border-slate-700 flex flex-col transition-transform duration-300 z-50 ${
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
        <div className="px-6 py-8 border-b border-slate-700">
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
              📊
            </div>
            dYdX Bot
          </h1>
          <p className="text-xs text-gray-400 mt-2">Trading & Analysis</p>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 px-4 py-6">
          <div className="space-y-1">
            {navItems.map((item) => {
              const active = isActive(item.path, item.exact);
              return (
                <button
                  key={item.path}
                  type="button"
                  onClick={() => {
                    navigate(item.path);
                    onClose?.();
                  }}
                  className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    active
                      ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20'
                      : 'text-gray-400 hover:bg-slate-800 hover:text-white'
                  }`}
                >
                  <span className={active ? 'text-white' : 'text-slate-400 group-hover:text-white'}>
                    {item.icon}
                  </span>
                  <span>{item.label}</span>
                  {active && <div className="ml-auto w-1.5 h-1.5 bg-white/70 rounded-full" />}
                </button>
              );
            })}
          </div>
        </nav>

        {/* User Section */}
        <div className="px-4 py-4 border-t border-slate-700">
          {/* User Info */}
          <div className="mb-4 p-3 bg-slate-800 rounded-lg">
            <p className="text-xs text-gray-400 mb-1">Logged in as</p>
            <p className="text-sm font-semibold text-white truncate">{user?.username}</p>
            <p className="text-xs text-gray-400 truncate">{user?.email}</p>
          </div>

          {/* Logout Button */}
          <button
            type="button"
            onClick={handleLogout}
            className="w-full flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Logout
          </button>
        </div>
      </aside>
    </>
  );
};
