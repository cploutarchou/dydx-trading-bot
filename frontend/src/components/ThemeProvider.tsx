import React, { useEffect } from 'react';
import { resolveTheme, useUIPreferencesStore } from '../store/uiPreferences';

interface ThemeProviderProps {
  children: React.ReactNode;
}

export const ThemeProvider: React.FC<ThemeProviderProps> = ({ children }) => {
  const theme = useUIPreferencesStore((state) => state.theme);
  const resolvedTheme = useUIPreferencesStore((state) => state.resolvedTheme);
  const setResolvedTheme = useUIPreferencesStore((state) => state.setResolvedTheme);

  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute('data-theme', resolvedTheme);
    root.setAttribute('data-theme-preference', theme);
    root.style.colorScheme = resolvedTheme;
  }, [resolvedTheme, theme]);

  useEffect(() => {
    if (theme !== 'system' || typeof window === 'undefined' || !window.matchMedia) {
      return;
    }

    const mediaQuery = window.matchMedia('(prefers-color-scheme: light)');
    const handleChange = () => setResolvedTheme(resolveTheme('system'));
    handleChange();
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, [setResolvedTheme, theme]);

  return <>{children}</>;
};
