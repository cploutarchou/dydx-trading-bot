/**
 * Sidebar Navigation Component
 * Persistent left sidebar with navigation links, user info, and logout
 */

import { BarChart3, Home, LogOut, Settings, X, Zap } from 'lucide-react';
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
    },
    {
      label: 'Strategies',
      path: '/strategies',
      icon: <Zap className="w-5 h-5" />,
    },
    {
      label: 'Strategy Runtime',
      path: '/strategies/manage',
      icon: <Zap className="w-5 h-5" />,
    },
    {
      label: 'Bot Manager',
      path: '/bots',
      icon: <Zap className="w-5 h-5" />,
    },
    {
      label: 'Compare Backtests',
      path: '/backtests/compare',
      icon: <BarChart3 className="w-5 h-5" />,
    },
    {
      label: 'Settings',
      path: '/settings',
      icon: <Settings className="w-5 h-5" />,
    },
  ];

  const isActive = (path: string) => location.pathname === path;

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
          <div className="space-y-2">
            {navItems.map((item) => (
              <button
                key={item.path}
                type="button"
                onClick={() => {
                  navigate(item.path);
                  onClose?.();
                }}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                  isActive(item.path)
                    ? 'bg-blue-600 text-white shadow-lg'
                    : 'text-gray-300 hover:bg-slate-800 hover:text-white'
                }`}
              >
                {item.icon}
                <span>{item.label}</span>
                {isActive(item.path) && <div className="ml-auto w-2 h-2 bg-white rounded-full" />}
              </button>
            ))}
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
