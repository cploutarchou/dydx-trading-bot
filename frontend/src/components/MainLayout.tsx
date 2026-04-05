/**
 * Main Layout Component
 * Wraps pages with Sidebar + Header
 * Handles responsive design and mobile menu state
 */

import React, { useState } from 'react';
import { Header } from './Header';
import { Sidebar } from './Sidebar';

interface MainLayoutProps {
  children: React.ReactNode;
}

export const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const toggleMobileMenu = () => {
    setIsMobileMenuOpen(!isMobileMenuOpen);
  };

  const closeMobileMenu = () => {
    setIsMobileMenuOpen(false);
  };

  return (
    <div className="premium-shell flex min-h-screen text-white">
      <div className="premium-orb left-[-8rem] top-12 h-64 w-64 bg-cyan-500/10" />
      <div className="premium-orb right-[-6rem] top-28 h-72 w-72 bg-blue-500/12" />

      {/* Sidebar */}
      <Sidebar isOpen={isMobileMenuOpen} onClose={closeMobileMenu} />

      {/* Main Content Area */}
      <div className="relative flex min-w-0 flex-1 flex-col overflow-hidden">
        {/* Header */}
        <Header onMenuToggle={toggleMobileMenu} />

        {/* Page Content */}
        <main className="relative z-10 flex-1 overflow-x-hidden overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
};
