/**
 * Main Layout Component
 * Wraps pages with Sidebar + Header
 * Handles responsive design and mobile menu state
 */

import React, { memo, useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import {
    getRecentPaths,
    persistRecentPath,
    WorkspaceCommandPalette,
} from './WorkspaceCommandPalette';

interface MainLayoutProps {
  children: React.ReactNode;
}

const MainLayoutContent: React.FC<MainLayoutProps> = ({ children }) => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [recentPaths, setRecentPaths] = useState<string[]>([]);
  const location = useLocation();

  const toggleMobileMenu = () => {
    setIsMobileMenuOpen(!isMobileMenuOpen);
  };

  const closeMobileMenu = () => {
    setIsMobileMenuOpen(false);
  };

  useEffect(() => {
    setRecentPaths(getRecentPaths());
  }, []);

  useEffect(() => {
    persistRecentPath(location.pathname);
    setRecentPaths(getRecentPaths());
  }, [location.pathname]);

  useEffect(() => {
    const handleKeyboardShortcut = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setIsCommandPaletteOpen((current) => !current);
      }
    };

    window.addEventListener('keydown', handleKeyboardShortcut);
    return () => window.removeEventListener('keydown', handleKeyboardShortcut);
  }, []);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  return (
    <div className="premium-shell app-shell flex h-screen overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        isOpen={isMobileMenuOpen}
        onClose={closeMobileMenu}
        onOpenCommandPalette={() => setIsCommandPaletteOpen(true)}
      />

      {/* Main Content Area */}
      <div className="relative flex min-w-0 flex-1 flex-col overflow-hidden">
        {/* Header */}
        <Header
          onMenuToggle={toggleMobileMenu}
          onOpenCommandPalette={() => setIsCommandPaletteOpen(true)}
        />

        {/* Page Content */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-cyan-500 focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-slate-900"
        >
          Skip to content
        </a>
        <main id="main-content" tabIndex={-1} className="relative z-10 flex-1 overflow-x-hidden overflow-y-auto">
          <div key={location.pathname} className="animate-page-enter h-full">
            {children}
          </div>
        </main>
      </div>

      <WorkspaceCommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        recentPaths={recentPaths}
      />
    </div>
  );
};

export const MainLayout = memo(MainLayoutContent);
MainLayout.displayName = 'MainLayout';
